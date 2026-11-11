from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.filtering import matches_search, paginate, sort_items

AE_PATTERNS = [
    re.compile(r"\badverse\s+event\b", re.I),
    re.compile(r"\bserious\s+adverse\b", re.I),
    re.compile(r"\bhospitali[sz]ed\b", re.I),
    re.compile(r"\bdeath\b", re.I),
    re.compile(r"\banaphylax", re.I),
]


class NotesService:
    def __init__(self, repo: Any) -> None:
        self.repo = repo

    def list_insights(
        self,
        *,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        doctors = list(self.repo.list_doctors())
        notes = self.repo.state().get("notes") or []
        # Also include note source records
        note_records = [r for r in self.repo.list_source_records() if r.get("source_id") == "notes"]
        by_uid = {n.get("uid"): n for n in notes}
        items: List[Dict[str, Any]] = []
        for rec in note_records:
            meta = by_uid.get(rec["source_record_id"]) or {}
            text = meta.get("redacted_note") or rec.get("note_text") or ""
            mention = self._guess_doctor_mention(text, doctors)
            decision = next(
                (
                    row for row in (self.repo.state().get("match_decisions") or [])
                    if row.get("record_id") == rec.get("source_record_id") or row.get("uid") == rec.get("source_record_id")
                ),
                {},
            )
            safety = decision.get("safety") or {}
            ae_flags = [safety.get("reason")] if safety.get("flagged") else [p.pattern for p in AE_PATTERNS if p.search(text)]
            quote = self._first_sentence(text)
            items.append({
                "note_id": rec.get("original_transaction_id") or rec["source_record_id"],
                "source_record_id": rec["source_record_id"],
                "note_date": rec.get("record_date") or meta.get("note_date"),
                "redacted_note": text,
                "doctor_mention": mention.get("mention"),
                "resolved_doctor_id": mention.get("doctor_id"),
                "resolved_doctor_name": mention.get("doctor_name"),
                "proposed_change": mention.get("proposed_change"),
                "quoted_sentence": quote,
                "review_status": rec.get("resolution_status") or "informational",
                "adverse_event_flags": ae_flags,
                "redaction_counts": meta.get("redaction_counts") or {},
                "safety_note": "Adverse-event flags are never silently removed.",
            })
        if search:
            items = [i for i in items if matches_search(" ".join(str(v or "") for v in i.values()), search)]
        items = sort_items(items, "note_date", "desc", {"note_date", "note_id"}, "note_id")
        page_items, total = paginate(items, page, page_size)
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "snapshot_version": self.repo.snapshot_version(),
        }

    def _first_sentence(self, text: str) -> str:
        if not text:
            return ""
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return parts[0][:280] if parts else text[:280]

    def _guess_doctor_mention(self, text: str, doctors: List[Dict[str, Any]]) -> Dict[str, Any]:
        low = (text or "").lower()
        for d in doctors:
            name = (d.get("preferred_name") or "").strip()
            if not name or len(name) < 4:
                continue
            # try last name
            family = (d.get("family_name") or name.split()[-1]).lower()
            if family and family in low:
                proposed = None
                if "now at" in low or "moved" in low or "joined" in low:
                    proposed = "Possible affiliation or location change"
                if "formerly" in low or "aka" in low or "née" in low:
                    proposed = "Possible name / alias update"
                return {
                    "mention": name,
                    "doctor_id": d.get("doctor_id"),
                    "doctor_name": name,
                    "proposed_change": proposed,
                }
        # free-text Dr. X pattern
        m = re.search(r"\bDr\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z\-]+)?)", text or "")
        if m:
            return {"mention": m.group(0), "doctor_id": None, "doctor_name": None, "proposed_change": "Unresolved doctor mention"}
        return {"mention": None, "doctor_id": None, "doctor_name": None, "proposed_change": None}
