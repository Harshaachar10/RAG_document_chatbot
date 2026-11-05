from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.identity.config import FIELD_WEIGHTS


def _name_agreement(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    na, nb = a.get("name") or {}, b.get("name") or {}
    score = 0.0
    fa, fb = na.get("first_norm") or "", nb.get("first_norm") or ""
    la, lb = na.get("last_norm") or "", nb.get("last_norm") or ""
    la_parts = set(na.get("last_parts") or [])
    lb_parts = set(nb.get("last_parts") or [])
    other_a = a.get("other_last") or ""
    other_b = b.get("other_last") or ""

    last_match = False
    if la and lb and la == lb:
        last_match = True
        reasons.append("last_exact")
    elif la and (la in lb_parts or la == other_b):
        last_match = True
        reasons.append("last_aka_or_hyphen")
    elif lb and (lb in la_parts or lb == other_a):
        last_match = True
        reasons.append("last_aka_or_hyphen")
    elif la and lb and (la.startswith(lb) or lb.startswith(la)) and min(len(la), len(lb)) >= 3:
        last_match = True
        score += 0.5
        reasons.append("last_prefix")

    first_match = False
    if fa and fb and fa == fb:
        first_match = True
        reasons.append("first_exact")
    elif fa and fb and fa[:1] == fb[:1]:
        first_match = True
        score += 0.35
        reasons.append("first_initial")
    elif fa and fb and (fa.startswith(fb) or fb.startswith(fa)):
        first_match = True
        score += 0.55
        reasons.append("first_prefix")

    if last_match and first_match and "last_exact" in reasons and "first_exact" in reasons:
        score = 1.0
    elif last_match and first_match:
        score = max(score, 0.75)
    elif last_match:
        score = max(score, 0.4)
    elif first_match:
        score = max(score, 0.2)

    # former name boost
    if other_a or other_b:
        if (other_a and other_a == lb) or (other_b and other_b == la):
            score = max(score, 0.85)
            reasons.append("former_name")

    return min(score, 1.0), reasons


def _field_agree(a_val: str, b_val: str) -> Optional[bool]:
    if not a_val or not b_val:
        return None
    return a_val == b_val


def score_pair(
    left: Dict[str, Any],
    right: Dict[str, Any],
    *,
    right_is_nppes: bool = False,
) -> Dict[str, Any]:
    """
    Explainable weighted score in [0, 1].
    `left` is always a source record; `right` is source record or synthetic NPPES dict.
    """
    a = left.get("standardized") or left
    if right_is_nppes:
        b = {
            "name": right.get("name") or {},
            "other_last": right.get("other_last") or "",
            "organization": right.get("organization") or "",
            "city": right.get("city") or "",
            "state": right.get("state") or "",
            "postal": right.get("postal") or "",
            "zip3": (right.get("postal") or "")[:3],
            "phone": right.get("phone") or "",
            "email": "",
            "specialty": right.get("specialty") or "",
            "license_no": right.get("license_no") or "",
            "license_state": right.get("license_state") or "",
        }
        right_npis = {right.get("npi")} if right.get("npi") else set()
    else:
        b = right.get("standardized") or right
        right_npis = {nf["digits"] for nf in (right.get("npi_fields") or []) if nf.get("valid")}

    left_npis = {nf["digits"] for nf in (left.get("npi_fields") or []) if nf.get("valid")}

    contributions: List[Dict[str, Any]] = []
    weighted = 0.0
    weight_sum = 0.0

    def add(field: str, agree: Optional[bool], detail: str = "", strength: float = 1.0) -> None:
        nonlocal weighted, weight_sum
        w = FIELD_WEIGHTS.get(field, 0.05) * strength
        if agree is None:
            contributions.append({"field": field, "status": "missing", "detail": detail, "delta": 0.0})
            return
        weight_sum += w
        if agree:
            weighted += w
            contributions.append({"field": field, "status": "agree", "detail": detail, "delta": round(w, 4)})
        else:
            # mild disagreement penalty (except hard-stop fields handled elsewhere)
            weighted -= w * 0.35
            contributions.append({"field": field, "status": "disagree", "detail": detail, "delta": round(-w * 0.35, 4)})

    # NPI
    if left_npis and right_npis:
        overlap = left_npis & right_npis
        add("npi", bool(overlap), "shared valid NPI" if overlap else "different valid NPIs")
    elif left_npis or right_npis:
        add("npi", None, "one side missing valid NPI")
    else:
        add("npi", None, "both missing NPI")

    name_score, name_reasons = _name_agreement(a, b)
    if name_score >= 0.9:
        add("name", True, ",".join(name_reasons))
    elif name_score >= 0.5:
        add("name", True, ",".join(name_reasons), strength=name_score)
    elif name_score > 0:
        add("name", True, ",".join(name_reasons), strength=name_score * 0.6)
    elif (a.get("name") or {}).get("last_norm") or (b.get("name") or {}).get("last_norm"):
        add("name", False, "name mismatch")
    else:
        add("name", None, "name missing")

    if "former_name" in name_reasons:
        add("former_name", True, "other/former last name")

    # suffix
    sa = set((a.get("name") or {}).get("suffixes") or [])
    sb = set((b.get("name") or {}).get("suffixes") or [])
    if sa and sb:
        add("suffix", bool(sa & sb), f"{sa} vs {sb}")
    else:
        add("suffix", None, "suffix missing")

    # specialty
    add("specialty", _field_agree(a.get("specialty") or "", b.get("specialty") or ""), "specialty family")

    # phone / email
    add("phone", _field_agree(a.get("phone") or "", b.get("phone") or ""), "phone")
    add("email", _field_agree(a.get("email") or "", b.get("email") or ""), "email")

    # geo
    zip_agree = _field_agree(a.get("zip3") or "", b.get("zip3") or "")
    add("zip3", zip_agree, "zip3")
    city_ok = _field_agree((a.get("city") or "").lower(), (b.get("city") or "").lower())
    state_ok = _field_agree(a.get("state") or "", b.get("state") or "")
    if city_ok is True and state_ok is True:
        add("city_state", True, "city+state")
    elif state_ok is True:
        add("city_state", True, "state only", strength=0.5)
    elif city_ok is False or state_ok is False:
        add("city_state", False, "geo mismatch")
    else:
        add("city_state", None, "geo missing")

    # org
    oa = (a.get("organization") or "").lower()
    ob = (b.get("organization") or "").lower()
    if oa and ob:
        org_agree = oa == ob or oa in ob or ob in oa
        add("organization", org_agree, "organization")
    else:
        add("organization", None, "organization missing")

    # license
    la = (a.get("license_no") or "").lower()
    lb = (b.get("license_no") or "").lower()
    if la and lb:
        add("license", la == lb and (not a.get("license_state") or not b.get("license_state") or a.get("license_state") == b.get("license_state")), "license")
    else:
        add("license", None, "license missing")

    # credentials soft
    ca = set((a.get("name") or {}).get("credentials") or [])
    cb = set((b.get("name") or {}).get("credentials") or [])
    if ca and cb:
        add("credential", bool(ca & cb), "credential")
    else:
        add("credential", None)

    # normalize to 0..1
    if weight_sum <= 0:
        score = 0.0
    else:
        # map weighted sum where max is weight_sum
        score = max(0.0, min(1.0, (weighted + weight_sum * 0.35) / (weight_sum * 1.35)))

    # strong NPI agreement floor
    if left_npis and right_npis and (left_npis & right_npis) and name_score >= 0.5:
        score = max(score, 0.97)

    return {
        "score": round(score, 4),
        "contributions": contributions,
        "name_score": round(name_score, 4),
        "name_reasons": name_reasons,
        "shared_npis": sorted(left_npis & right_npis),
    }
