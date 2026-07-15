import re
import urllib.request
import csv
import ipaddress
import socket
from datetime import datetime, timedelta
from urllib.parse import urlparse

from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .forms import ATSAnalysisForm, CVUploadForm, EnterpriseBulkAnalysisForm
from .models import (
    ApplicationReminder,
    ATSResult,
    CV,
    CVStorage,
    EnterpriseBatch,
    EnterpriseCandidateResult,
    GeneratedCoverLetter,
    GeneratedCV,
    JobRole,
)
from accounts.models import UserProfile
from .engine import ats_engine
from subscriptions.services import get_active_subscription, get_entitlements


SKILLS = [
    "python", "django", "sql", "postgresql", "html", "css", "javascript",
    "bootstrap", "api", "git", "github", "excel", "communication",
    "leadership", "project management", "data analysis", "customer service",
    "administration", "scheduling", "records management", "data entry",
    "reception", "office management", "document control", "compliance",
    "airport operations", "passenger service", "aviation", "boarding",
    "dentistry", "dental", "patient care", "oral health", "treatment planning",
    "radiography", "x-ray", "infection control", "clinical assessment",
]

STOP_WORDS = {
    "about", "above", "after", "again", "against", "also", "and", "any",
    "are", "because", "been", "before", "being", "below", "between", "both",
    "but", "can", "candidate", "company", "control", "could", "day", "description",
    "did", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "here", "hers", "him", "his",
    "how", "into", "its", "job", "just", "more", "most", "must", "not",
    "now", "off", "once", "only", "other", "our", "out", "over", "own",
    "position", "requirements", "responsibilities", "role", "same", "service", "she",
    "should", "some", "such", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "this", "those", "through", "too", "under",
    "until", "very", "was", "were", "what", "when", "where", "which", "while",
    "who", "will", "with", "work", "would", "you", "your",
}

ROLE_FAMILIES = {
    "dental": [
        "dentist", "dentistry", "dental", "oral", "clinic", "clinical",
        "patient", "patients", "hygienist", "nurse", "radiography", "x-ray",
        "xray", "treatment", "treatments", "diagnosis", "restorative",
        "periodontal", "endodontic", "extraction", "crown", "fillings",
        "infection control", "gdc", "nhs",
    ],
    "administration": [
        "admin", "administrator", "administration", "office", "reception",
        "records", "filing", "scheduling", "diary", "appointments", "email",
        "telephone", "correspondence", "document", "documents", "data entry",
        "excel", "reporting", "customer service", "coordination",
    ],
    "aviation": [
        "airport", "aviation", "airline", "terminal", "passenger",
        "passengers", "boarding", "flight", "flights", "airside", "landside",
        "baggage", "security", "check-in", "gate", "crew",
    ],
    "technology": [
        "developer", "engineer", "software", "python", "django", "api",
        "database", "sql", "cloud", "frontend", "backend", "testing",
        "deployment", "github", "git",
    ],
}


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
    return f"Job advert URL: {form.cleaned_data['job_url']}. Add the full job text if this page cannot be fetched."


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

    return "Imported Job Role"


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


def calculate_score(cv_text, job_description):
    cv_lower = (cv_text or "").lower()
    job_lower = (job_description or "").lower()

    jd_skills = _extract_known_terms(job_lower, SKILLS)
    cv_skills = _extract_known_terms(cv_lower, SKILLS)
    matched_skills = [skill for skill in jd_skills if skill in cv_skills]
    missing_skills = [skill for skill in jd_skills if skill not in cv_skills]

    jd_role_terms = _extract_role_terms(job_lower)
    cv_role_terms = _extract_role_terms(cv_lower)
    matched_role_terms = [term for term in jd_role_terms if term in cv_role_terms]
    missing_role_terms = [term for term in jd_role_terms if term not in cv_role_terms]

    jd_keywords = _extract_relevant_keywords(job_lower)
    cv_keywords = _extract_relevant_keywords(cv_lower)
    matched_keywords = [term for term in jd_keywords if term in cv_keywords]
    missing_keywords = [term for term in jd_keywords if term not in cv_keywords]

    skills_score = _ratio_score(matched_skills, jd_skills)
    role_score = _ratio_score(matched_role_terms, jd_role_terms)
    keyword_score = _ratio_score(matched_keywords, jd_keywords[:12])
    evidence_score = _evidence_score(cv_lower)

    if not jd_skills and jd_role_terms:
        skills_score = role_score
    if not jd_role_terms:
        role_score = min(70, keyword_score)

    score = int(
        (skills_score * 0.30)
        + (role_score * 0.35)
        + (keyword_score * 0.25)
        + (evidence_score * 0.10)
    )

    if jd_role_terms and role_score < 20:
        score = min(score, 45)
    elif jd_role_terms and role_score < 40:
        score = min(score, 59)
    elif missing_role_terms and len(missing_role_terms) >= max(3, len(jd_role_terms) // 2):
        score = min(score, 74)

    matched = _unique_keep_order(matched_role_terms + matched_skills + matched_keywords[:4])
    missing = _unique_keep_order(missing_role_terms[:6] + missing_skills[:6] + missing_keywords[:4])

    if jd_role_terms and role_score < 20:
        recommendation = (
            "High role mismatch. The CV may be well written, but recruiters are unlikely to see enough evidence "
            "for this specific profession. Add truthful role-specific experience before applying."
        )
    elif score >= 80:
        recommendation = "Strong role fit. Keep the top third focused on the matched requirements and measurable evidence."
    elif score >= 55:
        recommendation = (
            "Partial role fit. Improve the CV by moving matched evidence higher and adding truthful proof for the missing requirements."
        )
    else:
        recommendation = (
            "Weak match for this job. The CV needs clearer role-specific skills, keywords, and evidence before applying."
        )

    return score, matched, missing, recommendation


def _extract_known_terms(text, terms):
    found = []
    for term in terms:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        if re.search(pattern, text):
            found.append(term)
    return _unique_keep_order(found)


def _extract_role_terms(text):
    terms = []
    for family_terms in ROLE_FAMILIES.values():
        terms.extend(_extract_known_terms(text, family_terms))
    return _unique_keep_order(terms)


def _extract_relevant_keywords(text, limit=20):
    words = re.findall(r"\b[a-z][a-z+-]{2,}\b", text)
    counts = {}
    for word in words:
        if word in STOP_WORDS or len(word) < 4:
            continue
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _count in ranked[:limit]]


