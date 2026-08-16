import re
import urllib.request
import csv
import ipaddress
import logging
import socket
from datetime import datetime, timedelta
from urllib.parse import urlparse

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import (
    ATSAnalysisForm,
    CVUpdateForm,
    CVUploadForm,
    EnterpriseBulkAnalysisForm,
)
from .models import (
    ApplicationReminder,
    ATSResult,
    CV,
    CVBulletSuggestion,
    CVStorage,
    EnterpriseBatch,
    EnterpriseCandidateResult,
    GeneratedCoverLetter,
    GeneratedCV,
    JobRole,
)
from .bullet_rewriting import apply_bullet_decisions, extract_experience_bullets
from accounts.models import UserProfile
from .engine import ats_engine
from .cv_drafting import build_structured_cv_draft, cv_text_to_docx, is_legacy_generated_cv
from .scoring import ATS_MODEL_VERSION, calculate_score, calculate_score_details, validate_job_description
from subscriptions.services import get_active_subscription, get_entitlements


APPLY_STRONG_THRESHOLD = 75
APPLY_MINIMUM_THRESHOLD = 55
logger = logging.getLogger(__name__)


def get_user_profile(user):
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return profile


def storage_limit_for_user(user):
    limits = {
        "free": 5 * 1024 * 1024,
        "plus": 50 * 1024 * 1024,
        "enterprise": 1024 * 1024 * 1024,
    }
    return limits.get(get_entitlements(user).code, limits["free"])


def get_user_cv_storage(user):
    storage, _created = CVStorage.objects.get_or_create(
        user=user,
        defaults={"storage_limit": storage_limit_for_user(user)},
    )
    expected_limit = storage_limit_for_user(user)
    if storage.storage_limit != expected_limit:
        storage.storage_limit = expected_limit
        storage.save(update_fields=["storage_limit", "updated_at"])
    return storage


def populate_cv_metadata(cv, uploaded_file, validation_status="valid", validation_notes=""):
    cv.storage = get_user_cv_storage(cv.user)
    cv.original_filename = uploaded_file.name[:255]
    cv.mime_type = getattr(uploaded_file, "content_type", "") or ""
    cv.file_size = getattr(uploaded_file, "size", 0) or 0
    # Heroku's local filesystem is ephemeral. Keep the original bytes in
    # PostgreSQL for the 30-day retention window so a dyno restart does not make
    # an otherwise valid CV unreadable. The purge command deletes this row/data.
    uploaded_file.seek(0)
    cv.file_data = uploaded_file.read()
    uploaded_file.seek(0)
    cv.validation_status = validation_status
    cv.is_valid_cv = validation_status == "valid"
    cv.validation_notes = validation_notes
    return cv


def refresh_cv_storage(user):
    storage = get_user_cv_storage(user)
    storage.refresh_used_storage()
    return storage


def extract_cv_text(cv):
    """Extract stored bytes first, then storage backend file, then safe fallback."""
    if cv.file_data:
        from django.core.files.uploadedfile import SimpleUploadedFile
        stored_upload = SimpleUploadedFile(
            cv.original_filename or cv.title,
            bytes(cv.file_data),
            content_type=cv.mime_type or "application/octet-stream",
        )
        try:
            return ats_engine.extract_text_from_upload(stored_upload)
        except Exception:
            pass
    try:
        cv.file.open("rb")
        try:
            return ats_engine.extract_text_from_upload(cv.file)
        finally:
            cv.file.close()
    except Exception:
        return cv.title


def extract_uploaded_cv_text(uploaded_file):
    """Extract text from an uploaded CV file object."""
    try:
        text = ats_engine.extract_text_from_upload(uploaded_file)
        uploaded_file.seek(0)
        return text
    except Exception:
        uploaded_file.seek(0)
        try:
            text = uploaded_file.read().decode("utf-8")
            uploaded_file.seek(0)
            return text
        except Exception:
            return uploaded_file.name


def validate_cv_for_analysis(cv_text):
    is_valid, reason = ats_engine.validate_cv_text(cv_text)
    if is_valid:
        return True, ""
    return False, f"The document you uploaded is not good enough as a CV yet. {reason}"


def extract_job_file_text(uploaded_file):
    """Extract text from an uploaded job advert file."""
    try:
        text = ats_engine.extract_text_from_upload(uploaded_file)
        uploaded_file.seek(0)
        return text
    except Exception:
        uploaded_file.seek(0)
        try:
            text = uploaded_file.read().decode("utf-8")
            uploaded_file.seek(0)
            return text
        except Exception:
            return ""


def _validate_public_job_url(url):
    """Reject local/private destinations to prevent server-side request forgery."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTP(S) job URLs are allowed.")
    if parsed.port and parsed.port not in (80, 443):
        raise ValueError("Job URLs may use only standard HTTP or HTTPS ports.")
    for address in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Private or local job URLs are not allowed.")
    return url


class _SafeJobRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_job_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_job_url_text(url):
    """Best-effort fetch of a public job advert with SSRF-safe redirects."""
    try:
        _validate_public_job_url(url)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        # Keep this best-effort request short so a slow job board does not tie
        # up a web worker for most of Gunicorn's request timeout.
        opener = urllib.request.build_opener(_SafeJobRedirectHandler())
        with opener.open(request, timeout=4) as response:
            peer_socket = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
            if peer_socket:
                peer_ip = ipaddress.ip_address(peer_socket.getpeername()[0])
                if not peer_ip.is_global:
                    raise ValueError("The job URL connected to a private or local address.")
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
                raise ValueError("The job URL did not return a readable web page.")
            html = response.read(300000).decode("utf-8", errors="ignore")
        text = re.sub(r"<(script|style).*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


def build_job_description(form):
    source_type = form.cleaned_data["source_type"]
    if source_type == "text":
        return form.cleaned_data["job_description"]
    if source_type == "file":
        return extract_job_file_text(form.cleaned_data["job_file"])

    url_text = fetch_job_url_text(form.cleaned_data["job_url"])
    if url_text:
        return url_text
    return ""


def infer_job_title(form, job_description):
    explicit_title = form.cleaned_data.get("job_title")
    if explicit_title:
        return explicit_title

    source_type = form.cleaned_data.get("source_type")
    if source_type == "url" and form.cleaned_data.get("job_url"):
        parsed = urlparse(form.cleaned_data["job_url"])
        path_title = parsed.path.strip("/").split("/")[-1].replace("-", " ").replace("_", " ").strip()
        if path_title:
            return path_title.title()[:150]
        return parsed.netloc.replace("www.", "").title()[:150]

    if source_type == "file" and form.cleaned_data.get("job_file"):
        filename = form.cleaned_data["job_file"].name.rsplit(".", 1)[0]
        return filename.replace("-", " ").replace("_", " ").title()[:150]

    for line in job_description.splitlines():
        candidate = line.strip(" -:\t")
        if 4 <= len(candidate) <= 90 and not candidate.lower().startswith(("http", "www.")):
            return candidate[:150]

    return "Advertised Role"


def infer_company(form, job_description):
    explicit_company = form.cleaned_data.get("company")
    if explicit_company:
        return explicit_company

    patterns = [
        r"\bcompany\s*[:\-]\s*([A-Za-z0-9 &.,'-]{2,80})",
        r"\bemployer\s*[:\-]\s*([A-Za-z0-9 &.,'-]{2,80})",
        r"\bat\s+([A-Z][A-Za-z0-9 &.,'-]{2,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, job_description, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()[:150]
    return ""


def infer_deadline(form, job_description):
    explicit_deadline = form.cleaned_data.get("deadline")
    if explicit_deadline:
        return explicit_deadline

    label = r"(?:deadline|closing date|applications? close|apply by|apply before|last day to apply)"
    date_value = r"(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})"
    patterns = [rf"\b{label}\s*[:\-]?\s*{date_value}"]
    for pattern in patterns:
        match = re.search(pattern, job_description, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1)
        for date_format in ("%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
    return None


def user_can_use_enterprise(user):
    """Authorise bulk tools from a current Enterprise subscription, not UI state."""
    return get_entitlements(user).enterprise_reports


def active_enterprise_subscription(user):
    subscription = get_active_subscription(user)
    return subscription if subscription and subscription.plan.code == "enterprise" else None


def enterprise_monthly_usage(user):
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return EnterpriseCandidateResult.objects.filter(
        batch__user=user,
        created_at__gte=month_start,
    ).count()


ENTERPRISE_DAILY_LIMIT = 50


def enterprise_daily_usage(user):
    day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return EnterpriseCandidateResult.objects.filter(
        batch__user=user,
        created_at__gte=day_start,
    ).count()


def build_generated_cv(cv, result, matched, missing):
    cv_text = extract_cv_text(cv)
    preview = build_cv_draft_preview(result, matched, missing, cv_text)
    target_role = preview["target_role"]
    missing_text = ", ".join(missing) if missing else "No major missing skills detected"
    decision = build_application_decision(result.score)
    if not decision["can_rewrite"]:
        return f"""CV Evidence Plan for {target_role}

