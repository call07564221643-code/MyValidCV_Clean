from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import CVUploadForm, ATSAnalysisForm
from .models import CV, ATSResult


SKILLS = [
    "python", "django", "sql", "postgresql", "html", "css", "javascript",
    "bootstrap", "api", "git", "github", "excel", "communication",
    "leadership", "project management", "data analysis", "customer service",
]


def calculate_score(job_description):
    job_text = job_description.lower()
    matched = [skill for skill in SKILLS if skill in job_text]
    missing = [skill for skill in SKILLS if skill not in job_text]

    score = int((len(matched) / len(SKILLS)) * 100)

    recommendation = (
        "Your CV should clearly show the matched skills and add evidence for missing skills where truthful."
    )

    return score, matched, missing, recommendation


@login_required(login_url="login")
def upload_cv(request):
    if request.method == "POST":
        form = CVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            cv = form.save(commit=False)
            cv.user = request.user
            cv.save()
            messages.success(request, "CV uploaded successfully.")
            return redirect("ats_analyse")
    else:
        form = CVUploadForm()

    return render(request, "ats/upload_cv.html", {"form": form})


@login_required(login_url="login")
def analyse_cv(request):
    if request.method == "POST":
        form = ATSAnalysisForm(request.user, request.POST)
        if form.is_valid():
            cv = form.cleaned_data["cv"]
            job_title = form.cleaned_data["job_title"]
            job_description = form.cleaned_data["job_description"]

            score, matched, missing, recommendation = calculate_score(job_description)

            result = ATSResult.objects.create(
                user=request.user,
                cv=cv,
                job_title=job_title,
                job_description=job_description,
                score=score,
                matched_skills=", ".join(matched),
                missing_skills=", ".join(missing),
                recommendation=recommendation,
            )

            return redirect("ats_result", result_id=result.id)
    else:
        form = ATSAnalysisForm(request.user)

    return render(request, "ats/analyse.html", {"form": form})


@login_required(login_url="login")
def result_detail(request, result_id):
    result = get_object_or_404(ATSResult, id=result_id, user=request.user)
    return render(request, "ats/result.html", {"result": result})