def _ratio_score(matched, required):
    if not required:
        return 0
    return min(100, int((len(matched) / len(required)) * 100))


def _evidence_score(text):
    evidence_markers = [
        "achieved", "coordinated", "delivered", "improved", "increased",
        "managed", "reduced", "reported", "resolved", "supported", "trained",
    ]
    marker_hits = sum(1 for marker in evidence_markers if marker in text)
    number_hits = len(re.findall(r"\b\d+%?|\b\d+\+?\s+years?\b", text))
    return min(100, 45 + marker_hits * 7 + number_hits * 5)


def _unique_keep_order(items):
    seen = set()
    unique = []
    for item in items:
        normalized = item.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(item)
    return unique


def build_generated_cv(cv, result, matched, missing):
    cv_text = extract_cv_text(cv)
    matched_text = ", ".join(matched) if matched else "role-relevant strengths already present in your CV"
    missing_text = ", ".join(missing) if missing else "No major missing skills detected"
    return f"""Tailored CV Draft for {result.job_title}

Source CV: {cv.title}
ATS Match Score: {result.score}%

Professional Summary
Candidate with experience aligned to {result.job_title}. This version should highlight {matched_text} and keep the profile focused on evidence that matches the job advert.

Key Skills to Emphasise
{matched_text}

Skills or Evidence to Add Truthfully
{missing_text}

Recommended CV Changes
1. Move the most relevant skills into the top third of the CV.
2. Add measurable examples beside each matched skill.
3. If you have experience with the missing skills, add truthful project or work evidence.
4. Remove or shorten content that does not support this specific role.

Original CV Content Reference
{cv_text[:2500]}
"""


def build_cover_letter(user, result, matched):
    name = user.get_full_name().strip() or user.username
    company = result.job_role.company or "Hiring Manager"
    strengths = ", ".join(matched[:4]) if matched else "the relevant experience described in my CV"
    return f"""Dear Hiring Manager,

I am applying for the {result.job_title} position at {company}. My CV demonstrates experience relevant to this opportunity, particularly {strengths}.

I am interested in this role because it offers the opportunity to apply these strengths to the priorities described in the job advert. I would welcome the chance to discuss the evidence in my CV and how I could contribute to your team.

Thank you for considering my application.

Yours sincerely,
{name}

Draft note: personalise this letter and verify every statement before sending.
"""


def can_download_generated_cv(user):
    """Authorise individual paid generation for Plus/Professional accounts."""
    return get_entitlements(user).generated_documents


def score_breakdown(score, matched, missing):
    matched_count = len(matched)
    missing_count = len(missing)
    skills_score = score
    keyword_score = min(100, max(35, score + 6 if matched_count else score))
    experience_score = min(100, max(30, score + 10 if matched_count >= 2 else score - 5))
    format_score = 86
    return {
        "skills": skills_score,
        "keywords": keyword_score,
        "experience": experience_score,
        "format": format_score,
        "total": score,
        "matched_count": matched_count,
        "missing_count": missing_count,
    }