Source CV: {cv.title}
ATS Match Score: {result.score}%

Application Decision
{decision["message"]}

Suggested Action
Do not create a cosmetic CV rewrite for this job yet. The current CV does not show enough evidence for the role requirements. Build truthful evidence first, such as training, licence, domain experience, portfolio work, or measurable examples that directly support the job advert.

Missing Evidence To Address
{missing_text}

Original CV Content Reference
{cv_text[:2500]}
"""
    structured = build_structured_cv_draft(
        cv_text,
        target_role,
        preview["summary"],
        preview["skills"],
        missing,
    )
    return structured["full_text"]


def create_bullet_suggestions(result, cv_text="", matched=None):
    """Create deterministic Stage 2 suggestions once for an owned result."""
    if result.bullet_suggestions.exists():
        return result.bullet_suggestions.all()
    cv_text = cv_text or extract_cv_text(result.cv)
    matched = matched if matched is not None else [
        item.strip() for item in result.matched_skills.split(",") if item.strip()
    ]
    proposals = extract_experience_bullets(cv_text, matched)
    CVBulletSuggestion.objects.bulk_create([
        CVBulletSuggestion(
            user=result.user,
            ats_result=result,
            **proposal,
        )
        for proposal in proposals
    ], ignore_conflicts=True)
    return result.bullet_suggestions.all()


def clean_cover_letter_title(title):
    title = re.sub(r"\s+", " ", (title or "").strip(" -:"))
    bad_fragments = [
        "because you",
        "can't reveal",
        "cannot reveal",
        "before saving",
        "hiring manager",
        "imported job role",
    ]
    if not title or len(title) > 80 or any(fragment in title.lower() for fragment in bad_fragments):
        return "the advertised role"
    return title


def clean_cover_letter_company(company):
    company = re.sub(r"\s+", " ", (company or "").strip(" -:"))
    if not company or company.lower() in {"hiring manager", "unknown", "n/a"} or len(company) > 80:
        return "your organisation"
    return company


def build_cover_letter(user, result, matched, cv_text=""):
    name = user.get_full_name().strip() or user.username
    role_title = clean_cover_letter_title(result.job_title)
    company = clean_cover_letter_company(result.job_role.company if result.job_role else "")
    strengths = [item for item in matched[:5] if len(item) > 2]
    strengths_text = ", ".join(strengths) if strengths else "relevant experience evidenced in my CV"
    evidence_lines = extract_cv_evidence_lines(cv_text, strengths, limit=2)
    if evidence_lines:
        evidence_text = " ".join(evidence_lines)
    else:
        evidence_text = (
            "My CV demonstrates experience that is relevant to the role requirements, "
            "with emphasis on responsibilities and outcomes already evidenced in the document."
        )
    return f"""Dear Hiring Manager,

I am writing to apply for the position of {role_title} at {company}. Having reviewed the requirements, I believe my experience in {strengths_text} would enable me to make a positive contribution.

My suitability is supported by the following experience: {evidence_text}

I would welcome the opportunity to discuss how my skills and experience align with your priorities for this role. I would be pleased to provide further detail at interview.

Thank you for your time and consideration.

