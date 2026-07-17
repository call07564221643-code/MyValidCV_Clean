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
from .scoring import calculate_score, calculate_score_details
from subscriptions.services import get_active_subscription, get_entitlements


APPLY_STRONG_THRESHOLD = 75
APPLY_MINIMUM_THRESHOLD = 55


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


def build_generated_cv(cv, result, matched, missing):
    cv_text = extract_cv_text(cv)
    matched_text = ", ".join(matched) if matched else "role-relevant strengths already present in your CV"
    missing_text = ", ".join(missing) if missing else "No major missing skills detected"
    decision = build_application_decision(result.score)
    if not decision["can_rewrite"]:
        return f"""Tailored CV Draft for {result.job_title}

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
    return f"""Tailored CV Draft for {result.job_title}

Source CV: {cv.title}
ATS Match Score: {result.score}%

Application Decision
{decision["message"]}

Change Legend
[GREEN] Rewording only: same evidence, clearer ATS/recruiter wording.
[YELLOW] Window-dressed wording: stronger presentation of existing evidence; do not invent facts.
[RED] Evidence gap: CV owner must be ready with training, licence, certification, or truthful proof before claiming it.

Professional Summary
[GREEN] Candidate with experience relevant to {result.job_title}, with visible evidence in {matched_text}. The profile should keep the strongest role-matched evidence in the first third of the CV.

Key Skills to Emphasise
[GREEN] {matched_text}

Skills or Evidence to Add Truthfully
[RED] {missing_text}

Recommended CV Changes
1. [GREEN] Move the most relevant matched skills into the top third of the CV.
2. [YELLOW] Add measurable examples beside each matched skill using evidence already in the CV or real work history.
3. [RED] Add missing skills only when the candidate genuinely has experience, training, licence, or certification.
4. [YELLOW] Remove or shorten content that does not support this specific role.

Original CV Content Reference
{cv_text[:2500]}
"""


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
        return "your team"
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

I am applying for {role_title}. Your advert appears to prioritise {strengths_text}, and my CV has been tailored to make this evidence easier to identify.

The strongest CV evidence for this application is: {evidence_text}

I would welcome the opportunity to discuss how this experience can support {company}. I have kept this application focused on evidence already present in my CV and would be pleased to expand on it at interview.

Thank you for considering my application.

Yours sincerely,
{name}

Draft note: personalise the greeting, company name, and any figures before sending.
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
            "label": "Worth applying",
            "threshold": APPLY_STRONG_THRESHOLD,
            "can_rewrite": True,
            "message": (
                f"It is worth applying for this job role. Your success signal is above {APPLY_STRONG_THRESHOLD}%, "
                "which means the CV shows enough role evidence to justify a focused application."
            ),
        }
    if score >= APPLY_MINIMUM_THRESHOLD:
        return {
            "status": "improve",
            "label": "Possible, but improve first",
            "threshold": APPLY_MINIMUM_THRESHOLD,
            "can_rewrite": True,
            "message": (
                f"You may have a chance, but improve the CV before applying. The score is above the minimum "
                f"{APPLY_MINIMUM_THRESHOLD}% review line, but below the stronger shortlist signal of {APPLY_STRONG_THRESHOLD}%."
            ),
        }
    return {
        "status": "low",
        "label": "Low chance for this role",
        "threshold": APPLY_MINIMUM_THRESHOLD,
        "can_rewrite": False,
        "message": (
            "You do not currently have a strong chance with this job role because the CV does not meet the minimum "
            f"{APPLY_MINIMUM_THRESHOLD}% role-fit standard used by MyValidCV for a credible application review."
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
    matched_text = ", ".join(matched[:6]) if matched else "role-relevant evidence"
    missing_text = ", ".join(missing[:5]) if missing else "no major evidence gaps"
    safe_role = result.job_title or "Target Role"
    evidence_lines = extract_cv_evidence_lines(cv_text, matched, limit=4)
    if evidence_lines:
        summary_evidence = evidence_lines[0]
    else:
        summary_evidence = f"Evidence aligned to {matched_text} should be visible in the CV before this draft is used."
    return {
        "candidate_name": result.cv.title,
        "target_role": safe_role,
        "summary": (
            f"Candidate targeting {safe_role}, with CV evidence connected to {matched_text}. {summary_evidence}"
        ),
        "skills": matched[:8] or ["Add verified role-specific skills from your CV evidence"],
        "experience_bullets": evidence_lines or [
            "Relevant experience was not clearly detected in the source CV text.",
            "A stronger tailored CV cannot be produced until the CV includes truthful role evidence.",
        ],
        "education_note": (
            f"Not evidenced strongly enough in the source CV: {missing_text}."
        ),
    }


def build_report_insights(result, matched, missing):
    if result.score >= 80:
        readiness_label = "Ready to apply"
        readiness_class = "ready"
        recruiter_view = "Recruiters are likely to see a clear role match if the strongest evidence stays near the top."
        weakness_summary = "Main risk: strong evidence may be buried, generic, or not measurable."
    elif result.score >= 55:
        readiness_label = "Needs work before applying"
        readiness_class = "work"
        recruiter_view = "Recruiters may see partial fit, but the match is not immediate enough."
        weakness_summary = "Main risk: relevant experience is present but not visible or proven enough."
    else:
        readiness_label = "High risk of being screened out"
        readiness_class = "risk"
        recruiter_view = "Recruiters may not see enough role fit quickly."
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

            details = calculate_score_details(cv_text, job_description, job_title)
            score = details["score"]
            matched = details["matched"]
            missing = details["missing"]
            recommendation = details["recommendation"]
            metrics = score_breakdown(score, matched, missing)
            metrics["taxonomy"] = details.get("taxonomy", {})
            metrics["score_components"] = details.get("score_components", {})

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
    cv_text = extract_cv_text(result.cv)
    matched = [item.strip() for item in result.matched_skills.split(",") if item.strip()]
    missing = [item.strip() for item in result.missing_skills.split(",") if item.strip()]
    breakdown = score_breakdown(result.score, matched, missing)
    match_intelligence = build_match_intelligence(result, cv_text)
    report_insights = build_report_insights(result, matched, missing)
    application_decision = build_application_decision(result.score)
    suggested_cv_review = build_suggested_cv_review(result, matched, missing)
    cv_draft_preview = build_cv_draft_preview(result, matched, missing, cv_text)
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
