from __future__ import annotations

import re
from typing import Dict, Tuple

# Lightweight PHI redaction (Presidio optional — regex fallback always available).
DOB_RE = re.compile(
    r"\b(?:DOB|D\.O\.B\.|date of birth)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    re.I,
)
DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
MRN_RE = re.compile(r"\b(?:MRN|medical record(?:\s+number)?)\s*[:#]?\s*[A-Za-z0-9-]{4,}\b", re.I)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# "patient Maria G." is a name. "patient support" is an ordinary phrase and stays.
PATIENT_NAME_RE = re.compile(r"\b(?:patient|pt\.?)\s+([A-Z][a-z]+(?:\s+[A-Z]\.)?)")
_PATIENT_STOP = {
    "support",
    "assistance",
    "enrollment",
    "education",
    "services",
    "service",
    "access",
    "advocate",
    "advocacy",
    "program",
    "programs",
    "care",
    "safety",
}


def redact_text(text: str) -> Tuple[str, Dict[str, int]]:
    if not text:
        return "", {}
    counts: Dict[str, int] = {}
    out = text

    def sub(pattern: re.Pattern[str], label: str, value: str) -> str:
        nonlocal out
        matches = pattern.findall(out)
        if matches:
            counts[label] = counts.get(label, 0) + len(matches)
            out = pattern.sub(f"[{label}]", out)
        return out

    sub(DOB_RE, "DOB", out)
    sub(SSN_RE, "SSN", out)
    sub(MRN_RE, "MRN", out)

    def patient_sub(match: re.Match[str]) -> str:
        token = match.group(1).split()[0].lower().rstrip(".")
        if token in _PATIENT_STOP:
            return match.group(0)
        counts["PATIENT"] = counts.get("PATIENT", 0) + 1
        return "[PATIENT]"

    out = PATIENT_NAME_RE.sub(patient_sub, out)
    sub(EMAIL_RE, "EMAIL", out)
    # phones in notes often not needed — redact
    sub(PHONE_RE, "PHONE", out)
    # leftover bare dates near clinical context already handled; leave other dates

    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore
        from presidio_anonymizer import AnonymizerEngine  # type: ignore

        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        results = analyzer.analyze(text=out, language="en")
        if results:
            anonymized = anonymizer.anonymize(text=out, analyzer_results=results)
            out = anonymized.text
            counts["presidio"] = len(results)
    except Exception:
        pass

    return out, counts
