from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.identity.standardize import parse_person_name

_ABBREV = ("Dr", "Jr", "Sr", "Prof", "Mr", "Mrs", "Ms", "St", "vs", "etc", "MD", "PhD")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TOKEN = r"[A-Z][A-Za-z'’]*(?:-[A-Z][A-Za-z'’]*)*"
_NAME = rf"{_TOKEN}(?:\s+{_TOKEN}){{0,3}}"
_SUFFIX = r"(?:\s*,?\s*(?:Jr|Sr)\.?)?"
_TITLE_MENTION = re.compile(
    rf"\b(?:(?:Prof|Professor)\.?\s+)?(?:Dr\.?\s+)({_NAME}{_SUFFIX})"
    rf"(?:\s*,\s*(?:NP|MD|PhD))?",
)
_PROF_MENTION = re.compile(rf"\b(?:Prof|Professor)\.?\s+({_NAME}{_SUFFIX})")
_CREDENTIAL_MENTION = re.compile(rf"\b({_NAME}{_SUFFIX})\s*,\s*(?:NP|MD|PhD)\b")
_AT_ORG = re.compile(r"\bat\s+([A-Z][A-Za-z0-9&'’\-]+(?:\s+[A-Z][A-Za-z0-9&'’\-]+){0,4})")
_IN_CITY = re.compile(r"\bin\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b")
_AE = re.compile(
    r"severe rash|adverse event|anaphylaxis|hospitali[sz]ed|side effect|toxicity|allergic reaction|"
    r"after starting therapy",
    re.I,
)
_SKIP_NAME = {
    "front",
    "desk",
    "patient",
    "support",
    "spoke",
    "met",
    "discussed",
    "asked",
    "reported",
    "she",
    "he",
    "office",
    "staff",
}


def split_sentences(text: str) -> List[str]:
    """Split on sentence boundaries without breaking Dr., Jr., Sr., or Prof."""
    if not text:
        return []
    abbrev = "|".join(_ABBREV)
    protected = re.sub(rf"\b(?:{abbrev})\.", lambda m: m.group(0).replace(".", "∯"), text)
    parts = _SENTENCE_SPLIT.split(protected)
    return [part.replace("∯", ".").strip() for part in parts if part.strip()]


def _clean_mention(raw: str) -> str:
    text = re.sub(r"\s+,", ",", raw or "")
    text = re.sub(r"\s+", " ", text).strip(" ,.;")
    return text


def extract_note(text: str) -> Dict[str, Any]:
    """Pull doctor mentions, proposed changes, and adverse-event flags from a note.

    Patient phrases are assumed already redacted. Ordinary words such as
    "patient support" are not treated as names.
    """
    sentences = split_sentences(text or "")
    mentions: List[Dict[str, Any]] = []
    for sentence in sentences:
        found = _TITLE_MENTION.findall(sentence) or _PROF_MENTION.findall(sentence) or _CREDENTIAL_MENTION.findall(sentence)
        if not found:
            continue
        raw_name = _clean_mention(found[0] if isinstance(found[0], str) else found[0])
        parsed = parse_person_name(raw_name)
        first = (parsed.get("first") or "").lower()
        last = (parsed.get("last") or "").lower()
        if first in _SKIP_NAME or last in _SKIP_NAME:
            continue
        if not last and not first:
            continue
        org_match = _AT_ORG.search(sentence)
        city_match = _IN_CITY.search(sentence)
        mentions.append(
            {
                "raw": raw_name,
                "parsed": parsed,
                "organization": (org_match.group(1).strip() if org_match else ""),
                "city_hint": (city_match.group(1).strip() if city_match else ""),
                "sentence": sentence,
            }
        )

    proposed: List[Dict[str, Any]] = []
    for sentence in sentences:
        low = sentence.lower()
        if "now at" in low or re.search(r"\bnow sees patients\b", low):
            org = ""
            match = re.search(r"\bat\s+([^.,]+)", sentence)
            if match:
                org = match.group(1).strip()
            proposed.append(
                {
                    "change_type": "added_site" if "in addition" in low else "affiliation",
                    "field": "organization",
                    "new_value": org,
                    "quote": sentence,
                }
            )
        elif "moved from" in low or "moved to" in low:
            proposed.append(
                {
                    "change_type": "move",
                    "field": "organization",
                    "new_value": sentence,
                    "quote": sentence,
                }
            )
        elif "retired" in low or "retirement" in low:
            proposed.append(
                {
                    "change_type": "retirement",
                    "field": "status",
                    "new_value": "Retired",
                    "quote": sentence,
                }
            )
        elif "in addition to" in low and not any(p["quote"] == sentence for p in proposed):
            proposed.append(
                {
                    "change_type": "added_site",
                    "field": "organization",
                    "new_value": sentence,
                    "quote": sentence,
                }
            )
        elif re.search(r"\bname change\b|\bnow goes by\b|\bformerly\b", low):
            proposed.append(
                {
                    "change_type": "name_change",
                    "field": "name",
                    "new_value": sentence,
                    "quote": sentence,
                }
            )

    safety: Optional[Dict[str, Any]] = None
    for sentence in sentences:
        if _AE.search(sentence):
            safety = {
                "flagged": True,
                "reason": "Possible adverse event mentioned in the note.",
                "quote": sentence,
                "route": "safety",
            }
            break

    primary = mentions[0] if mentions else None
    ambiguous = len(mentions) > 1
    return {
        "sentences": sentences,
        "mentions": mentions,
        "primary": primary,
        "ambiguous_mention": ambiguous,
        "proposed_changes": proposed,
        "safety": safety,
    }
