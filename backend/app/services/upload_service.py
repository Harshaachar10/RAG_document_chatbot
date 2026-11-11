from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.settings import Settings
from app.identity.hard_stops import evaluate_hard_stops, record_level_flags
from app.identity.npi import classify_npi, lookup_npi
from app.identity.pipeline import run_identity_pipeline
from app.identity.redact import redact_text
from app.identity.routing import route_decision
from app.identity.scoring import score_pair
from app.identity.standardize import standardize_record
from app.utils.dates import utc_now_iso

ALLOWED_STRUCTURED = {".csv", ".xlsx", ".xls"}
ALLOWED_DOCUMENTS = {".pdf", ".txt", ".png", ".jpg", ".jpeg"}
# Simple magic-byte checks
SIGNATURES = {
    b"%PDF": ".pdf",
    b"PK\x03\x04": ".xlsx",  # also zip; xlsx is zip
    b"\x89PNG": ".png",
    b"\xff\xd8\xff": ".jpg",
}

HEADER_ALIASES = {
    "npi": ["npi", "npi_vod", "prescriber_npi", "recipient_npi", "provider_npi", "billing_npi"],
    "first_name": ["first_name", "first", "recipient_first", "provider_first_name", "given_name"],
    "last_name": ["last_name", "last", "recipient_last", "provider_last_name", "family_name"],
    "full_name": ["full_name", "name", "account_name", "prescriber_name", "attendee", "recorded_name"],
    "specialty": ["specialty", "specialty_desc", "recipient_specialty"],
    "organization": ["organization", "practice", "primary_parent", "primary_org", "org_as_written"],
    "city": ["city", "practice_city", "venue_city"],
    "state": ["state", "st", "practice_state", "venue_state"],
    "phone": ["phone", "practice_phone", "prescriber_phone"],
    "email": ["email"],
    "address": ["address", "practice_address"],
    "license": ["license_no", "state_license", "license_number_1"],
    "amount": ["amount_usd", "amount"],
    "date": ["payment_date", "service_date", "event_date", "enroll_date", "record_date", "last_modified"],
}


