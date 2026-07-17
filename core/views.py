"""Public marketing entry point.

Authenticated product work deliberately lives in the ATS app. Keeping the
landing page read-only avoids a second analysis implementation bypassing the
central entitlement and ownership checks.
"""

import logging
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

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


MAYA_SYSTEM_PROMPT = """You are Maya, the friendly customer-service assistant for MyValidCV.
Your job is to help visitors understand the service and move confidently from cold lead to registered user.
Explain MyValidCV simply: Upload CV -> Add job advert -> Validate -> Improve -> Apply.
You may explain reports, ATS match, suggested CV drafts, cover letters, plans, payments, refunds, discounts, terms, privacy and enterprise bulk reports.
Never invent discounts, guarantees, legal terms, refund approvals, or hiring outcomes.
For payments/refunds/account-specific issues, direct users to support@myvalidcv.com and the Terms/Privacy/Use of Data links.
Keep answers concise, professional, warm, and conversion-focused.
"""


def fallback_assistant_answer(question):
    q = question.lower()
    if "discount" in q or "offer" in q or "coupon" in q:
        return "When an official MyValidCV discount is available, it will be shown on the Plans page or shared by support. I can explain plan value, but I cannot promise an unannounced discount."
    if "refund" in q or "cancel" in q or "terms" in q or "privacy" in q:
        return "Refunds and cancellations depend on the plan terms, usage, and timing. Please review the Terms, Privacy, and Use of Data links in the footer, and contact support@myvalidcv.com for account-specific help."
    if "payment" in q or "pay" in q or "card" in q or "receipt" in q:
        return "Choose a plan, click Pay Now, and complete secure checkout. After payment, MyValidCV confirms the payment and updates your plan. Card details are handled by the payment provider."
    if "report" in q or "ats" in q or "score" in q:
        return "The report explains role fit, matched evidence, missing requirements, must-have gaps, and recruiter-facing recommendations. Focus on why the CV is weak and what evidence improves interview chance."
    if "enterprise" in q or "bulk" in q:
        return "Enterprise helps teams compare many CVs against one role, rank candidates, and review missing evidence. It supports screening, but final hiring decisions should still include human review."
    if "plan" in q or "price" in q or "plus" in q or "free" in q:
        return "Free is best for trying MyValidCV. Plus is for active job seekers who need more validations and downloadable drafts. Enterprise is for hiring teams using bulk CV reports."
    return "MyValidCV helps you quickly see whether your CV is ready for a specific job: upload your CV, add the job advert, validate, improve, and apply with more confidence."


def call_ollama(question):
    if not settings.OLLAMA_BASE_URL:
        return ""
    endpoint = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": MAYA_SYSTEM_PROMPT},
            {"role": "user", "content": question[:1200]},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if settings.OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=settings.OLLAMA_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))
    return (data.get("message") or {}).get("content", "").strip()


@csrf_exempt
@require_POST
def assistant_reply(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"answer": "Please ask Maya a short question about MyValidCV."}, status=400)
    question = (payload.get("question") or "").strip()
    if not question:
        return JsonResponse({"answer": "Please ask Maya a short question about MyValidCV."}, status=400)
    try:
        answer = call_ollama(question)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        logger.exception("Maya Ollama call failed; using fallback response.")
        answer = ""
    return JsonResponse({
        "answer": answer or fallback_assistant_answer(question),
        "source": "ollama" if answer else "fallback",
    })
