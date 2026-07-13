import re
import urllib.request
import csv
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
    GeneratedCV,
    JobRole,
)
from accounts.models import UserProfile
from core.services import ats_engine


SKILLS = [
    "python", "django", "sql", "postgresql", "html", "css", "javascript",
    "bootstrap", "api", "git", "github", "excel", "communication",
    "leadership", "project management", "data analysis", "customer service",
]


def get_user_profile(user):
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return profile


def storage_limit_for_user(user):
    profile = get_user_profile(user)
    limits = {
        "free": 5 * 1024 * 1024,
        "plus": 50 * 1024 * 1024,
        "professional": 50 * 1024 * 1024,
        "enterprise": 1024 * 1024 * 1024,
    }
    return limits.get(profile.plan, limits["free"])


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
    cv.validation_status = validation_status
    cv.is_valid_cv = validation_status == "valid"
    cv.validation_notes = validation_notes
    return cv


def refresh_cv_storage(user):
    storage = get_user_cv_storage(user)
    storage.refresh_used_storage()
    return storage


def extract_cv_text(cv):
    """Extract text from a stored CV file, falling back to the title."""
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


def fetch_job_url_text(url):
    """Best-effort job advert fetch for simple public pages."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=8) as response:
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

    patterns = [
        r"\b(?:deadline|closing date|apply by)\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4})",
        r"\b(?:deadline|closing date|apply by)\s*[:\-]?\s*(\d{4}-\d{1,2}-\d{1,2})",
        r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
        r"\b(\d{4}-\d{1,2}-\d{1,2})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, job_description, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1)
        for date_format in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
    return None


def user_can_use_enterprise(user):
    return user.is_superuser or get_user_profile(user).plan == "enterprise"


def calculate_score(cv_text, job_description):
    cv_text = cv_text.lower()
    job_text = job_description.lower()
    required_skills = [skill for skill in SKILLS if skill in job_text]

    if not required_skills:
        required_skills = [skill for skill in SKILLS if skill in cv_text]

    matched = [skill for skill in required_skills if skill in cv_text]
    missing = [skill for skill in required_skills if skill not in cv_text]

    score = int((len(matched) / len(required_skills)) * 100) if required_skills else 0

    if missing:
        recommendation = (
            "Your CV matches some requirements. Add truthful evidence for the missing skills if you have them."
        )
    elif matched:
        recommendation = "Strong match. Keep the CV focused on measurable outcomes for these role requirements."
    else:
        recommendation = "Add more role-specific skills and evidence before applying for this position."

    return score, matched, missing, recommendation


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


def can_download_generated_cv(user):
    return user.is_superuser or get_user_profile(user).plan in ("plus", "professional", "enterprise")


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
    elif result.score >= 60:
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

    profile = get_user_profile(request.user)
    cv_count = CV.objects.filter(user=request.user).count()
    if cv_count >= profile.get_cv_limit():
        form.add_error("cv_file", f"Your {profile.plan} plan has reached the saved CV limit.")
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
    cv_count = CV.objects.filter(user=request.user).count()
    if request.method != "POST" and cv_count >= profile.get_cv_limit():
        messages.warning(request, f"Your {profile.plan} plan allows {profile.get_cv_limit()} saved CV(s). Upgrade to save more.")

    if request.method == "POST":
        form = CVUploadForm(request.POST, request.FILES)
        if cv_count >= profile.get_cv_limit():
            messages.error(request, f"Your {profile.plan} plan has reached the saved CV limit.")
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
            return redirect(f"{reverse('home')}?cv={cv.id}#composer")
    else:
        form = CVUploadForm()

    return render(request, "ats/upload_cv.html", {"form": form, "profile": profile, "cv_count": cv_count})


@login_required(login_url="login")
def analyse_cv(request):
    if request.method == "GET":
        target = reverse("home")
        query_string = request.META.get("QUERY_STRING")
        if query_string:
            target = f"{target}?{query_string}"
        return redirect(f"{target}#composer")

    user_cvs = CV.objects.filter(user=request.user)
    profile = get_user_profile(request.user)
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
            "is_enterprise": request.user.is_superuser or profile.plan == "enterprise",
        }

    if request.method == "POST":
        form = ATSAnalysisForm(request.user, request.POST, request.FILES)
        if not profile.can_run_analysis():
            messages.error(request, f"You have used today's {profile.get_analysis_limit()} analysis limit for your {profile.plan} plan.")
            return redirect("dashboard")
        if form.is_valid():
            cv = save_inline_cv(request, form)
            if cv is None:
                return render(request, "ats/analyse.html", workspace_context(form))

            job_description = build_job_description(form)

            if len(job_description.strip()) < 30:
                form.add_error(None, "The job description could not be read. Paste the job text directly and try again.")
                return render(request, "ats/analyse.html", workspace_context(form))

            job_title = infer_job_title(form, job_description)
            company = infer_company(form, job_description)
            deadline = infer_deadline(form, job_description)
            cv_text = extract_cv_text(cv)
            is_valid_cv, reason = validate_cv_for_analysis(cv_text)
            if not is_valid_cv:
                form.add_error(None, reason)
                return render(request, "ats/analyse.html", workspace_context(form))

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

            GeneratedCV.objects.create(
                user=request.user,
                original_cv=cv,
                ats_result=result,
                title=f"{cv.title} tailored for {job_title}",
                content=build_generated_cv(cv, result, matched, missing),
            )

            if job_role.deadline:
                reminder_date = max(timezone.localdate(), job_role.deadline - timedelta(days=2))
                ApplicationReminder.objects.create(
                    user=request.user,
                    job_role=job_role,
                    reminder_date=reminder_date,
                    note="Apply before the job deadline.",
                )

            profile.record_analysis()
            messages.success(request, "ATS analysis complete. A tailored CV draft was generated.")
            inline_result = result
            breakdown = score_breakdown(score, matched, missing)
            user_cvs = CV.objects.filter(user=request.user)
    else:
        initial = {}
        selected_cv = request.GET.get("cv")
        if selected_cv:
            initial["cv"] = selected_cv
        form = ATSAnalysisForm(request.user, initial=initial)

    return render(request, "ats/analyse.html", workspace_context(form))


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
        messages.error(request, "Download is available on Plus and Enterprise plans. You can still view the suggested CV draft here.")
        return redirect("ats_result", result_id=result.id)
    generated_cv = get_object_or_404(GeneratedCV, ats_result=result, user=request.user)
    response = HttpResponse(generated_cv.content, content_type="text/plain")
    response["Content-Disposition"] = f'attachment; filename="mvcv-tailored-cv-{result.id}.txt"'
    return response


@login_required(login_url="login")
def enterprise_bulk_upload(request):
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