def build_report_insights(result, matched, missing):
    if result.score >= 80:
        readiness_label = "Ready to apply"
        readiness_class = "ready"
        recruiter_view = (
            "Recruiters are likely to see a clear role match. Before applying, make sure the strongest evidence "
            "is visible in the top third of the CV."
        )
        weakness_summary = (
            "The CV is not weak overall, but it may still lose interviews if the best achievements are buried, "
            "generic, or not measurable."
        )
    elif result.score >= 55:
        readiness_label = "Needs work before applying"
        readiness_class = "work"
        recruiter_view = (
            "Recruiters may see partial fit, but they may need to work too hard to connect your CV to this role."
        )
        weakness_summary = (
            "The CV likely has relevant experience, but some requirements are not visible enough or lack clear proof."
        )
    else:
        readiness_label = "High risk of being screened out"
        readiness_class = "risk"
        recruiter_view = (
            "Recruiters may not see enough role fit quickly, especially if the missing skills are important in the advert."
        )
        weakness_summary = (
            "The CV is weak for this specific role because the visible evidence does not yet match enough of the job requirements."
        )

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
                return render(request, "ats/upload_cv.html", {"form": form, "profile": profile, "cv_count": cv_count})
            cv = form.save(commit=False)
            cv.user = request.user
            populate_cv_metadata(cv, form.cleaned_data["file"], validation_status="valid", validation_notes="Passed CV readiness validation.")
            cv.save()
            refresh_cv_storage(request.user)
            messages.success(request, "CV uploaded successfully.")
            return redirect(f"{reverse('ats_analyse')}?cv={cv.id}")
    else:
        form = CVUploadForm()

    return render(request, "ats/upload_cv.html", {"form": form, "profile": profile, "cv_count": cv_count})


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

            if len(job_description.strip()) < 30:
                form.add_error(None, "The job description could not be read. Paste the job text directly and try again.")
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

            score, matched, missing, recommendation = calculate_score(cv_text, job_description)
            metrics = score_breakdown(score, matched, missing)

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
                    content=build_cover_letter(request.user, result, matched),
                )

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
def result_detail(request, result_id):
    result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    matched = [item.strip() for item in result.matched_skills.split(",") if item.strip()]
    missing = [item.strip() for item in result.missing_skills.split(",") if item.strip()]
    breakdown = score_breakdown(result.score, matched, missing)
    report_insights = build_report_insights(result, matched, missing)
    return render(
        request,
        "ats/result.html",
        {
            "result": result,
            "breakdown": breakdown,
            "matched": matched,
            "missing": missing,
            "report_insights": report_insights,
            "can_download": can_download_generated_cv(request.user),
        },
    )


@login_required(login_url="login")
def download_generated_cv(request, result_id):
    result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    if not can_download_generated_cv(request.user):
        messages.error(request, "Tailored CV generation is available on the Plus plan.")
        return redirect("ats_result", result_id=result.id)
    generated_cv = get_object_or_404(GeneratedCV, ats_result=result, user=request.user)
    response = HttpResponse(generated_cv.content, content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="mvcv-tailored-cv-{result.id}.txt"'
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
                remaining = max(0, monthly_limit - enterprise_monthly_usage(request.user))
                if len(cv_files) > remaining:
                    form.add_error(
                        "cv_files",
                        f"Your Enterprise plan has {remaining} of {monthly_limit} monthly CV scans remaining.",
                    )
                    return render(request, "ats/enterprise_bulk.html", {"form": form})

            job_description = build_job_description(form)
            if len(job_description.strip()) < 30:
                form.add_error(None, "The job role could not be read. Paste the job text directly and try again.")
                return render(request, "ats/enterprise_bulk.html", {"form": form})

            prepared_candidates = []
            invalid_cvs = []
            for uploaded_file in cv_files:
                cv_text = extract_uploaded_cv_text(uploaded_file)
                is_valid_cv, reason = validate_cv_for_analysis(cv_text)
                if not is_valid_cv:
                    invalid_cvs.append(f"{uploaded_file.name}: {reason}")
                    continue
                score, matched, missing, recommendation = calculate_score(cv_text, job_description)
                prepared_candidates.append((uploaded_file, score, matched, missing, recommendation))

            if invalid_cvs:
                form.add_error("cv_files", "Some uploaded files are not usable CVs. " + " ".join(invalid_cvs[:5]))
                return render(request, "ats/enterprise_bulk.html", {"form": form})

            job_role = JobRole.objects.create(
                user=request.user,
                title=infer_job_title(form, job_description),
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
            for index, candidate in enumerate(ranked, start=1):
                candidate.rank = index
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
    shortlisted_count = results.filter(score__gte=80).count()
    review_count = results.filter(score__gte=60, score__lt=80).count()
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
                "shortlisted_count": shortlisted_count,
                "review_count": review_count,
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
    writer.writerow(["Rank", "Candidate", "Score", "Matched Skills", "Missing Skills", "Recommendation"])
    for result in batch.candidate_results.all():
        writer.writerow([
            result.rank,
            result.candidate_name,
            result.score,
            result.matched_skills,
            result.missing_skills,
            result.recommendation,
        ])
    return response
