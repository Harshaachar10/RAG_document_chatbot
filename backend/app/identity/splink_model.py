"""Fellegi-Sunter weights in the form Splink uses.

The sample is too small for EM, so every comparison level has a documented
m (probability the level agrees given a match) and u (given a non-match).
A Bayes factor of m/u is agreement; (1-m)/(1-u) is disagreement.
Missing levels are ignored. The prior odds convert the product into a
match probability. Embeddings, when present, are one banded level and
cannot carry a decision on their own.

Splink is imported when installed so the same m/u values can be attached to
comparison levels. The probability itself is the Fellegi-Sunter calculation
Splink's match weight uses (log2 of the Bayes factor, plus the prior).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

# Documented starting values. Tuned for precision on this oncology sample,
# not trained by EM. Rare surnames lower u at score time.
COMPARISON_LEVELS: Dict[str, Dict[str, float]] = {
    "surname_exact": {"m": 0.94, "u": 0.02},
    "surname_former": {"m": 0.72, "u": 0.01},
    "surname_typo": {"m": 0.55, "u": 0.008},
    "first_exact": {"m": 0.90, "u": 0.04},
    "first_nickname": {"m": 0.78, "u": 0.03},
    "first_initial": {"m": 0.35, "u": 0.18},
    "suffix_agree": {"m": 0.80, "u": 0.05},
    "state_agree": {"m": 0.84, "u": 0.08},
    "city_agree": {"m": 0.70, "u": 0.04},
    "specialty_agree": {"m": 0.75, "u": 0.15},
    "specialty_conflict": {"m": 0.08, "u": 0.40},
    "phone_unique": {"m": 0.88, "u": 0.01},
    "phone_shared": {"m": 0.40, "u": 0.25},
    "email_exact": {"m": 0.92, "u": 0.005},
    "license_agree": {"m": 0.97, "u": 0.002},
    "org_agree": {"m": 0.62, "u": 0.05},
    "embedding_high": {"m": 0.45, "u": 0.18},
    "embedding_mid": {"m": 0.28, "u": 0.22},
}

# Prior that two random compared records are the same doctor.
PRIOR_MATCH = 0.03


def bayes_factor(level: str, *, agree: bool) -> float:
    spec = COMPARISON_LEVELS[level]
    m = spec["m"]
    u = max(spec["u"], 1e-6)
    if agree:
        return m / u
    return (1.0 - m) / (1.0 - u)


def match_probability(levels: List[Dict[str, Any]], *, prior: float = PRIOR_MATCH) -> Dict[str, Any]:
    """levels: [{name, agree: bool|None}]. None means the comparison is missing."""
    odds = prior / (1.0 - prior)
    weights: List[Dict[str, Any]] = []
    for level in levels:
        agree = level.get("agree")
        if agree is None:
            continue
        factor = bayes_factor(level["name"], agree=bool(agree))
        # Rare-name adjustment is passed in as a u override.
        if level.get("u_override") and agree:
            spec = COMPARISON_LEVELS[level["name"]]
            factor = spec["m"] / max(float(level["u_override"]), 1e-6)
        odds *= factor
        weights.append(
            {
                "field": level["name"],
                "agree": bool(agree),
                "bayes_factor": round(factor, 4),
                "weight": round(math.log2(factor), 4),
            }
        )
    probability = odds / (1.0 + odds)
    match_weight = math.log2(odds) if odds > 0 else -99.0
    return {
        "probability": round(probability, 4),
        "match_weight": round(match_weight, 4),
        "prior": prior,
        "levels": weights,
    }


def splink_available() -> bool:
    try:
        import splink  # noqa: F401

        return True
    except Exception:
        return False


def splink_level_weights() -> List[Dict[str, Any]]:
    """Expose the same m/u table Splink comparison levels would be given."""
    rows = []
    for name, spec in COMPARISON_LEVELS.items():
        rows.append(
            {
                "level": name,
                "m_probability": spec["m"],
                "u_probability": spec["u"],
                "agreement_weight": round(math.log2(spec["m"] / spec["u"]), 4),
                "disagreement_weight": round(math.log2((1 - spec["m"]) / (1 - spec["u"])), 4),
            }
        )
    if splink_available():
        import splink

        rows.append({"splink_version": getattr(splink, "__version__", "installed")})
    return rows
