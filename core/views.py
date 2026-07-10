"""
Views for CV analysis MVP:
- home: landing page
- analyse: process CV upload and job description
- results_preview: show analysis results
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
import json
from datetime import timedelta

from .services import ats_engine
from accounts.models import UserProfile
from ats.forms import ATSAnalysisForm
from ats.models import ApplicationReminder, ATSResult, CV, GeneratedCV, JobRole
from ats.views import (
    build_generated_cv,
    build_job_description,
    calculate_score,
    can_download_generated_cv,
    extract_cv_text,
    infer_company,
    infer_deadline,
    infer_job_title,
    save_inline_cv,
    score_breakdown,
    validate_cv_for_analysis,
)


def home(request):
    """
    Product entry page.
    Guests see the same validation workspace shape with a registration CTA.
    Logged-in users can start validation from the home page and submit into ATS analysis.
    """
    context = {
        'is_authenticated': request.user.is_authenticated,
        'result': None,
        'breakdown': None,
        'can_download': False,
    }

    if request.user.is_authenticated:
        profile, _created = UserProfile.objects.get_or_create(user=request.user)
        selected_cv = request.GET.get("cv")
        initial = {"cv": selected_cv} if selected_cv else {}
        form = ATSAnalysisForm(request.user, request.POST or None, request.FILES or None, initial=initial)
        context.update({
            'profile': profile,
            'form': form,
            'has_cvs': CV.objects.filter(user=request.user).exists(),
            'recent_results': ATSResult.objects.filter(user=request.user).select_related("cv", "job_role")[:8],
            'saved_cvs': CV.objects.filter(user=request.user)[:6],
            'generated_cvs': GeneratedCV.objects.filter(user=request.user).select_related("ats_result")[:6],
            'reminders': ApplicationReminder.objects.filter(user=request.user, is_sent=False).select_related("job_role")[:4],
            'is_enterprise': request.user.is_staff or profile.plan == "enterprise",
            'can_download': can_download_generated_cv(request.user),
        })

        if request.method == "POST":
            if not profile.can_run_analysis():
                messages.error(request, f"You have used today's {profile.get_analysis_limit()} analysis limit for your {profile.plan} plan.")
            elif form.is_valid():
                cv = save_inline_cv(request, form)
                if cv is not None:
                    job_description = build_job_description(form)
                    if len(job_description.strip()) < 30:
                        form.add_error(None, "The job description could not be read. Paste the job text directly and try again.")
                    else:
                        cv_text = extract_cv_text(cv)
                        is_valid_cv, reason = validate_cv_for_analysis(cv_text)
                        if not is_valid_cv:
                            form.add_error(None, reason)
                            return render(request, 'landing/home.html', context)

                        job_title = infer_job_title(form, job_description)
                        company = infer_company(form, job_description)
                        deadline = infer_deadline(form, job_description)
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
                            ApplicationReminder.objects.create(
                                user=request.user,
                                job_role=job_role,
                                reminder_date=max(timezone.localdate(), job_role.deadline - timedelta(days=2)),
                                note="Apply before the job deadline.",
                            )
                        profile.record_analysis()
                        messages.success(request, "ATS analysis complete. A tailored CV draft was generated.")
                        context["result"] = result
                        context["breakdown"] = metrics

    return render(request, 'landing/home.html', context)


@require_http_methods(['POST'])
def analyse(request):
    """
    Process CV upload and job description.
    - Extract CV file (PDF, DOCX, TXT)
    - Parse job description
    - Run ATS analysis
    - Store results in session (temporary)
    - Redirect to results preview
    """
    try:
        # Get CV file
        if 'cv_file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No CV file uploaded'
            }, status=400)

        cv_file = request.FILES['cv_file']

        # Validate file extension
        valid_extensions = ['.pdf', '.docx', '.txt']
        file_ext = '.' + cv_file.name.split('.')[-1].lower()
        if file_ext not in valid_extensions:
            return JsonResponse({
                'success': False,
                'error': f'Invalid file format. Supported: PDF, DOCX, TXT'
            }, status=400)

        # Get job description
        jd_text = request.POST.get('job_description', '').strip()
        if not jd_text:
            return JsonResponse({
                'success': False,
                'error': 'Job description is required'
            }, status=400)

        # Extract CV text from upload (no disk storage)
        try:
            cv_text = ats_engine.extract_text_from_upload(cv_file)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Failed to process CV: {str(e)}'
            }, status=400)

        # Run ATS analysis
        analysis_result = ats_engine.analyse(cv_text, jd_text)

        if not analysis_result['success']:
            return JsonResponse({
                'success': False,
                'error': analysis_result['error']
            }, status=400)

        # Store result in session (temporary, cleared before new analysis)
        request.session['analysis_data'] = analysis_result['data']
        request.session.modified = True

        return JsonResponse({
            'success': True,
            'redirect_url': '/results/'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


def results_preview(request):
    """
    Display ATS analysis results.
    Shows comprehensive report with scores, matches, recommendations.
    Guests can register/login to save results.
    """
    # Get analysis data from session
    analysis_data = request.session.get('analysis_data')

    if not analysis_data:
        return redirect('home')

    # Prepare context for template
    context = {
        'analysis': analysis_data,
        'is_authenticated': request.user.is_authenticated,
        'recommendation': get_recommendation(analysis_data['overall_score']),
    }

    return render(request, 'landing/results_preview.html', context)


def get_recommendation(overall_score: int) -> str:
    """Get text recommendation based on overall score."""
    if overall_score >= 80:
        return "Excellent match! Your CV aligns very well with this job description. Consider applying with confidence."
    elif overall_score >= 65:
        return "Good match! Your CV meets most requirements. Consider highlighting relevant skills in your application."
    elif overall_score >= 50:
        return "Moderate match. Your CV covers some key areas. Consider reinforcing missing skills or experience."
    else:
        return "Limited match. Your CV may need significant adjustments to align with this role. Consider gaining more relevant experience or skills."
