"""Public marketing entry point.

Authenticated product work deliberately lives in the ATS app. Keeping the
landing page read-only avoids a second analysis implementation bypassing the
central entitlement and ownership checks.
"""

import logging

from django.db import DatabaseError
from django.shortcuts import render

from accounts.models import UserProfile
from ats.models import ATSResult, ApplicationReminder, CV, GeneratedCV
from subscriptions.services import get_entitlements


logger = logging.getLogger(__name__)


def home(request):
    """Render marketing content plus a safe summary for logged-in customers."""
    context = {
        "is_authenticated": request.user.is_authenticated,
        "workspace_available": True,
        "result": None,
        "breakdown": None,
        "can_download": False,
    }
    if not request.user.is_authenticated:
        return render(request, "landing/home.html", context)

    try:
        profile, _created = UserProfile.objects.get_or_create(user=request.user)
        entitlements = get_entitlements(request.user)
        context.update({
            "profile": profile,
            "has_cvs": CV.objects.filter(user=request.user).exists(),
            "recent_results": ATSResult.objects.filter(user=request.user).select_related("cv", "job_role")[:8],
            "saved_cvs": CV.objects.filter(user=request.user)[:6],
            "generated_cvs": GeneratedCV.objects.filter(user=request.user).select_related("ats_result")[:6],
            "reminders": ApplicationReminder.objects.filter(
                user=request.user,
                is_sent=False,
            ).select_related("job_role")[:4],
            "is_enterprise": entitlements.enterprise_reports,
            "can_download": entitlements.generated_documents,
        })
    except DatabaseError:
        logger.exception("Unable to load authenticated homepage summary.")
        context.update({"workspace_available": False, "profile": None})
    return render(request, "landing/home.html", context)