class UploadService:
    def __init__(self, repo: Any, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings
        self.settings.upload_path.mkdir(parents=True, exist_ok=True)

    def list_batches(self) -> Dict[str, Any]:
        batches = list(self.repo.state().get("upload_batches") or [])
        batches.sort(key=lambda b: b.get("created_at") or "", reverse=True)
        return {"items": batches, "total": len(batches), "snapshot_version": self.repo.snapshot_version()}

    def get_batch(self, batch_id: str) -> Dict[str, Any]:
        for b in self.repo.state().get("upload_batches") or []:
            if b.get("batch_id") == batch_id:
                return b
        raise NotFoundError(f"Upload batch {batch_id} not found")

    def upload_file(
        self,
        *,
        filename: str,
        content: bytes,
        mode: str,
        uploaded_by: str = "Steward",
    ) -> Dict[str, Any]:
        if not content:
            raise ValidationAppError("Empty file")
        if len(content) > int(self.settings.upload_max_bytes):
            raise ValidationAppError(
                f"File exceeds size limit of {self.settings.upload_max_bytes} bytes",
            )
        suffix = Path(filename).suffix.lower()
        if mode == "structured" and suffix not in ALLOWED_STRUCTURED:
            raise ValidationAppError(f"Unsupported structured file type: {suffix}")
        if mode == "document" and suffix not in ALLOWED_DOCUMENTS:
            raise ValidationAppError(f"Unsupported document type: {suffix}")
        if mode not in {"structured", "document"}:
            raise ValidationAppError("mode must be structured or document")

        sig_ok, sig_reason = self._check_signature(content, suffix)
        if not sig_ok:
            raise ValidationAppError(sig_reason)

        checksum = hashlib.sha256(content).hexdigest()
        # Duplicate upload: return existing batch, no new links
        for existing in self.repo.state().get("upload_batches") or []:
            if existing.get("checksum") == checksum and existing.get("status") in {
                "mapped", "matched", "committed", "awaiting_confirm", "extracted"
            }:
                return {**existing, "duplicate_of": existing.get("batch_id"), "message": "Repeat upload — no duplicate links or changes made."}

        batch_id = f"UP-{uuid.uuid4().hex[:10].upper()}"
        dest = self.settings.upload_path / f"{batch_id}{suffix}"
        dest.write_bytes(content)

        batch: Dict[str, Any] = {
            "batch_id": batch_id,
            "filename": filename,
            "mode": mode,
            "suffix": suffix,
            "checksum": checksum,
            "stored_path": str(dest),
            "uploaded_by": uploaded_by or "Steward",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "status": "uploaded",
            "steps": [
                {"key": "upload", "label": "Upload", "status": "done"},
                {"key": "file_checks", "label": "File checks", "status": "running"},
                {"key": "read_extract", "label": "Read and extract", "status": "pending"},
                {"key": "protect", "label": "Protect patient data", "status": "pending"},
                {"key": "map_fields", "label": "Map fields", "status": "pending"},
                {"key": "standardize", "label": "Standardize", "status": "pending"},
                {"key": "npi_check", "label": "Check NPI", "status": "pending"},
                {"key": "match", "label": "Match to master", "status": "pending"},
                {"key": "nppes", "label": "Check NPPES if needed", "status": "pending"},
                {"key": "route", "label": "Route", "status": "pending"},
                {"key": "review_results", "label": "Review results", "status": "pending"},
                {"key": "commit", "label": "Commit", "status": "pending"},
            ],
            "errors": [],
            "quarantined_rows": [],
            "mapping": None,
            "records": [],
            "results": [],
            "action_counts": {},
            "committed": False,
            "rollback_of": None,
        }

        try:
            self._set_step(batch, "file_checks", "done")
            if mode == "structured":
                self._process_structured(batch, content, suffix)
            else:
                self._process_document(batch, content, suffix)
        except ValidationAppError as exc:
            batch["status"] = "rejected"
            batch["errors"].append(str(exc))
            self._set_step(batch, "file_checks", "failed")
            self._save_batch(batch)
            raise

        self._save_batch(batch)
        return batch

    def confirm_mapping(self, batch_id: str, mapping: Dict[str, str]) -> Dict[str, Any]:
        batch = self.get_batch(batch_id)
        if batch.get("mode") != "structured":
            raise ValidationAppError("Mapping confirmation only applies to structured uploads")
        required = {"full_name"} if "full_name" in mapping.values() else set()
        # need name somehow
        has_name = (
            "full_name" in mapping.values()
            or ("first_name" in mapping.values() and "last_name" in mapping.values())
        )
        if not has_name:
            batch["status"] = "rejected"
            batch["errors"].append("Required name column cannot be mapped")
            self._save_batch(batch)
            raise ValidationAppError("Required name column is missing and cannot be mapped — file rejected with no partial commit")

        batch["mapping"] = mapping
        batch["status"] = "mapped"
        self._set_step(batch, "map_fields", "done")
        # rebuild records from stored raw rows using mapping
        raw_rows = batch.get("raw_rows") or []
        records, quarantined = self._rows_to_records(raw_rows, mapping, batch_id)
        batch["quarantined_rows"] = quarantined
        batch["records"] = records
        self._match_records(batch)
        self._save_batch(batch)
        return batch

    def confirm_document_extract(self, batch_id: str, extracted: Dict[str, Any]) -> Dict[str, Any]:
        batch = self.get_batch(batch_id)
        if batch.get("mode") != "document":
            raise ValidationAppError("Document confirmation only applies to document uploads")
        # Validate quotes exist in redacted text
        redacted = batch.get("redacted_text") or ""
        quote = (extracted.get("source_quote") or "").strip()
        if quote and quote not in redacted:
            raise ValidationAppError("Source quote was not found in the redacted document text — rejected")
        # Never invent NPI
        if not extracted.get("stated_npi"):
            extracted["stated_npi"] = None
        batch["extracted"] = extracted
        self._set_step(batch, "map_fields", "done")
        record = self._extracted_to_record(extracted, batch_id)
        batch["records"] = [record]
        self._match_records(batch)
        self._save_batch(batch)
        return batch

    def commit(self, batch_id: str) -> Dict[str, Any]:
        batch = self.get_batch(batch_id)
        if batch.get("committed"):
            return batch
        if batch.get("status") not in {"matched", "awaiting_confirm"}:
            raise ValidationAppError("Batch is not ready to commit")

        snapshot = {
            "doctors": self.repo.state().get("doctors"),
            "source_links": self.repo.state().get("source_links"),
            "source_records": self.repo.state().get("source_records"),
            "reviews": self.repo.state().get("reviews"),
        }

        def mutator(state: Dict[str, Any]) -> None:
            state.setdefault("upload_rollbacks", {})[batch_id] = {
                "saved_at": utc_now_iso(),
                "snapshot_keys": list(snapshot.keys()),
                # shallow copy ids only for restore of links added
                "link_ids_added": [],
                "review_ids_added": [],
                "doctor_ids_added": [],
                "record_ids_added": [],
            }
            rb = state["upload_rollbacks"][batch_id]
            for result in batch.get("results") or []:
                action = result.get("action")
                rec = result.get("record") or {}
                uid = rec.get("uid")
                if not uid:
                    continue
                # store source record (proposed changes only — never overwrite golden attrs here)
                state.setdefault("source_records", {})[uid] = {
                    "source_record_id": uid,
                    "source_id": f"upload:{batch_id}",
                    "record_kind": "upload",
                    "recorded_name": ((rec.get("standardized") or {}).get("name") or {}).get("display"),
                    "specialty": (rec.get("standardized") or {}).get("specialty"),
                    "practice_name": (rec.get("standardized") or {}).get("organization"),
                    "city": (rec.get("standardized") or {}).get("city"),
                    "state": (rec.get("standardized") or {}).get("state"),
                    "provider_identifier": result.get("npi"),
                    "identifier_kind": "npi" if result.get("npi") else None,
                    "resolution_status": "linked" if action == "LINK" else "pending_review",
                    "raw": rec.get("raw") or {},
                    "standardized": rec.get("standardized") or {},
                    "npi_fields": rec.get("npi_fields") or [],
                    "record_flags": rec.get("record_flags") or [],
                    "upload_batch_id": batch_id,
                    "ingested_at": utc_now_iso(),
                    "evidence_ids": [],
                    "note_text": "",
                }
                rb["record_ids_added"].append(uid)

                if action == "LINK" and result.get("doctor_id"):
                    # Wrong NPI must not update master — only link history
                    if result.get("stated_npi_status") in {"mismatch", "invalid", "group", "deactivated"}:
                        action = "REVIEW"
                        result["action"] = "REVIEW"
                        result["reason"] = "Stated NPI issue — sent to review; master not updated"
                    else:
                        lid = f"LNK-UP-{uuid.uuid4().hex[:8]}"
                        state.setdefault("source_links", {})[lid] = {
                            "link_id": lid,
                            "source_record_id": uid,
                            "doctor_id": result["doctor_id"],
                            "link_status": "auto_linked",
                            "decision_basis": "upload_commit",
                            "demo_score": result.get("score"),
                            "review_id": None,
                            "upload_batch_id": batch_id,
                        }
                        rb["link_ids_added"].append(lid)
                        # Late old records: do not replace current golden values
                        continue

                if action in {"REVIEW", "COMPLIANCE_REVIEW", "CREATE_PROVISIONAL", "CREATE_FROM_NPPES", "UNMATCHED"}:
                    rid = f"REV-{uid}"
                    state.setdefault("reviews", {})[rid] = {
                        "review_id": rid,
                        "doctor_id": result.get("doctor_id"),
                        "case_type": {
                            "COMPLIANCE_REVIEW": "compliance_review",
                            "CREATE_PROVISIONAL": "npi_assignment",
                            "CREATE_FROM_NPPES": "npi_assignment",
                            "UNMATCHED": "unmatched",
                        }.get(action, "probable_match"),
                        "title": f"Upload: review {((rec.get('standardized') or {}).get('name') or {}).get('display') or uid}",
                        "severity": "high" if action == "COMPLIANCE_REVIEW" else "medium",
                        "status": "pending",
                        "source_record_id": uid,
                        "candidate_doctor_id": result.get("doctor_id"),
                        "pipeline_action": action,
                        "pipeline_reason": result.get("reason"),
                        "pipeline_score": result.get("score"),
                        "match_score": result.get("score"),
                        "created_at": utc_now_iso(),
                        "updated_at": utc_now_iso(),
                        "version": 1,
                        "assignment_status": "unassigned",
                        "upload_batch_id": batch_id,
                    }
                    rb["review_ids_added"].append(rid)

                if action == "CREATE_FROM_NPPES" and result.get("npi"):
                    did = f"GR-{result['npi']}"
                    if did not in state.get("doctors", {}):
                        state.setdefault("doctors", {})[did] = {
                            "doctor_id": did,
                            "preferred_name": result.get("doctor_name") or result.get("npi"),
                            "official_npi": result.get("npi"),
                            "npi_status": "verified",
                            "badge": "Verified",
                            "identity_status": "resolved",
                            "member_uids": [uid],
                            "sources": [f"upload:{batch_id}"],
                            "updated_at": utc_now_iso(),
                            "version": 1,
                            "open_issue_count": 0,
                        }
                        rb["doctor_ids_added"].append(did)
                if action == "CREATE_PROVISIONAL":
                    did = f"GR-PROV-{uuid.uuid4().hex[:8].upper()}"
                    state.setdefault("doctors", {})[did] = {
                        "doctor_id": did,
                        "preferred_name": ((rec.get("standardized") or {}).get("name") or {}).get("display") or "Provisional",
                        "official_npi": None,
                        "npi_status": "provisional",
                        "badge": "Provisional",
                        "identity_status": "provisional",
                        "member_uids": [uid],
                        "sources": [f"upload:{batch_id}"],
                        "updated_at": utc_now_iso(),
                        "version": 1,
                        "open_issue_count": 0,
                    }
                    rb["doctor_ids_added"].append(did)
                    result["doctor_id"] = did

            # update batch in state list
            for b in state.get("upload_batches") or []:
                if b.get("batch_id") == batch_id:
                    b["committed"] = True
                    b["status"] = "committed"
                    b["updated_at"] = utc_now_iso()
                    b["results"] = batch.get("results")
                    self._set_step(b, "commit", "done")
                    break
            state.setdefault("audit_events", {})[f"AUD-UP-{batch_id}"] = {
                "audit_id": f"AUD-UP-{batch_id}",
                "action": "upload_commit",
                "actor": "Steward",
                "entity_id": batch_id,
                "created_at": utc_now_iso(),
                "detail": f"Committed upload {batch_id}",
            }

        self.repo.runtime.mutate(mutator)
        from app.identity.summary_jobs import refresh_profiles

        touched = {
            result.get("doctor_id")
            for result in (batch.get("results") or [])
            if result.get("doctor_id")
        }
        refresh_profiles(self.repo, touched)
        return self.get_batch(batch_id)

    def rollback(self, batch_id: str) -> Dict[str, Any]:
        batch = self.get_batch(batch_id)
        if not batch.get("committed"):
            raise ValidationAppError("Batch is not committed")

        def mutator(state: Dict[str, Any]) -> None:
            rb = (state.get("upload_rollbacks") or {}).get(batch_id) or {}
            for lid in rb.get("link_ids_added") or []:
                state.get("source_links", {}).pop(lid, None)
            for rid in rb.get("review_ids_added") or []:
                state.get("reviews", {}).pop(rid, None)
            for did in rb.get("doctor_ids_added") or []:
                state.get("doctors", {}).pop(did, None)
            for uid in rb.get("record_ids_added") or []:
                state.get("source_records", {}).pop(uid, None)
            for b in state.get("upload_batches") or []:
                if b.get("batch_id") == batch_id:
                    b["committed"] = False
                    b["status"] = "rolled_back"
                    b["updated_at"] = utc_now_iso()
            state.setdefault("audit_events", {})[f"AUD-RB-{batch_id}"] = {
                "audit_id": f"AUD-RB-{batch_id}",
                "action": "upload_rollback",
                "actor": "Steward",
                "entity_id": batch_id,
                "created_at": utc_now_iso(),
                "detail": f"Rolled back upload {batch_id}; prior links restored",
            }

        self.repo.runtime.mutate(mutator)
        return self.get_batch(batch_id)

    # --- internals ---

    def _save_batch(self, batch: Dict[str, Any]) -> None:
        def mutator(state: Dict[str, Any]) -> None:
            batches = state.setdefault("upload_batches", [])
            for i, b in enumerate(batches):
                if b.get("batch_id") == batch["batch_id"]:
                    batches[i] = batch
                    return
            batches.append(batch)

        self.repo.runtime.mutate(mutator)

    def _set_step(self, batch: Dict[str, Any], key: str, status: str) -> None:
        for step in batch.get("steps") or []:
            if step["key"] == key:
                step["status"] = status
                break
        batch["updated_at"] = utc_now_iso()

    def _check_signature(self, content: bytes, suffix: str) -> Tuple[bool, str]:
        if suffix == ".txt" or suffix == ".csv":
            # reject if binary-looking
            if b"\x00" in content[:1024]:
                return False, "File looks binary; expected text/CSV"
            return True, ""
        if suffix in {".png", ".jpg", ".jpeg", ".pdf", ".xlsx"}:
            head = content[:8]
            if suffix == ".pdf" and not content.startswith(b"%PDF"):
                return False, "PDF signature mismatch"
            if suffix == ".png" and not content.startswith(b"\x89PNG"):
                return False, "PNG signature mismatch"
            if suffix in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
                return False, "JPEG signature mismatch"
            # xlsx is zip — PK
            if suffix == ".xlsx" and not content.startswith(b"PK"):
                return False, "XLSX signature mismatch"
            return True, ""
        if suffix == ".xls":
            return True, ""  # legacy ole — accept with caution
        return True, ""

    def _process_structured(self, batch: Dict[str, Any], content: bytes, suffix: str) -> None:
        self._set_step(batch, "read_extract", "running")
        if suffix == ".csv":
            text = content.decode("utf-8-sig", errors="replace")
            # skip title rows: find first line with multiple commas that looks like headers
            lines = text.splitlines()
            header_idx = 0
            for i, line in enumerate(lines[:10]):
                if line.count(",") >= 2 and not re.match(r"^(total|report|summary)\b", line.strip(), re.I):
                    # blank header cells ok
                    header_idx = i
                    break
            sample = "\n".join(lines[header_idx:])
            reader = csv.DictReader(io.StringIO(sample))
            if not reader.fieldnames:
                raise ValidationAppError("Could not detect CSV headers")
            headers = [((h or "").strip() or f"column_{idx}") for idx, h in enumerate(reader.fieldnames)]
            raw_rows = []
            for row_i, row in enumerate(reader):
                # skip total rows
                joined = " ".join(str(v or "") for v in row.values()).lower()
                if joined.startswith("total") or joined.startswith("grand total"):
                    batch["quarantined_rows"].append({"row": row_i + 2, "reason": "Total row skipped"})
                    continue
                # malformed: too few non-empty
                values = [str(row.get(h) or "") for h in (reader.fieldnames or [])]
                if sum(1 for v in values if v.strip()) == 0:
                    batch["quarantined_rows"].append({"row": row_i + 2, "reason": "Blank row"})
                    continue
                normalized = {headers[i]: values[i] if i < len(values) else "" for i in range(len(headers))}
                raw_rows.append(normalized)
        else:
            # XLSX without executing macros: prefer openpyxl read_only data_only=False values as text
            try:
                from openpyxl import load_workbook  # type: ignore
            except Exception as exc:  # noqa: BLE001
                raise ValidationAppError(f"XLSX support unavailable: {exc}") from exc
            wb = load_workbook(filename=io.BytesIO(content), read_only=True, data_only=False, keep_vba=False)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            header_row = next(rows_iter, None)
            if not header_row:
                raise ValidationAppError("Empty spreadsheet")
            headers = [str(c).strip() if c is not None else f"column_{i}" for i, c in enumerate(header_row)]
            raw_rows = []
            for row_i, row in enumerate(rows_iter):
                values = ["" if c is None else str(c) for c in row]
                if len(values) < len(headers):
                    values += [""] * (len(headers) - len(values))
                if len(values) > len(headers):
                    batch["quarantined_rows"].append({"row": row_i + 2, "reason": "Too many fields"})
                    values = values[: len(headers)]
                if not any(v.strip() for v in values):
                    continue
                raw_rows.append({headers[i]: values[i] for i in range(len(headers))})

        batch["raw_rows"] = raw_rows
        batch["detected_headers"] = list(raw_rows[0].keys()) if raw_rows else headers
        self._set_step(batch, "read_extract", "done")
        self._set_step(batch, "protect", "done")  # structured PHI limited

        mapping, confidence, missing = self._suggest_mapping(batch["detected_headers"])
        batch["mapping"] = mapping
        batch["mapping_confidence"] = confidence
        batch["missing_required"] = missing
        batch["status"] = "awaiting_confirm"
        self._set_step(batch, "map_fields", "running")
        if missing and "name" in missing:
            # still allow user confirm; do not auto-reject until confirm
            pass

    def _suggest_mapping(self, headers: List[str]) -> Tuple[Dict[str, str], float, List[str]]:
        mapping: Dict[str, str] = {}
        lower = {h: h.lower().strip() for h in headers}
        for canonical, aliases in HEADER_ALIASES.items():
            for h, hl in lower.items():
                if hl in aliases or hl.replace(" ", "_") in aliases:
                    mapping[h] = canonical
                    break
        # confidence
        hits = len(mapping)
        confidence = min(1.0, hits / max(3, len(HEADER_ALIASES) // 3))
        missing = []
        vals = set(mapping.values())
        if "full_name" not in vals and not ("first_name" in vals and "last_name" in vals):
            missing.append("name")
        return mapping, round(confidence, 2), missing

    def _rows_to_records(
        self, raw_rows: List[Dict[str, str]], mapping: Dict[str, str], batch_id: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        records = []
        quarantined = []
        for idx, raw in enumerate(raw_rows):
            try:
                mapped = {canonical: raw.get(src, "") for src, canonical in mapping.items()}
                # build name
                if mapped.get("full_name"):
                    name_raw = mapped["full_name"]
                else:
                    name_raw = f"{mapped.get('first_name', '')} {mapped.get('last_name', '')}".strip()
                synth = {
                    "Account_Name": name_raw,
                    "NPI_vod": mapped.get("npi", ""),
                    "Specialty": mapped.get("specialty", ""),
                    "Primary_Parent": mapped.get("organization", ""),
                    "City": mapped.get("city", ""),
                    "St": mapped.get("state", ""),
                    "Phone": mapped.get("phone", ""),
                    "Email": mapped.get("email", ""),
                    "Address": mapped.get("address", ""),
                    "State_License": mapped.get("license", ""),
                    "amount_usd": mapped.get("amount", ""),
                    "payment_date": mapped.get("date", ""),
                }
                std = standardize_record(
                    synth,
                    source_key="crm",
                    profile_flags={"name_fields": ["Account_Name"], "venue_is_not_practice": False},
                )
                npi_info = classify_npi(mapped.get("npi"))
                uid = f"upload:{batch_id}:{idx}"
                records.append({
                    "uid": uid,
                    "record_id": uid,
                    "source_key": "upload",
                    "trust": 0.5,
                    "raw": {**raw, **synth},
                    "standardized": std,
                    "npi_fields": [{"field": "npi", **npi_info}] if npi_info.get("raw") or npi_info.get("digits") else [],
                    "payment_source": bool(mapped.get("amount")),
                    "requires_compliance_review": bool(mapped.get("amount")),
                })
            except Exception as exc:  # noqa: BLE001
                quarantined.append({"row": idx + 1, "reason": str(exc)})
        return records, quarantined

    def _process_document(self, batch: Dict[str, Any], content: bytes, suffix: str) -> None:
        self._set_step(batch, "read_extract", "running")
        text = ""
        if suffix == ".txt":
            text = content.decode("utf-8", errors="replace")
        elif suffix == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore

                reader = PdfReader(io.BytesIO(content))
                text = "\n".join((page.extract_text() or "") for page in reader.pages)
            except Exception:
                text = ""
            if not text.strip():
                batch["errors"].append("Could not extract text from this PDF (may be scanned). OCR not available.")
                raise ValidationAppError("Scanned or unreadable PDF — text could not be extracted")
        else:
            # images: do not send to LLM by default
            if not self.settings.upload_allow_llm_images:
                raise ValidationAppError(
                    "Image uploads require local OCR; LLM image input is disabled. Convert to PDF/TXT or enable OCR."
                )
            raise ValidationAppError("Image OCR is not configured in this environment")

        self._set_step(batch, "read_extract", "done")
        self._set_step(batch, "protect", "running")
        redacted, counts = redact_text(text)
        batch["redacted_text"] = redacted
        batch["redaction_counts"] = counts
        self._set_step(batch, "protect", "done")

        # Rule-based extract (LLM optional)
        extracted = self._rule_extract(redacted)
        batch["extracted"] = extracted
        batch["status"] = "awaiting_confirm"
        self._set_step(batch, "map_fields", "running")
        batch["llm_used"] = False
        batch["llm_note"] = "Rule-based extraction shown for confirmation. LLM used only when configured; never sends patient tokens."

    def _rule_extract(self, text: str) -> Dict[str, Any]:
        npi_match = re.search(r"\b(\d{10})\b", text)
        name_match = re.search(r"\bDr\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z\-]+)+)", text)
        amount_match = re.search(r"\$?\s*(\d{2,5}(?:\.\d{2})?)", text)
        quote = (text.strip().splitlines() or [""])[0][:240]
        return {
            "document_type": "unknown",
            "doctor_name": name_match.group(0) if name_match else None,
            "stated_npi": npi_match.group(1) if npi_match else None,
            "billing_npi": None,
            "organization": None,
            "address": None,
            "phone": None,
            "license": None,
            "specialty": None,
            "service_or_event_date": None,
            "product_code": None,
            "amount": amount_match.group(1) if amount_match else None,
            "source_quote": quote if quote in text else None,
            "confidence": {"doctor_name": 0.4 if name_match else 0.0, "stated_npi": 0.5 if npi_match else 0.0},
        }

    def _extracted_to_record(self, extracted: Dict[str, Any], batch_id: str) -> Dict[str, Any]:
        name = extracted.get("doctor_name") or ""
        synth = {
            "Account_Name": name,
            "NPI_vod": extracted.get("stated_npi") or "",
            "Specialty": extracted.get("specialty") or "",
            "Primary_Parent": extracted.get("organization") or "",
            "Address": extracted.get("address") or "",
            "Phone": extracted.get("phone") or "",
            "State_License": extracted.get("license") or "",
            "amount_usd": extracted.get("amount") or "",
        }
        std = standardize_record(
            synth,
            source_key="crm",
            profile_flags={"name_fields": ["Account_Name"], "venue_is_not_practice": False},
        )
        npi_info = classify_npi(extracted.get("stated_npi"))
        uid = f"upload:{batch_id}:0"
        return {
            "uid": uid,
            "record_id": uid,
            "source_key": "upload",
            "trust": 0.45,
            "raw": synth,
            "standardized": std,
            "npi_fields": [{"field": "npi", **npi_info}] if npi_info.get("raw") or npi_info.get("digits") else [],
            "payment_source": bool(extracted.get("amount")),
            "requires_compliance_review": bool(extracted.get("amount")),
        }

    def _match_records(self, batch: Dict[str, Any]) -> None:
        self._set_step(batch, "standardize", "done")
        self._set_step(batch, "npi_check", "running")
        doctors = self.repo.list_doctors()
        # Build lightweight NPPES index from doctors with NPIs + pipeline nppes if available
        nppes_keys = set(self.repo.state().get("nppes_index_keys") or [])
        # Prefer matching against golden masters
        results = []
        action_counts: Dict[str, int] = {}
        # Deduplicate new person within batch by name+zip
        provisional_index: Dict[str, str] = {}

        for rec in batch.get("records") or []:
            rec["record_flags"] = record_level_flags(rec)
            stated = None
            stated_status = "missing"
            for nf in rec.get("npi_fields") or []:
                if nf.get("digits"):
                    stated = nf["digits"]
                    stated_status = nf.get("status") or "unknown"
                    break

            # Score against goldens
            candidates = []
            for doc in doctors:
                # synthetic right side from doctor
                right = {
                    "npi": doc.get("official_npi"),
                    "name": {
                        "display": doc.get("preferred_name"),
                        "first_norm": (doc.get("given_name") or "").lower(),
                        "last_norm": (doc.get("family_name") or "").lower().replace("-", ""),
                        "last_parts": [],
                        "credentials": [],
                        "suffixes": [],
                        "is_non_person": False,
                    },
                    "other_last": "",
                    "organization": ((doc.get("primary_affiliation") or {}) if False else None),
                    "city": doc.get("city") or "",
                    "state": doc.get("state") or "",
                    "postal": "",
                    "phone": doc.get("professional_phone") or "",
                    "specialty": doc.get("specialty") or "",
                    "license_no": "",
                    "license_state": "",
                    "entity_type": "1",
                }
                # use aliases
                scored = score_pair(
                    rec,
                    {
                        "standardized": {
                            "name": right["name"],
                            "other_last": "",
                            "organization": "",
                            "city": right["city"],
                            "state": right["state"],
                            "postal": "",
                            "zip3": "",
                            "phone": right["phone"] or "",
                            "email": doc.get("professional_email") or "",
                            "specialty": right["specialty"] or "",
                            "license_no": "",
                            "license_state": "",
                        },
                        "npi_fields": (
                            [{"field": "npi", "digits": doc["official_npi"], "valid": True, "status": "valid"}]
                            if doc.get("official_npi")
                            else []
                        ),
                    },
                    right_is_nppes=False,
                )
                hard = []
                if stated and doc.get("official_npi") and stated != doc.get("official_npi") and classify_npi(stated).get("valid"):
                    hard.append({"code": "NPI_CONFLICT", "message": "Stated NPI differs from master NPI"})
                candidates.append({
                    "doctor_id": doc["doctor_id"],
                    "doctor_name": doc.get("preferred_name"),
                    "npi": doc.get("official_npi"),
                    "score": scored["score"],
                    "contributions": scored["contributions"],
                    "hard_stops": hard,
                })
            candidates.sort(key=lambda c: c["score"], reverse=True)
            best = candidates[0] if candidates else None

            self._set_step(batch, "npi_check", "done")
            self._set_step(batch, "match", "done")

            action = "UNMATCHED"
            reason = "Evidence too weak"
            doctor_id = None
            npi = stated
            score = best["score"] if best else 0.0

            if rec.get("payment_source") or rec.get("requires_compliance_review"):
                action = "COMPLIANCE_REVIEW"
                reason = "Payment/transparency record — compliance must approve any correction"
                doctor_id = best["doctor_id"] if best and best["score"] >= 0.7 else None
            elif stated_status in {"luhn_fail", "invalid_format", "placeholder"}:
                action = "REVIEW"
                reason = f"Stated NPI status: {stated_status}"
                doctor_id = best["doctor_id"] if best else None
            elif best and best["hard_stops"]:
                action = "REVIEW"
                reason = best["hard_stops"][0]["message"]
                doctor_id = best["doctor_id"]
            elif best and best["score"] >= 0.95:
                action = "LINK"
                reason = f"High-confidence match to {best['doctor_name']}"
                doctor_id = best["doctor_id"]
                npi = best.get("npi") or stated
            elif best and best["score"] >= 0.70:
                action = "REVIEW"
                reason = "Probable match — needs human review"
                doctor_id = best["doctor_id"]
            elif stated and classify_npi(stated).get("valid"):
                # in NPPES sense — if any golden has it or key present
                action = "CREATE_FROM_NPPES"
                reason = "Valid NPI present; create or attach master from NPPES"
                npi = stated
                # batch dedupe
                key = stated
                if key in provisional_index:
                    doctor_id = provisional_index[key]
                    action = "LINK"
                    reason = "Same new person already in this batch — single master"
                else:
                    provisional_index[key] = f"GR-{stated}"
            else:
                # provisional person
                std = rec.get("standardized") or {}
                name = ((std.get("name") or {}).get("display") or "").lower()
                key = f"{name}|{std.get('zip3') or std.get('state')}"
                if key in provisional_index:
                    doctor_id = provisional_index[key]
                    action = "LINK"
                    reason = "Same new person already in this batch — single provisional master"
                else:
                    action = "CREATE_PROVISIONAL"
                    reason = "Person not in master or clear NPPES hit"
                    provisional_index[key] = f"pending:{key}"

            action_counts[action] = action_counts.get(action, 0) + 1
            results.append({
                "record": rec,
                "action": action,
                "reason": reason,
                "doctor_id": doctor_id,
                "doctor_name": next((c["doctor_name"] for c in candidates if c["doctor_id"] == doctor_id), None),
                "npi": npi,
                "stated_npi": stated,
                "stated_npi_status": stated_status,
                "score": score,
                "candidates": candidates[:5],
                "conflicts": (best or {}).get("hard_stops") or [],
            })

        batch["results"] = results
        batch["action_counts"] = action_counts
        batch["status"] = "matched"
        self._set_step(batch, "route", "done")
        self._set_step(batch, "review_results", "done")
