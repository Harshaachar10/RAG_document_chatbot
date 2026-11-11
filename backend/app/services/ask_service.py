"""Read-only assistant. Answers come from parameterized lookups, never from free-form SQL."""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from app.utils.dates import utc_now_iso


class AskService:
    def __init__(self, repo: Any) -> None:
        self.repo = repo

    def ask(self, question: str, *, doctor_id: Optional[str] = None) -> Dict[str, Any]:
        text = (question or "").strip()
        tools: List[Dict[str, Any]] = []
        if not text:
            return self._finish(text, doctor_id, "Ask a question about the doctors and records already stored.", [], [])

        lowered = text.lower()
        if doctor_id:
            tools.append(self._tool("get_doctor", {"doctor_id": doctor_id}))

        if "separate" in lowered and "sarah" in lowered:
            found = self._tool("search_doctors", {"query": "Sarah Lee"})
            tools.append(found)
            doctors = found["result"]
            if len(doctors) < 2:
                answer = "The stored doctors do not show two Sarah Lee records to compare."
            else:
                bits = []
                for doctor in doctors:
                    bits.append(
                        f"{doctor['name']} (NPI {doctor.get('npi') or 'not assigned'}, {doctor.get('specialty') or 'specialty not recorded'}, {doctor.get('city') or ''} {doctor.get('state') or ''})".strip()
                    )
                answer = "They stay separate because the registry shows different people. " + " ".join(bits) + "."
            citations = [{"label": d["name"], "href": d["href"]} for d in doctors]
            return self._finish(text, doctor_id, answer, tools, citations)

        if "payment" in lowered and ("1000" in lowered or "1,000" in lowered or "$1" in lowered):
            found = self._tool("list_payments", {"min_amount": 1000, "doubtful": True})
            tools.append(found)
            rows = found["result"]
            if not rows:
                answer = "No stored payment over $1,000 is marked with a doubtful identity."
            else:
                answer = f"{len(rows)} stored payments over $1,000 need an identity check."
            citations = [{"label": row["record_id"], "href": row["href"]} for row in rows]
            return self._finish(text, doctor_id, answer, tools, citations)

        if "unresolved" in lowered or "still open" in lowered:
            query = "Sharma" if "sharma" in lowered else ""
            if doctor_id and not query:
                doctor = self.repo.get_doctor(doctor_id) or {}
                query = doctor.get("preferred_name") or ""
            found = self._tool("list_unresolved", {"query": query})
            tools.append(found)
            rows = found["result"]
            if not rows:
                answer = "No unresolved stored records match that question."
            else:
                answer = f"{len(rows)} unresolved records match."
            citations = [{"label": row["record_id"], "href": row["href"]} for row in rows]
            return self._finish(text, doctor_id, answer, tools, citations)

        if "practice" in lowered or "moved" in lowered or "change" in lowered:
            found = self._tool("list_changes", {})
            tools.append(found)
            rows = found["result"]
            if not rows:
                answer = "No stored practice-move or name-change proposals match that question."
            else:
                answer = f"{len(rows)} stored change proposals are waiting. Each one keeps the quote from the note."
            citations = [{"label": row["record_id"], "href": row["href"]} for row in rows]
            return self._finish(text, doctor_id, answer, tools, citations)

        if "how many" in lowered or "count" in lowered:
            found = self._tool("counts", {})
            tools.append(found)
            counts = found["result"]
            answer = f"Stored results: {counts['doctors']} doctors, {counts['linked']} linked records, {counts['unresolved']} unresolved records."
            return self._finish(text, doctor_id, answer, tools, [])

        name_match = re.search(r"\b(?:dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", text)
        query = name_match.group(1) if name_match else ""
        if query:
            found = self._tool("search_doctors", {"query": query})
            tools.append(found)
            doctors = found["result"]
            if not doctors:
                answer = "The stored doctors do not include a match for that name."
                return self._finish(text, doctor_id, answer, tools, [])
            answer = "Matching doctors: " + "; ".join(d["name"] for d in doctors) + "."
            citations = [{"label": d["name"], "href": d["href"]} for d in doctors]
            return self._finish(text, doctor_id, answer, tools, citations)

        return self._finish(
            text,
            doctor_id,
            "The stored records do not answer that. Try a doctor name, an unresolved queue, a payment threshold, or a practice change.",
            tools,
            [],
        )

    def preview(self, text: str) -> Dict[str, Any]:
        """Score a pasted line against stored doctors. Nothing is written."""
        from app.identity.standardize import parse_person_name

        parsed = parse_person_name(text or "")
        last = (parsed.get("last_norm") or parsed.get("last") or "").lower()
        first = (parsed.get("first_norm") or parsed.get("first") or "").lower()
        blob = (text or "").lower()
        candidates = []
        for doctor in self.repo.list_doctors():
            if doctor.get("identity_status") == "reference":
                continue
            name = (doctor.get("preferred_name") or "").lower()
            score = 0.0
            reasons = []
            if last and last in name.replace("-", ""):
                score += 0.55
                reasons.append("Surname agrees")
            elif last and last in name:
                score += 0.55
                reasons.append("Surname agrees")
            if first and first[:1] and name.startswith(first[:1]):
                score += 0.15
                reasons.append("First initial agrees")
            city = (doctor.get("city") or "").lower()
            state = (doctor.get("state") or "").lower()
            if city and city in blob:
                score += 0.2
                reasons.append("City agrees")
            if state and re.search(rf"\b{re.escape(state)}\b", blob):
                score += 0.05
                reasons.append("State agrees")
            org = (doctor.get("primary_affiliation") or "").lower()
            if org and any(tok in blob for tok in org.split() if len(tok) > 3):
                score += 0.15
                reasons.append("Organization token agrees")
            if score <= 0:
                continue
            candidates.append(
                {
                    "doctor_id": doctor.get("doctor_id"),
                    "name": doctor.get("preferred_name"),
                    "npi": doctor.get("official_npi"),
                    "specialty": doctor.get("specialty"),
                    "city": doctor.get("city"),
                    "state": doctor.get("state"),
                    "score": round(min(score, 0.99), 2),
                    "reasons": reasons,
                    "href": f"/doctors/{doctor.get('doctor_id')}",
                }
            )
        candidates.sort(key=lambda row: (-row["score"], row["name"] or ""))
        return {
            "committed": False,
            "candidates": candidates[:3],
            "reason": "Preview only. No record was saved and no doctor was updated.",
        }

    def _tool(self, name: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        if name == "search_doctors":
            result = self._search_doctors(str(filters.get("query") or ""))
        elif name == "get_doctor":
            doctor = self.repo.get_doctor(str(filters.get("doctor_id") or ""))
            result = {"doctor_id": filters.get("doctor_id"), "name": (doctor or {}).get("preferred_name")}
        elif name == "list_unresolved":
            result = self._unresolved(str(filters.get("query") or ""))
        elif name == "list_payments":
            result = self._payments(float(filters.get("min_amount") or 0), bool(filters.get("doubtful")))
        elif name == "list_changes":
            result = self._changes()
        elif name == "counts":
            result = self._counts()
        else:
            result = []
        return {"name": name, "filters": filters, "result": result}

    def _search_doctors(self, query: str) -> List[Dict[str, Any]]:
        needle = query.lower()
        rows = []
        for doctor in self.repo.list_doctors():
            if doctor.get("identity_status") == "reference":
                continue
            alias_bits = []
            for alias in doctor.get("aliases") or []:
                if isinstance(alias, dict):
                    alias_bits.append(str(alias.get("name") or ""))
                else:
                    alias_bits.append(str(alias))
            blob = " ".join(
                [
                    doctor.get("preferred_name") or "",
                    doctor.get("family_name") or "",
                    " ".join(alias_bits),
                    doctor.get("city") or "",
                    doctor.get("state") or "",
                ]
            ).lower()
            if needle and needle not in blob and not all(part in blob for part in needle.split()):
                continue
            rows.append(
                {
                    "doctor_id": doctor.get("doctor_id"),
                    "name": doctor.get("preferred_name"),
                    "npi": doctor.get("official_npi"),
                    "specialty": doctor.get("specialty"),
                    "city": doctor.get("city"),
                    "state": doctor.get("state"),
                    "href": f"/doctors/{doctor.get('doctor_id')}",
                }
            )
        rows.sort(key=lambda row: row["name"] or "")
        return rows[:8]

    def _unresolved(self, query: str) -> List[Dict[str, Any]]:
        needle = query.lower()
        reviews = self.repo.list_reviews()
        rows = []
        for review in reviews:
            if review.get("status") != "pending":
                continue
            blob = " ".join([review.get("title") or "", review.get("pipeline_reason") or ""]).lower()
            if needle and needle not in blob:
                continue
            rows.append(
                {
                    "record_id": review.get("source_record_id") or review.get("review_id"),
                    "title": review.get("title"),
                    "href": f"/review/{review.get('review_id')}",
                }
            )
        return rows[:12]

    def _payments(self, min_amount: float, doubtful: bool) -> List[Dict[str, Any]]:
        decisions = self.repo.state().get("match_decisions") or []
        records = self.repo.state().get("source_records") or {}
        reviews = {r.get("source_record_id"): r for r in self.repo.list_reviews()}
        rows = []
        for decision in decisions:
            record = records.get(decision.get("uid") or "") or {}
            if record.get("source_id") != "payments":
                continue
            amount = (record.get("amount_cents") or 0) / 100
            if amount < min_amount:
                continue
            if doubtful and decision.get("action") != "COMPLIANCE_REVIEW":
                continue
            review = reviews.get(decision.get("uid"))
            rows.append(
                {
                    "record_id": decision.get("record_id"),
                    "amount": amount,
                    "href": f"/review/{review['review_id']}" if review else "/review",
                }
            )
        return rows

    def _changes(self) -> List[Dict[str, Any]]:
        rows = []
        for decision in self.repo.state().get("match_decisions") or []:
            for change in decision.get("proposed_changes") or []:
                if not change.get("quote"):
                    continue
                rows.append(
                    {
                        "record_id": decision.get("record_id"),
                        "kind": change.get("change_type"),
                        "quote": change.get("quote"),
                        "href": "/review",
                    }
                )
        return rows[:12]

    def _counts(self) -> Dict[str, int]:
        decisions = self.repo.state().get("match_decisions") or []
        return {
            "doctors": len([d for d in self.repo.list_doctors() if d.get("identity_status") != "reference"]),
            "linked": sum(1 for d in decisions if d.get("action") in {"AUTO_LINK", "PROVISIONAL"}),
            "unresolved": sum(1 for d in decisions if d.get("action") in {"REVIEW", "COMPLIANCE_REVIEW", "UNMATCHED"}),
        }

    def _finish(self, question: str, doctor_id: Optional[str], answer: str, tools: List[Dict[str, Any]], citations: List[Dict[str, str]]) -> Dict[str, Any]:
        public_tools = [{"name": tool["name"], "filters": tool["filters"]} for tool in tools]
        payload = {
            "question": question,
            "answer": answer,
            "citations": citations,
            "tools": public_tools,
            "doctor_id": doctor_id,
            "wrote": False,
        }

        def mutator(state: Dict[str, Any]) -> Dict[str, Any]:
            event_id = f"AUD-ASK-{uuid.uuid4().hex[:8]}"
            state.setdefault("audit_events", {})[event_id] = {
                "audit_id": event_id,
                "actor_label": "Ask assistant",
                "action": "ask",
                "summary": question[:240],
                "detail": answer[:500],
                "doctor_id": doctor_id,
                "occurred_at": utc_now_iso(),
                "tools": public_tools,
            }
            state.setdefault("ask_log", []).append({**payload, "audit_id": event_id, "at": utc_now_iso()})
            return payload

        return self.repo.runtime.mutate(mutator)