Yours sincerely,
{name}
"""


def can_download_generated_cv(user):
    """Authorise individual paid generation for Plus/Professional accounts."""
    return get_entitlements(user).generated_documents


def score_breakdown(score, matched, missing, metrics=None):
    """Return measured ATS v2 components rather than inferred percentages."""
    components = (metrics or {}).get("score_components", {})
    return {
        "skills": components.get("skills", 0),
        "requirements": components.get("requirements", 0),
        "evidence": components.get("evidence", 0),
        "format": components.get("format", 0),
        "total": score,
        "matched_count": len(matched),
        "missing_count": len(missing),
    }


def build_match_intelligence(result, cv_text=None):
    metrics = result.metrics or {}
    taxonomy = metrics.get("taxonomy") or {}
    components = metrics.get("score_components") or {}
    if (not taxonomy or not components) and cv_text is not None:
        details = calculate_score_details(cv_text, result.job_description, result.job_title)
        taxonomy = details.get("taxonomy", {})
        components = details.get("score_components", {})
    return {
        "detected_role": taxonomy.get("detected_role") or "Specific job advert",
        "detected_family": taxonomy.get("detected_family") or "Advert-led analysis",
        "mandatory_terms": taxonomy.get("mandatory_terms", []),
        "missing_mandatory": taxonomy.get("missing_mandatory", []),
        "matched_required": taxonomy.get("matched_required", []),
        "required_skills": taxonomy.get("required_skills", []),
        "required_qualifications": taxonomy.get("required_qualifications", []),
        "components": components,
    }


def build_application_decision(score):
    if score >= APPLY_STRONG_THRESHOLD:
        return {
            "status": "worth",
            "label": "Strong CV-to-role alignment",
            "threshold": APPLY_STRONG_THRESHOLD,
            "can_rewrite": True,
            "message": (
                f"Your CV is aligned above the {APPLY_STRONG_THRESHOLD}% evidence-review threshold. "
                "This is not a prediction of hiring success; confirm every claim and mandatory requirement before applying."
            ),
        }
    if score >= APPLY_MINIMUM_THRESHOLD:
        return {
            "status": "improve",
            "label": "Strengthen the evidence",
            "threshold": APPLY_MINIMUM_THRESHOLD,
            "can_rewrite": True,
            "message": (
                f"The CV shows partial alignment above the {APPLY_MINIMUM_THRESHOLD}% review threshold. "
                "Strengthen the identified evidence gaps before deciding whether to apply."
            ),
        }
    return {
        "status": "low",
        "label": "Significant evidence gap",
        "threshold": APPLY_MINIMUM_THRESHOLD,
        "can_rewrite": False,
        "message": (
            "The CV does not currently meet the minimum "
            f"{APPLY_MINIMUM_THRESHOLD}% evidence-alignment threshold. This describes the document match, not your personal potential."
        ),
    }


def build_suggested_cv_review(result, matched, missing):
    decision = build_application_decision(result.score)
    matched_text = ", ".join(matched[:5]) if matched else "the strongest truthful evidence already visible in the CV"
    missing_text = ", ".join(missing[:5]) if missing else "no major missing evidence"
    return {
        "decision": decision,
        "format_note": (
            "The suggested draft keeps the candidate's existing CV structure where possible: summary, skills, "
            "experience, education, and supporting evidence. It changes wording and ordering; it must not invent facts."
        ),
        "sections": [
            {
                "tone": "green",
                "label": "CV wording",
                "meaning": "Rewording only",
                "text": (
                    f"Green highlights use evidence already detected in the CV, such as {matched_text}. "
                    "These are safe wording and ordering changes."
                ),
            },
            {
                "tone": "yellow",
                "label": "Enhanced evidence",
                "meaning": "Stronger presentation",
                "text": (
                    "Yellow highlights show where the same CV evidence has been presented more strongly, usually by making "
                    "responsibility, tools, scope, or impact clearer."
                ),
            },
            {
                "tone": "red",
                "label": "Not evidenced",
                "meaning": "Proof needed",
                "text": (
                    f"Red highlights show missing or weakly evidenced items such as {missing_text}. "
                    "These should not be claimed unless the candidate genuinely has proof."
                ),
            },
        ],
    }


def clean_cv_sentence(text):
    cleaned = re.sub(r"\s+", " ", (text or "").strip(" -•*\t"))
    if not cleaned:
        return ""
    cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def extract_cv_evidence_lines(cv_text, terms, limit=4):
    text = cv_text or ""
    candidates = []
    for chunk in re.split(r"[\n\r]+|(?<=[.!?])\s+", text):
        line = clean_cv_sentence(chunk)
        if not 35 <= len(line) <= 220:
            continue
        line_lower = line.lower()
        if "@" in line_lower or "http" in line_lower or "linkedin" in line_lower:
            continue
        if terms and not any(term.lower() in line_lower for term in terms):
            continue
        candidates.append(line)

    if not candidates:
        for chunk in re.split(r"[\n\r]+|(?<=[.!?])\s+", text):
            line = clean_cv_sentence(chunk)
            if 45 <= len(line) <= 220 and "@" not in line:
                candidates.append(line)
            if len(candidates) >= limit:
                break

    seen = set()
    unique = []
    for line in candidates:
        key = line.lower()
        if key not in seen:
            seen.add(key)
            unique.append(line)
        if len(unique) >= limit:
            break
    return unique


def build_cv_draft_preview(result, matched, missing, cv_text=""):
    generic_terms = {
        "various", "skills", "skill", "software", "office", "work", "working",
        "experience", "role", "responsibilities", "job",
    }
    specific_matches = [
        item for item in matched
        if item.strip().lower() not in generic_terms and len(item.strip()) > 2
    ]
    selected_matches = specific_matches[:4] or matched[:3]
    matched_text = ", ".join(selected_matches) if selected_matches else "role-relevant evidence"
    missing_text = ", ".join(missing[:5]) if missing else "no major evidence gaps"
    safe_role = result.job_title or "Target Role"
    taxonomy = (result.metrics or {}).get("taxonomy", {})
    if safe_role.strip().lower() in {"imported job role", "advertised role"}:
        safe_role = taxonomy.get("detected_role") or "the advertised role"
    safe_role = format_document_heading(safe_role)
    evidence_lines = extract_cv_evidence_lines(cv_text, matched, limit=4)
    return {
        "candidate_name": format_document_heading(result.cv.title),
        "target_role": safe_role,
        "summary": (
            f"Professional targeting {safe_role}, with source-CV evidence in {matched_text}. "
            "Brings relevant experience that should be supported by specific responsibilities "
            "and measurable outcomes elsewhere in the CV."
        ),
        "skills": (specific_matches or matched)[:8] or ["Add verified role-specific skills from your CV evidence"],
        "experience_bullets": evidence_lines or [
            "Relevant experience was not clearly detected in the source CV text.",
            "A stronger tailored CV cannot be produced until the CV includes truthful role evidence.",
        ],
        "education_note": (
            f"Not evidenced strongly enough in the source CV: {missing_text}."
        ),
    }


def format_document_heading(value):
    """Normalise user-supplied report headings without damaging mixed-case names."""
    text = re.sub(r"\s+", " ", (value or "").strip())
    if not text:
        return ""

    acronyms = {
        "ats": "ATS",
        "cv": "CV",
        "gdpr": "GDPR",
        "hr": "HR",
        "it": "IT",
        "uk": "UK",
    }
    normalise_words = text.islower()
    words = []
    for word in text.split(" "):
        bare_word = re.sub(r"[^A-Za-z0-9]+", "", word).lower()
        if bare_word in acronyms:
            replacement = acronyms[bare_word]
            words.append(re.sub(re.escape(bare_word), replacement, word, flags=re.IGNORECASE))
        elif normalise_words and word:
            words.append(word[0].upper() + word[1:])
        else:
            words.append(word)

    formatted = " ".join(words)
    return formatted[0].upper() + formatted[1:] if formatted else ""


def resolve_generated_cv_draft(result, generated_cv=None, cv_text=""):
    """Return the current clean draft and its provenance without rewriting saved data."""
    cv_text = cv_text or extract_cv_text(result.cv)
    matched = [item.strip() for item in result.matched_skills.split(",") if item.strip()]
    missing = [item.strip() for item in result.missing_skills.split(",") if item.strip()]
    preview = build_cv_draft_preview(result, matched, missing, cv_text)
    structured = build_structured_cv_draft(
        cv_text,
        preview["target_role"],
        preview["summary"],
        preview["skills"],
        missing,
    )

    saved_content = (getattr(generated_cv, "content", "") or "").strip()
    if not saved_content:
        state = "system_proposal"
        editable_content = structured["full_text"]
        state_label = "System proposal"
        state_note = "Generated from the source CV and ready for candidate review."
    elif is_legacy_generated_cv(saved_content):
        state = "legacy_upgraded"
        editable_content = structured["full_text"]
        state_label = "Legacy draft upgraded"
        state_note = "The older advisory format was converted for review; its saved record was not overwritten."
    elif saved_content == structured["full_text"].strip():
        state = "system_proposal"
        editable_content = saved_content
        state_label = "System proposal"
        state_note = "Generated from the source CV and not yet edited by the candidate."
    else:
        state = "candidate_edited"
        editable_content = saved_content
        state_label = "Candidate-edited"
        state_note = "This version contains changes saved by the candidate."

    structured.update({
        "editable_content": editable_content,
        "draft_state": state,
        "draft_state_label": state_label,
        "draft_state_note": state_note,
    })
    return structured


def build_report_insights(result, matched, missing):
    if result.score >= 80:
        readiness_label = "Ready to apply"
        readiness_class = "ready"
        recruiter_view = "The document shows clear role alignment when the strongest verified evidence stays near the top."
        weakness_summary = "Main risk: strong evidence may be buried, generic, or not measurable."
    elif result.score >= 55:
        readiness_label = "Needs work before applying"
        readiness_class = "work"
        recruiter_view = "The document shows partial fit, but the supporting evidence is not immediate enough."
        weakness_summary = "Main risk: relevant experience is present but not visible or proven enough."
    else:
        readiness_label = "High risk of being screened out"
        readiness_class = "risk"
        recruiter_view = "The document does not yet show enough role-specific evidence."
        weakness_summary = "Main risk: visible CV evidence does not meet enough of the role requirements."

    top_fixes = [
        "Move the strongest role-matched skills and achievements into the top third of the CV.",
        "Add measurable proof beside relevant skills, such as outcomes, tools used, scale, or delivery impact.",
        "Remove or shorten generic content that does not help this specific application.",
    ]
    if missing:
        top_fixes.insert(
            1,
            f"Address missing evidence for {', '.join(missing[:3])} only if you genuinely have experience with it.",
        )
    if matched:
        top_fixes.insert(
            0,
            f"Make these matched strengths easy to spot: {', '.join(matched[:4])}.",
        )

    return {
        "readiness_label": readiness_label,
        "readiness_class": readiness_class,
        "recruiter_view": recruiter_view,
        "weakness_summary": weakness_summary,
        "top_fixes": top_fixes[:5],
    }


REQUIREMENT_DISPLAY_LABELS = {
    "skillsproficiency": "Skills proficiency",
    "workexperience": "Work experience",
    "customerservice": "Customer service",
    "problemsolving": "Problem solving",
    "projectmanagement": "Project management",
    "timemanagement": "Time management",
}


def humanize_requirement_term(term):
    cleaned = re.sub(r"[_-]+", " ", str(term or "").strip())
    cleaned = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    known_label = REQUIREMENT_DISPLAY_LABELS.get(cleaned.replace(" ", "").lower())
    if known_label:
        return known_label
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "This requirement"


def build_truth_gate_summary(evidence_map):
    items = list(evidence_map or [])[:12]
    actions = [item.get("candidate_action") for item in items]
    confirmed = actions.count("confirmed")
    training = actions.count("training")
    not_have = actions.count("not_have")
    answered = confirmed + training + not_have
    total = len(items)
    remaining = max(total - answered, 0)
    completion = int((answered / total) * 100) if total else 0

    if total == 0:
        next_action = "No requirement-level questions are available for this report."
        tone = "neutral"
    elif remaining:
        next_action = (
            f"Answer the remaining {remaining} requirement"
            f"{'' if remaining == 1 else 's'} to unlock your evidence-based next step."
        )
        tone = "progress"
    elif not_have:
        next_action = (
            "Keep unsupported requirements out of the CV. Focus the application on confirmed strengths, "
            "then review whether the missing requirements are mandatory before applying."
        )
        tone = "caution"
    elif training:
        next_action = (
            "Continue with the application using confirmed evidence only. Present training as in progress "
            "and prepare a clear completion timeline for interview."
        )
        tone = "developing"
    else:
        next_action = (
            "Your review is complete. Use the confirmed strengths in the suggested CV, then open the "
            "role-specific interview studio to prepare evidence-based examples."
        )
        tone = "ready"

    return {
        "total": total,
        "answered": answered,
        "remaining": remaining,
        "confirmed": confirmed,
        "training": training,
        "not_have": not_have,
        "completion": completion,
        "confirmed_percentage": int((confirmed / total) * 100) if total else 0,
        "training_percentage": int((training / total) * 100) if total else 0,
        "gap_percentage": int((not_have / total) * 100) if total else 0,
        "complete": bool(total and answered == total),
        "next_action": next_action,
        "tone": tone,
    }


def build_reliability_guidance(confidence, historic_score=False):
    confidence = confidence or {}
    reasons = list(confidence.get("reasons") or [])
    label = confidence.get("label", "Low")
    no_role_match = any("role template" in reason.lower() for reason in reasons)

    if label == "High" and not no_role_match:
        status = "Reliable basis"
        tone = "positive"
        message = "We found enough clear information in the CV and job advert to support this check."
        action = "Continue to the Truth Gate and verify each requirement before using the recommendations."
    elif label == "Low":
        status = "Limited check"
        tone = "neutral"
        message = "The CV or job advert did not provide enough clear information for a dependable comparison."
        action = "Add more detail to the CV or job advert, then run the check again."
    else:
        status = "Review carefully"
        tone = "neutral"
        if no_role_match:
            message = "We found enough information to assess the CV, but we could not identify the exact job type."
        else:
            message = "We completed the check, but some information was too limited to classify confidently."
        action = "Check the requirements below carefully before using the recommendations."

    plain_details = []
    detail_translations = {
        "No curated role template matched this advert.": "The exact job type could not be identified.",
        "The CV contains limited extractable text.": "The CV contained limited readable text.",
        "The CV contains only moderate extractable detail.": "The CV contained a moderate amount of readable detail.",
        "The job advert is relatively short.": "The job advert was short.",
        "The job advert contains only moderate detail.": "The job advert contained a moderate amount of detail.",
        "Few distinct job requirements were detected.": "Only a few clear job requirements were found.",
        "Little requirement-level evidence was located in the CV.": "Less than half of the requirements had visible CV evidence.",
    }
    for reason in reasons:
        plain_details.append(detail_translations.get(reason, reason))
    if historic_score:
        plain_details.append("This older report keeps its original match score while using the latest explanation format.")

    return {
        "status": status,
        "tone": tone,
        "message": message,
        "action": action,
        "details": plain_details,
    }


def build_interview_plan(evidence_map, job_title):
    tailored = []
    focus_terms = []
    for item in (evidence_map or [])[:12]:
        term = item.get("term", "this requirement")
        display_term = humanize_requirement_term(term)
        focus_terms.append(display_term)
        candidate_action = item.get("candidate_action")
        if candidate_action == "confirmed":
            prompt = (
                f"Show how you used {display_term} in a real situation. What did you personally do, "
                "what changed, and how would you prove the result?"
            )
        elif candidate_action == "training":
            prompt = (
                f"Explain what you are currently learning about {display_term}, how you are practising it, "
                "and when you expect to be work-ready."
            )
        elif candidate_action == "not_have":
            prompt = (
                f"Prepare an honest response about not yet having {display_term}. Which transferable strength "
                "reduces the gap, and what realistic learning plan would you offer?"
            )
        elif item.get("status") == "verified":
            prompt = (
                f"Tell me about a time you used {display_term}. Explain the situation, your actions, "
                "and the measurable result."
            )
        elif item.get("status") == "mentioned":
            prompt = f"Your CV mentions {display_term}. What specific example proves your level of experience?"
        elif item.get("status") == "proof_required":
            prompt = f"If asked about {display_term}, clearly explain your current qualification, licence, or training status."
        else:
            prompt = f"How would you respond honestly if the interviewer asks about your experience with {display_term}?"
        tailored.append({"term": display_term, "prompt": prompt, "status": candidate_action or item.get("status")})
        if len(tailored) >= 6:
            break

    role_name = job_title or "this role"
    return {
        "role": role_name,
        "focus_terms": focus_terms[:4],
        "standard": [
            {
                "title": "Your 60-second introduction",
                "prompt": (
                    f"Connect your current experience to {role_name}, name two relevant strengths, "
                    "and explain why this move makes sense now."
                ),
            },
            {
                "title": "STAR evidence",
                "prompt": (
                    "Prepare one concise Situation, Task, Action and Result example. Spend most of the "
                    "answer on your own actions and finish with a verifiable outcome."
                ),
            },
            {
                "title": "Your questions",
                "prompt": (
                    f"Prepare two informed questions about expectations, priorities or success measures "
                    f"for {role_name}; avoid questions answered clearly in the advert."
                ),
            },
        ],
        "tailored": tailored,
    }


def save_inline_cv(request, form):
    selected_cv = form.cleaned_data.get("cv")
    if selected_cv:
        return selected_cv

    uploaded_cv = form.cleaned_data.get("cv_file")
    if not uploaded_cv:
        return None

    cv_text = extract_uploaded_cv_text(uploaded_cv)
    is_valid_cv, reason = validate_cv_for_analysis(cv_text)
    if not is_valid_cv:
        form.add_error("cv_file", reason)
        return None

    entitlements = get_entitlements(request.user)
    cv_count = CV.objects.filter(user=request.user).count()
    if cv_count >= entitlements.cv_limit:
        form.add_error("cv_file", f"Your {entitlements.code} plan has reached the saved CV limit.")
        return None

    cv_title = form.cleaned_data.get("cv_title") or uploaded_cv.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
    cv = CV(user=request.user, title=cv_title[:150])
    populate_cv_metadata(cv, uploaded_cv, validation_status="valid", validation_notes="Passed CV readiness validation.")
    cv.file.save(uploaded_cv.name, uploaded_cv, save=True)
    refresh_cv_storage(request.user)
    return cv


@login_required(login_url="login")
def upload_cv(request):
    profile = get_user_profile(request.user)
    entitlements = get_entitlements(request.user)
    cv_count = CV.objects.filter(user=request.user).count()

    def page_context(form):
        return {
            "form": form,
            "profile": profile,
            "cv_count": cv_count,
            "cv_limit": entitlements.cv_limit,
            "saved_cvs": CV.objects.filter(user=request.user).order_by("-uploaded_at"),
        }

    if request.method != "POST" and cv_count >= entitlements.cv_limit:
        messages.warning(request, f"Your {entitlements.code} plan allows {entitlements.cv_limit} saved CV(s). Upgrade to save more.")

    if request.method == "POST":
        form = CVUploadForm(request.POST, request.FILES)
        if cv_count >= entitlements.cv_limit:
            messages.error(request, f"Your {entitlements.code} plan has reached the saved CV limit.")
            return redirect("dashboard")
        if form.is_valid():
            cv_text = extract_uploaded_cv_text(form.cleaned_data["file"])
            is_valid_cv, reason = validate_cv_for_analysis(cv_text)
            if not is_valid_cv:
                form.add_error("file", reason)
                return render(request, "ats/upload_cv.html", page_context(form))
            cv = form.save(commit=False)
            cv.user = request.user
            populate_cv_metadata(cv, form.cleaned_data["file"], validation_status="valid", validation_notes="Passed CV readiness validation.")
            cv.save()
            refresh_cv_storage(request.user)
            messages.success(request, "CV uploaded successfully.")
            return redirect(f"{reverse('ats_analyse')}?cv={cv.id}")
    else:
        form = CVUploadForm()

    return render(request, "ats/upload_cv.html", page_context(form))


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def update_cv(request, public_id):
    """Rename one CV owned by the authenticated user."""
    cv = get_object_or_404(CV, public_id=public_id, user=request.user)
    form = CVUpdateForm(request.POST or None, instance=cv)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "CV name updated.")
        return redirect("upload_cv")
    return render(request, "ats/update_cv.html", {"form": form, "cv": cv})


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def delete_cv(request, public_id):
    """Confirm and delete one owned CV plus its dependent analysis records."""
    cv = get_object_or_404(CV, public_id=public_id, user=request.user)
    if request.method == "POST":
        title = cv.title
        cv.delete()
        refresh_cv_storage(request.user)
        messages.success(request, f'“{title}” and its related reports were deleted.')
        return redirect("upload_cv")
    return render(request, "ats/delete_cv_confirm.html", {
        "cv": cv,
        "result_count": cv.results.count(),
    })


@login_required(login_url="login")
def analyse_cv(request):
    """Run the authenticated individual CV-to-job workflow.

    Stages: enforce monthly allowance; select/upload the user's CV; read the job
    text/file/URL; create JobRole and ATSResult rows; create Plus-only CV and
    cover-letter drafts; optionally schedule a deadline reminder; record usage.
    Every subsequent result query is also restricted to ``request.user``.
    """
    user_cvs = CV.objects.filter(user=request.user)
    profile = get_user_profile(request.user)
    entitlements = get_entitlements(request.user)
    inline_result = None
    breakdown = None

    def workspace_context(form):
        return {
            "form": form,
            "has_cvs": user_cvs.exists(),
            "profile": profile,
            "result": inline_result,
            "breakdown": breakdown,
            "can_download": can_download_generated_cv(request.user),
            "recent_results": ATSResult.objects.filter(user=request.user).select_related("cv", "job_role")[:8],
            "saved_cvs": CV.objects.filter(user=request.user)[:6],
            "generated_cvs": GeneratedCV.objects.filter(user=request.user).select_related("ats_result")[:6],
            "reminders": ApplicationReminder.objects.filter(user=request.user, is_sent=False).select_related("job_role")[:4],
            "is_enterprise": entitlements.enterprise_reports,
        }

    def render_home_workspace(form):
        return render(request, "ats/analyse.html", workspace_context(form))

    if request.method == "POST":
        form = ATSAnalysisForm(request.user, request.POST, request.FILES)
        if profile.analyses_this_month >= entitlements.analysis_limit:
            messages.error(request, f"You have used this month's {entitlements.analysis_limit} analysis limit for your {entitlements.code} plan.")
            return redirect("dashboard")
        if form.is_valid():
            if form.cleaned_data["source_type"] == "url" and not entitlements.job_url:
                form.add_error("job_url", "Job URL analysis is available on Plus plans. Paste the advert text on Free.")
                return render_home_workspace(form)
            if form.cleaned_data.get("email_reminder") and not entitlements.deadline_alerts:
                form.add_error("email_reminder", "Deadline email alerts are available on Plus plans.")
                return render_home_workspace(form)
            cv = save_inline_cv(request, form)
            if cv is None:
                return render_home_workspace(form)

            job_description = build_job_description(form)

            valid_job, job_reason = validate_job_description(job_description)
            if not valid_job:
                form.add_error(None, job_reason)
                return render_home_workspace(form)

            job_title = infer_job_title(form, job_description)
            company = infer_company(form, job_description)
            deadline = infer_deadline(form, job_description)
            cv_text = extract_cv_text(cv)
            is_valid_cv, reason = validate_cv_for_analysis(cv_text)
            if not is_valid_cv:
                form.add_error(None, reason)
                return render_home_workspace(form)

            job_role = JobRole.objects.create(
                user=request.user,
                title=job_title,
                company=company,
                description=job_description,
                source_type=form.cleaned_data["source_type"],
                source_url=form.cleaned_data.get("job_url", ""),
                source_file=form.cleaned_data.get("job_file"),
                deadline=deadline,
            )

            details = calculate_score_details(cv_text, job_description, job_title)
            score = details["score"]
            matched = details["matched"]
            missing = details["missing"]
            recommendation = details["recommendation"]
            metrics = {
                "taxonomy": details.get("taxonomy", {}),
                "score_components": details.get("score_components", {}),
                "requirement_groups": details.get("requirement_groups", {}),
                "evidence_map": details.get("evidence_map", []),
                "format_checks": details.get("format_checks", {}),
                "confidence": details.get("confidence", {}),
                "model_version": details.get("model_version", ATS_MODEL_VERSION),
            }

            result = ATSResult.objects.create(
                user=request.user,
                cv=cv,
                job_role=job_role,
                job_title=job_title,
                job_description=job_description,
                score=score,
                matched_skills=", ".join(matched),
                missing_skills=", ".join(missing),
                recommendation=recommendation,
                metrics=metrics,
                status="completed",
            )

            if can_download_generated_cv(request.user):
                GeneratedCV.objects.create(
                    user=request.user,
                    original_cv=cv,
                    ats_result=result,
                    title=f"{cv.title} tailored for {job_title}",
                    content=build_generated_cv(cv, result, matched, missing),
                )
                GeneratedCoverLetter.objects.create(
                    user=request.user,
                    ats_result=result,
                    title=f"Cover letter for {job_title}",
                    content=build_cover_letter(request.user, result, matched, cv_text),
                )
                if build_application_decision(result.score)["can_rewrite"]:
                    create_bullet_suggestions(result, cv_text, matched)

            if job_role.deadline and form.cleaned_data.get("email_reminder"):
                reminder_date = max(timezone.localdate(), job_role.deadline - timedelta(days=2))
                ApplicationReminder.objects.create(
                    user=request.user,
                    job_role=job_role,
                    reminder_date=reminder_date,
                    note=f"Apply before {job_role.deadline:%d %B %Y}.",
                )

            profile.record_analysis()
            if can_download_generated_cv(request.user):
                messages.success(request, "ATS analysis complete. Your tailored CV draft is ready.")
            else:
                messages.success(request, "ATS analysis complete. Your compatibility results are ready.")
            return redirect("ats_result", result_id=result.id)
    else:
        initial = {}
        selected_cv = request.GET.get("cv")
        if selected_cv:
            initial["cv"] = selected_cv
        form = ATSAnalysisForm(request.user, initial=initial)

    return render_home_workspace(form)


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def result_detail(request, result_id):
    if request.user.is_superuser:
        result = get_object_or_404(ATSResult, id=result_id)
    else:
        result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    cv_text = extract_cv_text(result.cv)
    matched = [item.strip() for item in result.matched_skills.split(",") if item.strip()]
    missing = [item.strip() for item in result.missing_skills.split(",") if item.strip()]
    ats_v2 = result.metrics or {}
    if ats_v2.get("model_version") != ATS_MODEL_VERSION:
        current_details = calculate_score_details(cv_text, result.job_description, result.job_title)
        ats_v2 = {
            **ats_v2,
            "taxonomy": current_details.get("taxonomy", {}),
            "score_components": current_details.get("score_components", {}),
            "requirement_groups": current_details.get("requirement_groups", {}),
            "evidence_map": current_details.get("evidence_map", []),
            "format_checks": current_details.get("format_checks", {}),
            "confidence": current_details.get("confidence", {}),
            "model_version": ATS_MODEL_VERSION,
            "historic_score": True,
        }
    if request.method == "POST":
        submitted_item = request.POST.get("truth_gate_item", "")
        truth_gate_anchor = (
            f"truth-gate-item-{submitted_item}"
            if submitted_item.isdigit() and 1 <= int(submitted_item) <= 12
            else "truth-gate"
        )
        truth_gate_url = f"{reverse('ats_result', args=[result.id])}#{truth_gate_anchor}"
        if result.user_id != request.user.id:
            messages.error(request, "Only the candidate who owns this report can confirm its evidence.")
            return redirect(truth_gate_url)
        requirement = re.sub(r"\s+", " ", request.POST.get("requirement", "")).strip().lower()
        action = request.POST.get("evidence_action", "")
        allowed_actions = {"confirmed", "training", "not_have"}
        valid_terms = {item.get("term", "").lower() for item in ats_v2.get("evidence_map", [])}
        if requirement not in valid_terms or action not in allowed_actions:
            messages.error(request, "That evidence confirmation could not be recorded.")
        else:
            stored_metrics = dict(result.metrics or {})
            confirmations = dict(stored_metrics.get("candidate_confirmations") or {})
            confirmations[requirement] = action
            stored_metrics["candidate_confirmations"] = confirmations
            result.metrics = stored_metrics
            result.save(update_fields=["metrics", "updated_at"])
            messages.success(request, f"Your evidence status for “{requirement}” was recorded.")
        return redirect(truth_gate_url)
    ats_v2["candidate_confirmations"] = (result.metrics or {}).get("candidate_confirmations", {})
    for evidence_item in ats_v2.get("evidence_map", []):
        evidence_item["candidate_action"] = ats_v2["candidate_confirmations"].get(evidence_item.get("term", ""))
        evidence_item["display_term"] = humanize_requirement_term(evidence_item.get("term", ""))
    truth_gate_summary = build_truth_gate_summary(ats_v2.get("evidence_map", []))
    reliability_guidance = build_reliability_guidance(
        ats_v2.get("confidence", {}),
        historic_score=bool(ats_v2.get("historic_score")),
    )
    interview_plan = build_interview_plan(ats_v2.get("evidence_map", []), result.job_title)
    breakdown = score_breakdown(result.score, matched, missing, ats_v2)
    match_intelligence = build_match_intelligence(result, cv_text)
    report_insights = build_report_insights(result, matched, missing)
    application_decision = build_application_decision(result.score)
    suggested_cv_review = build_suggested_cv_review(result, matched, missing)
    cv_draft_preview = build_cv_draft_preview(result, matched, missing, cv_text)
    generated_cv = result.generated_cv if hasattr(result, "generated_cv") else None
    structured_cv_draft = resolve_generated_cv_draft(result, generated_cv, cv_text)
    bullet_suggestions = list(result.bullet_suggestions.all())
    bullet_review_summary = {
        "total": len(bullet_suggestions),
        "pending": sum(item.status == "pending" for item in bullet_suggestions),
        "accepted": sum(item.status == "accepted" for item in bullet_suggestions),
        "edited": sum(item.status == "edited" for item in bullet_suggestions),
        "rejected": sum(item.status == "rejected" for item in bullet_suggestions),
        "applied": sum(item.application_is_current for item in bullet_suggestions),
        "ready": sum(item.needs_application for item in bullet_suggestions),
    }
    if hasattr(result, "generated_cover_letter"):
        refreshed_letter = build_cover_letter(request.user, result, matched, cv_text)
        if result.generated_cover_letter.content != refreshed_letter:
            result.generated_cover_letter.content = refreshed_letter
            result.generated_cover_letter.save(update_fields=["content"])
    return render(
        request,
        "ats/result.html",
        {
            "result": result,
            "breakdown": breakdown,
            "match_intelligence": match_intelligence,
            "matched": matched,
            "missing": missing,
            "report_insights": report_insights,
            "application_decision": application_decision,
            "suggested_cv_review": suggested_cv_review,
            "cv_draft_preview": cv_draft_preview,
            "structured_cv_draft": structured_cv_draft,
            "bullet_suggestions": bullet_suggestions,
            "bullet_review_summary": bullet_review_summary,
            "can_download": can_download_generated_cv(request.user),
            "ats_v2": ats_v2,
            "truth_gate_summary": truth_gate_summary,
            "reliability_guidance": reliability_guidance,
            "interview_plan": interview_plan,
        },
    )


@login_required(login_url="login")
@require_http_methods(["POST"])
def start_bullet_review(request, result_id):
    result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    if not can_download_generated_cv(request.user):
        messages.error(request, "Bullet-level CV review is available on the Plus plan.")
        return redirect("ats_result", result_id=result.id)
    if not build_application_decision(result.score)["can_rewrite"]:
        messages.error(request, "Bullet rewriting is unavailable until the CV meets the evidence threshold.")
        return redirect(f"{reverse('ats_result', args=[result.id])}#stage-2-bullet-review")
    suggestions = create_bullet_suggestions(result)
    if suggestions.exists():
        messages.success(request, "Your evidence-grounded bullet review is ready.")
    else:
        messages.info(request, "No complete experience statements were detected for bullet review.")
    return redirect(f"{reverse('ats_result', args=[result.id])}#stage-2-bullet-review")


@login_required(login_url="login")
@require_http_methods(["POST"])
def decide_bullet_suggestion(request, result_id, suggestion_id):
    result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest"
    if not can_download_generated_cv(request.user):
        if wants_json:
            return JsonResponse({"error": "Bullet-level CV review is available on the Plus plan."}, status=403)
        messages.error(request, "Bullet-level CV review is available on the Plus plan.")
        return redirect("ats_result", result_id=result.id)
    suggestion = get_object_or_404(
        CVBulletSuggestion,
        id=suggestion_id,
        ats_result=result,
        user=request.user,
    )
    decision = request.POST.get("decision", "")
    if decision not in {"accepted", "edited", "rejected", "pending"}:
        if wants_json:
            return JsonResponse({"error": "Choose a valid bullet-review decision."}, status=400)
        messages.error(request, "Choose a valid bullet-review decision.")
        return redirect(f"{reverse('ats_result', args=[result.id])}#bullet-{suggestion.id}")

    update_fields = ["status", "updated_at"]
    if decision == "edited":
        edited_text = re.sub(r"\s+", " ", request.POST.get("edited_text", "")).strip()
        if not 20 <= len(edited_text) <= 600:
            if wants_json:
                return JsonResponse(
                    {"error": "Edited bullet wording must contain between 20 and 600 characters."},
                    status=400,
                )
            messages.error(request, "Edited bullet wording must contain between 20 and 600 characters.")
            return redirect(f"{reverse('ats_result', args=[result.id])}#bullet-{suggestion.id}")
        suggestion.edited_text = edited_text
        update_fields.append("edited_text")
    suggestion.status = decision
    suggestion.save(update_fields=update_fields)
    if wants_json:
        suggestions = list(result.bullet_suggestions.all())
        states = [item.status for item in suggestions]
        return JsonResponse({
            "saved": True,
            "suggestion_id": suggestion.id,
            "status": suggestion.status,
            "status_label": suggestion.get_status_display(),
            "display_text": (
                suggestion.edited_text if suggestion.status == "edited"
                else suggestion.proposed_text
            ),
            "needs_application": suggestion.needs_application,
            "application_is_current": suggestion.application_is_current,
            "summary": {
                "total": len(states),
                "pending": states.count("pending"),
                "approved": states.count("accepted") + states.count("edited"),
                "applied": sum(item.application_is_current for item in suggestions),
                "ready": sum(item.needs_application for item in suggestions),
            },
            "message": f"Bullet {suggestion.position + 1} saved.",
        })
    messages.success(request, f"Bullet {suggestion.position + 1} marked {suggestion.get_status_display().lower()}.")
    return redirect(f"{reverse('ats_result', args=[result.id])}#bullet-{suggestion.id}")


@login_required(login_url="login")
@require_http_methods(["POST"])
def apply_bullet_review(request, result_id):
    wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest"
    result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    if not can_download_generated_cv(request.user):
        if wants_json:
            return JsonResponse(
                {"error": "Bullet-level CV review is available on the Plus plan."},
                status=403,
            )
        messages.error(request, "Bullet-level CV review is available on the Plus plan.")
        return redirect("ats_result", result_id=result.id)
    generated_cv = get_object_or_404(GeneratedCV, ats_result=result, user=request.user)
    suggestions = list(result.bullet_suggestions.all())
    ready_suggestions = [item for item in suggestions if item.needs_application]
    if not ready_suggestions:
        if wants_json:
            return JsonResponse(
                {"error": "Accept or edit at least one bullet before applying changes."},
                status=400,
            )
        messages.info(request, "Accept or edit at least one bullet before applying changes.")
        return redirect(f"{reverse('ats_result', args=[result.id])}#stage-2-bullet-review")

    draft = resolve_generated_cv_draft(result, generated_cv)
    rebuilt_content, applied_suggestions = apply_bullet_decisions(
        draft["editable_content"],
        ready_suggestions,
    )
    applied = len(applied_suggestions)
    if not applied:
        if wants_json:
            return JsonResponse(
                {"error": "The approved wording is already applied or its source wording is no longer in the CV draft."},
                status=400,
            )
        messages.error(request, "The selected source wording was not found in the current CV draft.")
        return redirect(f"{reverse('ats_result', args=[result.id])}#stage-2-bullet-review")
    generated_cv.content = rebuilt_content
    generated_cv.save(update_fields=["content"])
    applied_time = timezone.now()
    for suggestion in applied_suggestions:
        if suggestion.status in {"accepted", "edited"}:
            suggestion.applied_text = suggestion.selected_text
            suggestion.applied_at = applied_time
        else:
            suggestion.applied_text = ""
            suggestion.applied_at = None
        suggestion.save(update_fields=["applied_text", "applied_at", "updated_at"])
    message = f"Applied {applied} reviewed bullet change{'s' if applied != 1 else ''} to the CV draft."
    if wants_json:
        refreshed_suggestions = list(result.bullet_suggestions.all())
        refreshed_states = [item.status for item in refreshed_suggestions]
        return JsonResponse({
            "saved": True,
            "applied": applied,
            "applied_ids": [item.id for item in applied_suggestions],
            "current_applied_ids": [
                item.id for item in refreshed_suggestions if item.application_is_current
            ],
            "content": rebuilt_content,
            "summary": {
                "total": len(refreshed_suggestions),
                "pending": refreshed_states.count("pending"),
                "approved": refreshed_states.count("accepted") + refreshed_states.count("edited"),
                "applied": sum(item.application_is_current for item in refreshed_suggestions),
                "ready": sum(item.needs_application for item in refreshed_suggestions),
            },
            "message": message,
        })
    messages.success(request, message)
    return redirect(f"{reverse('ats_result', args=[result.id])}#full-cv-workspace")


@login_required(login_url="login")
def download_generated_cv(request, result_id):
    result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    if not can_download_generated_cv(request.user):
        messages.error(request, "Tailored CV generation is available on the Plus plan.")
        return redirect("ats_result", result_id=result.id)
    generated_cv = get_object_or_404(GeneratedCV, ats_result=result, user=request.user)
    draft = resolve_generated_cv_draft(result, generated_cv)
    response = HttpResponse(draft["editable_content"], content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="mvcv-tailored-cv-{result.id}.txt"'
    return response


@login_required(login_url="login")
@require_http_methods(["POST"])
def save_generated_cv_draft(request, result_id):
    wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest"
    result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    if not can_download_generated_cv(request.user):
        if wants_json:
            return JsonResponse({"error": "Editable CV drafts are available on the Plus plan."}, status=403)
        messages.error(request, "Editable CV drafts are available on the Plus plan.")
        return redirect("ats_result", result_id=result.id)
    if not build_application_decision(result.score)["can_rewrite"]:
        if wants_json:
            return JsonResponse(
                {"error": "This draft cannot be edited until the CV meets the evidence threshold."},
                status=403,
            )
        messages.error(request, "This draft cannot be edited until the CV meets the evidence threshold.")
        return redirect(f"{reverse('ats_result', args=[result.id])}#suggested-cv")

    content = request.POST.get("cv_draft_content", "").strip()
    if not 120 <= len(content) <= 50000:
        if wants_json:
            return JsonResponse(
                {"error": "The CV draft must contain between 120 and 50,000 characters."},
                status=400,
            )
        messages.error(request, "The CV draft must contain between 120 and 50,000 characters.")
        return redirect(f"{reverse('ats_result', args=[result.id])}#full-cv-workspace")

    generated_cv = get_object_or_404(GeneratedCV, ats_result=result, user=request.user)
    generated_cv.content = content
    generated_cv.save(update_fields=["content"])
    if wants_json:
        return JsonResponse({
            "saved": True,
            "saved_at": timezone.localtime().isoformat(),
            "message": "Your CV draft was saved.",
        })
    messages.success(request, "Your edited CV draft was saved.")
    return redirect(f"{reverse('ats_result', args=[result.id])}#full-cv-workspace")


@login_required(login_url="login")
def download_generated_cv_docx(request, result_id):
    result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    if not can_download_generated_cv(request.user):
        messages.error(request, "DOCX CV export is available on the Plus plan.")
        return redirect("ats_result", result_id=result.id)
    if not build_application_decision(result.score)["can_rewrite"]:
        messages.error(request, "DOCX export is unavailable until the CV meets the evidence threshold.")
        return redirect(f"{reverse('ats_result', args=[result.id])}#suggested-cv")

    generated_cv = get_object_or_404(GeneratedCV, ats_result=result, user=request.user)
    draft = resolve_generated_cv_draft(result, generated_cv)
    document_bytes = cv_text_to_docx(draft["editable_content"], title=generated_cv.title)
    response = HttpResponse(
        document_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="mvcv-tailored-cv-{result.id}.docx"'
    return response


@login_required(login_url="login")
def download_cover_letter(request, result_id):
    result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    if not can_download_generated_cv(request.user):
        messages.error(request, "Cover-letter generation is available on the Plus plan.")
        return redirect("ats_result", result_id=result.id)
    letter = get_object_or_404(GeneratedCoverLetter, ats_result=result, user=request.user)
    response = HttpResponse(letter.content, content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="mvcv-cover-letter-{result.id}.txt"'
    return response


@login_required(login_url="login")
def enterprise_bulk_upload(request):
    """Run Enterprise-only bulk ranking after subscription and quota checks."""
    if not user_can_use_enterprise(request.user):
        messages.error(request, "Enterprise bulk analysis is available on the Enterprise plan.")
        return redirect("dashboard")

    if request.method == "POST":
        form = EnterpriseBulkAnalysisForm(request.POST, request.FILES)
        if form.is_valid():
            cv_files = form.cleaned_data["cv_files"]
            if not cv_files:
                form.add_error("cv_files", "Upload at least one CV file.")
                return render(request, "ats/enterprise_bulk.html", {"form": form})
            if not request.user.is_superuser:
                subscription = active_enterprise_subscription(request.user)
                monthly_limit = subscription.plan.monthly_bulk_cv_limit if subscription else 0
                monthly_remaining = max(0, monthly_limit - enterprise_monthly_usage(request.user))
                daily_remaining = max(0, ENTERPRISE_DAILY_LIMIT - enterprise_daily_usage(request.user))
                available = min(monthly_remaining, daily_remaining)
                if len(cv_files) > available:
                    form.add_error(
                        "cv_files",
                        (
                            f"You can scan {available} more CV(s) now. "
                            f"Daily allowance remaining: {daily_remaining} of {ENTERPRISE_DAILY_LIMIT}. "
                            f"Monthly allowance remaining: {monthly_remaining} of {monthly_limit}."
                        ),
                    )
                    return render(request, "ats/enterprise_bulk.html", {"form": form})

            job_description = build_job_description(form)
            valid_job, job_reason = validate_job_description(job_description)
            if not valid_job:
                form.add_error(None, job_reason)
                return render(request, "ats/enterprise_bulk.html", {"form": form})

            job_title = infer_job_title(form, job_description)
            prepared_candidates = []
            invalid_cvs = []
            for uploaded_file in cv_files:
                cv_text = extract_uploaded_cv_text(uploaded_file)
                is_valid_cv, reason = validate_cv_for_analysis(cv_text)
                if not is_valid_cv:
                    invalid_cvs.append(f"{uploaded_file.name}: {reason}")
                    continue
                score, matched, missing, recommendation = calculate_score(cv_text, job_description, job_title)
                prepared_candidates.append((uploaded_file, score, matched, missing, recommendation))

            if invalid_cvs:
                form.add_error("cv_files", "Some uploaded files are not usable CVs. " + " ".join(invalid_cvs[:5]))
                return render(request, "ats/enterprise_bulk.html", {"form": form})

            job_role = JobRole.objects.create(
                user=request.user,
                title=job_title,
                company=infer_company(form, job_description),
                description=job_description,
                source_type=form.cleaned_data["source_type"],
                source_url=form.cleaned_data.get("job_url", ""),
                source_file=form.cleaned_data.get("job_file"),
            )
            batch = EnterpriseBatch.objects.create(
                user=request.user,
                job_role=job_role,
                title=form.cleaned_data["batch_title"],
                notes=form.cleaned_data.get("notes", ""),
            )

            candidate_results = []
            for uploaded_file, score, matched, missing, recommendation in prepared_candidates:
                candidate = EnterpriseCandidateResult(
                    batch=batch,
                    candidate_name=uploaded_file.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title(),
                    score=score,
                    matched_skills=", ".join(matched),
                    missing_skills=", ".join(missing),
                    recommendation=recommendation,
                )
                candidate.cv_file.save(uploaded_file.name, uploaded_file, save=False)
                candidate_results.append(candidate)

            ranked = sorted(candidate_results, key=lambda item: item.score, reverse=True)
            previous_score = None
            current_rank = 0
            for index, candidate in enumerate(ranked, start=1):
                if candidate.score != previous_score:
                    current_rank = index
                    previous_score = candidate.score
                candidate.rank = current_rank
                candidate.save()

            messages.success(request, f"Enterprise report created for {len(ranked)} CV(s).")
            return redirect("enterprise_report", batch_id=batch.id)
    else:
        form = EnterpriseBulkAnalysisForm()

    return render(request, "ats/enterprise_bulk.html", {"form": form})


@login_required(login_url="login")
def enterprise_report(request, batch_id):
    if request.user.is_superuser:
        batch = get_object_or_404(EnterpriseBatch, id=batch_id)
    else:
        batch = get_object_or_404(EnterpriseBatch, id=batch_id, user=request.user)
    results = batch.candidate_results.all()
    candidate_count = results.count()
    top_candidate = results.first()
    aligned_count = results.filter(score__gt=50).count()
    gap_count = results.filter(score__lte=50).count()
    average_score = 0
    if candidate_count:
        average_score = int(sum(result.score for result in results) / candidate_count)
    return render(
        request,
        "ats/enterprise_report.html",
        {
            "batch": batch,
            "results": results,
            "summary": {
                "candidate_count": candidate_count,
                "aligned_count": aligned_count,
                "gap_count": gap_count,
                "average_score": average_score,
                "top_candidate": top_candidate,
            },
        },
    )


@login_required(login_url="login")
def enterprise_report_csv(request, batch_id):
    if request.user.is_superuser:
        batch = get_object_or_404(EnterpriseBatch, id=batch_id)
    else:
        batch = get_object_or_404(EnterpriseBatch, id=batch_id, user=request.user)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="mvcv-enterprise-report-{batch.id}.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Advisory Rank",
        "Candidate",
        "Document Alignment Score",
        "Matched Skills",
        "Missing Evidence",
        "Recommendation",
        "Human Review Required",
    ])
    for result in batch.candidate_results.all():
        writer.writerow([
            result.rank,
            result.candidate_name,
            result.score,
            result.matched_skills,
            result.missing_skills,
            result.recommendation,
            "Yes - do not use this score as an automatic hiring or rejection decision.",
        ])
    return response
