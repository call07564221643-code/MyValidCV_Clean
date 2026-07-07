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
import json

from .services import ats_engine


def home(request):
    """
    Landing page: display CV upload form and job description textarea.
    GET: Show landing page
    """
    if request.method == 'GET':
        # Check if user is logged in
        is_authenticated = request.user.is_authenticated
        return render(request, 'landing/home.html', {
            'is_authenticated': is_authenticated
        })


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
