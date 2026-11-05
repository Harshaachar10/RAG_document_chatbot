from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.identity.config import MatchThresholds


def route_decision(
    *,
    score: float,
    hard_stops: List[Dict[str, str]],
    record_flags: List[Dict[str, str]],
    candidates: List[Dict[str, Any]],
    thresholds: Optional[MatchThresholds] = None,
    payment_source: bool = False,
    has_valid_npi_match: bool = False,
    npi_only_assignable: bool = False,
) -> Dict[str, Any]:
    """
    Decide action for a source record given scored candidates (best-first).
    Actions: AUTO_LINK | ASSIGN_NPI | REVIEW | COMPLIANCE_REVIEW | REJECT | DEDUPE_REVIEW | NOT_A_PERSON
    """
    thresholds = thresholds or MatchThresholds()
    flag_codes = {f["code"] for f in record_flags}
    stop_codes = {s["code"] for s in hard_stops}

    if "NOT_A_PERSON" in flag_codes or "NOT_A_PERSON" in stop_codes:
        return {
            "action": "NOT_A_PERSON",
            "queue": "data_quality",
            "reason": "Record appears to be non-person / office staff",
            "auto": True,
        }

    if payment_source or "COMPLIANCE_REVIEW" in flag_codes:
        return {
            "action": "COMPLIANCE_REVIEW",
            "queue": "compliance",
            "reason": "Payment/transparency record requires compliance review before link",
            "auto": False,
        }

    if hard_stops:
        return {
            "action": "REVIEW",
            "queue": "hard_stop",
            "reason": "; ".join(s["message"] for s in hard_stops),
            "auto": False,
        }

    if not candidates:
        if npi_only_assignable:
            return {
                "action": "ASSIGN_NPI",
                "queue": "npi_assignment",
                "reason": "No match candidates; eligible for new NPI assignment review",
                "auto": False,
            }
        return {
            "action": "REVIEW",
            "queue": "no_match",
            "reason": "No blocking candidates found",
            "auto": False,
        }

    # Prefer NPPES targets when choosing the "best" for routing.
    npi_cands = [c for c in candidates if str(c.get("target_id") or "").startswith("npi:")]
    best = (npi_cands[0] if npi_cands else candidates[0])
    # Margin is vs next distinct identity (different target_id)
    rivals = [c for c in candidates if c.get("target_id") != best.get("target_id")]
    second = rivals[0] if rivals else None
    best_score = float(best.get("score") or 0)
    second_score = float(second.get("score") or 0) if second else 0.0
    margin = best_score - second_score

    # Strong path: clear NPPES hit
    if str(best.get("target_id") or "").startswith("npi:") and best_score >= thresholds.auto_link:
        # Only treat as ambiguous if another *different NPI* is also very close
        other_npi = next(
            (
                c
                for c in rivals
                if str(c.get("target_id") or "").startswith("npi:")
                and float(c.get("score") or 0) >= thresholds.auto_link
                and (best_score - float(c.get("score") or 0)) < thresholds.clear_winner_margin
            ),
            None,
        )
        if other_npi:
            return {
                "action": "REVIEW",
                "queue": "ambiguous_top",
                "reason": f"Multiple NPPES candidates near score {best_score:.2f}",
                "auto": False,
                "target_id": best.get("target_id"),
            }
        return {
            "action": "AUTO_LINK",
            "queue": None,
            "reason": f"NPPES match score {best_score:.2f}",
            "auto": True,
            "target_id": best.get("target_id"),
        }

    # Near-duplicate source rows (same source system, near-equal scores)
    if (
        second
        and margin < 0.02
        and best_score >= 0.95
        and best.get("target_source")
        and best.get("target_source") == second.get("target_source")
        and not str(best.get("target_id") or "").startswith("npi:")
    ):
        return {
            "action": "DEDUPE_REVIEW",
            "queue": "dedupe",
            "reason": "Near-duplicate rows in the same source",
            "auto": False,
        }

    if best_score >= thresholds.auto_link and margin >= thresholds.clear_winner_margin:
        if has_valid_npi_match or str(best.get("target_id") or "").startswith("npi:"):
            return {
                "action": "AUTO_LINK",
                "queue": None,
                "reason": f"Score {best_score:.2f} with clear margin {margin:.2f}",
                "auto": True,
                "target_id": best.get("target_id"),
            }
        return {
            "action": "REVIEW",
            "queue": "high_score_no_npi",
            "reason": "High score but no confirmed NPI target",
            "auto": False,
            "target_id": best.get("target_id"),
        }

    if best_score >= thresholds.auto_link and margin < thresholds.clear_winner_margin:
        return {
            "action": "REVIEW",
            "queue": "ambiguous_top",
            "reason": f"Top score {best_score:.2f} but margin {margin:.2f} below clear-winner threshold",
            "auto": False,
            "target_id": best.get("target_id"),
        }

    if best_score >= thresholds.review_low:
        return {
            "action": "REVIEW",
            "queue": "probable_match",
            "reason": f"Probable match score {best_score:.2f} — needs human review",
            "auto": False,
            "target_id": best.get("target_id"),
        }

    return {
        "action": "REVIEW",
        "queue": "low_score",
        "reason": f"Best score {best_score:.2f} below review threshold",
        "auto": False,
        "target_id": best.get("target_id"),
    }
