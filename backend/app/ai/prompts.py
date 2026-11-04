from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"

PROMPT_FILES = {
    "identity_analysis": "doctor_identity_analysis_v1.txt",
    "change_extraction": "doctor_change_extraction_v1.txt",
    "profile_summary": "doctor_profile_summary_v1.txt",
    "review_explanation": "doctor_review_explanation_v1.txt",
}


@lru_cache
def load_prompt(operation: str) -> tuple[str, str, str]:
    filename = PROMPT_FILES[operation]
    text = (PROMPT_DIR / filename).read_text(encoding="utf-8")
    version = filename.replace(".txt", "")
    for line in text.splitlines():
        if line.lower().startswith("version:"):
            version = line.split(":", 1)[1].strip()
            break
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return version, digest, text
