"""Bounded Ollama assistance for low-confidence deterministic validations."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request

from django.conf import settings


logger = logging.getLogger(__name__)


def redact_personal_data(text: str) -> str:
    """Remove common direct identifiers before optional model processing."""
    value = text or ""
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL REDACTED]", value)
    value = re.sub(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", "[PHONE REDACTED]", value)
    value = re.sub(r"https?://\S+|(?:www\.)?linkedin\.com/\S+", "[URL REDACTED]", value, flags=re.I)
    return value


def _clean_response(data) -> dict | None:
    if not isinstance(data, dict):
        return None
    explanation = str(data.get("explanation") or "").strip()[:800]
    terms = data.get("ambiguous_terms") or []
    if not isinstance(terms, list):
        return None
    terms = [str(term).strip()[:80] for term in terms if str(term).strip()][:8]
    if not explanation:
        return None
    return {"explanation": explanation, "ambiguous_terms": terms}


def low_confidence_assistance(details: dict, cv_text: str, job_description: str, job_title: str) -> dict | None:
    """Return advisory text without changing deterministic scoring fields."""
    if not getattr(settings, "ATS_AI_ASSIST_ENABLED", False) or not settings.OLLAMA_BASE_URL:
        return None
    confidence = details.get("confidence") or {}
    confidence_score = int(confidence.get("score") or 0)
    threshold = getattr(settings, "ATS_AI_CONFIDENCE_THRESHOLD", 60)
    if confidence_score >= threshold:
        return None

    payload = {
        "model": settings.OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 220},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You assist a deterministic CV validation system. Do not score, rank, reject, infer protected "
                    "characteristics, or invent evidence. Explain why the evidence may be ambiguous. Return JSON "
                    "only with keys explanation (string) and ambiguous_terms (array of strings)."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    "job_title": job_title[:150],
                    "job_description": redact_personal_data(job_description)[:5000],
                    "cv": redact_personal_data(cv_text)[:7000],
                    "deterministic_score": details.get("score"),
                    "confidence": confidence,
                    "missing_requirements": details.get("missing", [])[:12],
                }),
            },
        ],
    }
    headers = {"Content-Type": "application/json"}
    if settings.OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"
    request = urllib.request.Request(
        settings.OLLAMA_BASE_URL.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.OLLAMA_TIMEOUT_SECONDS) as response:
            outer = json.loads(response.read().decode("utf-8"))
        content = (outer.get("message") or {}).get("content", "")
        result = _clean_response(json.loads(content))
        if result:
            return {
                **result,
                "task": "low_confidence_explanation",
                "model": settings.OLLAMA_MODEL,
                "advisory_only": True,
                "changed_score": False,
            }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError, TypeError):
        logger.exception("Optional ATS Ollama assistance failed; deterministic result preserved.")
    return None
