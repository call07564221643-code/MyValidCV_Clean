"""Evidence-safe experience bullet proposals for ATS Stage 2."""

from hashlib import sha256
import re

from .cv_drafting import parse_cv_sections


ACTION_VERBS = (
    "achieved", "administered", "analysed", "analyzed", "built", "coordinated",
    "created", "delivered", "developed", "implemented", "improved", "increased",
    "led", "maintained", "managed", "monitored", "organised", "organized",
    "prepared", "produced", "reduced", "resolved", "scheduled", "supported",
)

GERUND_TO_ACTION = {
    "coordinating": "Coordinated",
    "creating": "Created",
    "delivering": "Delivered",
    "developing": "Developed",
    "handling": "Handled",
    "implementing": "Implemented",
    "maintaining": "Maintained",
    "managing": "Managed",
    "monitoring": "Monitored",
    "organising": "Organised",
    "organizing": "Organized",
    "preparing": "Prepared",
    "scheduling": "Scheduled",
    "supporting": "Supported",
}


def _clean_bullet(text):
    return re.sub(r"\s+", " ", (text or "")).strip(" \t-•*")


def _normalise_bullet(text):
    cleaned = _clean_bullet(text)
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _term_matches(term, text):
    words = re.findall(r"[a-z0-9]+", term.lower())
    text_words = re.findall(r"[a-z0-9]+", text.lower())
    return bool(words) and all(
        any(candidate.startswith(word[:6]) for candidate in text_words)
        if len(word) >= 7 else word in text_words
        for word in words
    )


def propose_safe_bullet(original):
    """Improve presentation without adding facts, tools, outcomes, or duties."""
    text = _normalise_bullet(original)
    proposed = re.sub(r"^(?:I\s+)", "", text, flags=re.IGNORECASE)
    responsible = re.match(
        r"^(?:Was\s+)?responsible\s+for\s+([a-z]+ing)\s+(.+)$",
        proposed,
        flags=re.IGNORECASE,
    )
    if responsible:
        action = GERUND_TO_ACTION.get(responsible.group(1).lower())
        if action:
            proposed = f"{action} {responsible.group(2)}"
    proposed = _normalise_bullet(proposed)
    changed = proposed != text
    return proposed, changed


def extract_experience_bullets(cv_text, matched_terms, limit=12):
    """Return ordered, reviewable experience statements from the source CV."""
    sections = parse_cv_sections(cv_text)
    experience_sections = [section for section in sections if section["key"] == "experience"]
    candidates = []
    for section in experience_sections:
        for line in section["lines"]:
            for sentence in re.split(r"(?<=[.!?])\s+", line):
                cleaned = _clean_bullet(sentence)
                if not 35 <= len(cleaned) <= 420:
                    continue
                lower = cleaned.lower()
                has_action = (
                    any(re.search(rf"\b{verb}\b", lower) for verb in ACTION_VERBS)
                    or "responsible for" in lower
                    or any(re.search(rf"\b{verb}\b", lower) for verb in GERUND_TO_ACTION)
                )
                has_measure = bool(re.search(r"\b\d+(?:\.\d+)?%?\b|£|\$", cleaned))
                likely_employment_heading = (
                    not has_action
                    and bool(re.search(r"\b(?:19|20)\d{2}\b", cleaned))
                    and ("|" in cleaned or re.search(r"\b(?:19|20)\d{2}\s*[-–]\s*(?:present|(?:19|20)\d{2})", cleaned, re.IGNORECASE))
                )
                if likely_employment_heading:
                    continue
                if not has_action and not has_measure:
                    continue
                terms = [term for term in matched_terms if _term_matches(term, cleaned)][:5]
                proposed, changed = propose_safe_bullet(cleaned)
                rationale = (
                    "Uses direct action-led wording while preserving the source claim."
                    if changed else
                    "Keeps the evidence-led wording and standardises CV-ready punctuation."
                )
                position = len(candidates)
                fingerprint = sha256(
                    f"{position}:{cleaned.lower()}".encode("utf-8")
                ).hexdigest()
                candidates.append({
                    "position": position,
                    "original_text": cleaned,
                    "proposed_text": proposed,
                    "evidence_terms": terms,
                    "evidence_passage": cleaned,
                    "rationale": rationale,
                    "has_measure": has_measure,
                    "measurement_prompt": (
                        "" if has_measure else
                        "No measurable outcome is visible. Add one only if you can verify it."
                    ),
                    "fingerprint": fingerprint,
                })
                if len(candidates) >= limit:
                    return candidates
    return candidates


def apply_bullet_decisions(base_content, suggestions):
    """Apply new decisions or revisions against the wording currently in the draft."""
    content = base_content
    applied = []
    for suggestion in suggestions:
        applied_text = getattr(suggestion, "applied_text", "")
        if suggestion.status == "accepted":
            selected_text = suggestion.proposed_text
        elif suggestion.status == "edited":
            selected_text = suggestion.edited_text
        else:
            selected_text = suggestion.original_text
        needs_application = (
            applied_text != selected_text
            if applied_text
            else suggestion.status in {"accepted", "edited"}
        )
        if not needs_application:
            continue
        source = applied_text or suggestion.original_text
        replacement = selected_text
        if source in content:
            content = content.replace(source, replacement, 1)
            applied.append(suggestion)
    return content, applied
