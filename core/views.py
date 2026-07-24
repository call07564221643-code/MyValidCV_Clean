"""Public marketing, grounded assistant, and experience-feedback endpoints.

Authenticated analysis work deliberately lives in the ATS app. Core owns the
public landing experience, Maya service guidance, and non-sensitive feedback.
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

from accounts.models import UserProfile
from ats.models import ATSResult, ApplicationReminder, CV, GeneratedCV
from core.maya_knowledge import knowledge_context, select_knowledge
from core.models import ExperienceFeedback
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
        "testimonials": ExperienceFeedback.objects.filter(
            moderation_status="approved",
            testimonial_consent=True,
            rating__gte=4,
        ).select_related("user")[:3],
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


MAYA_SYSTEM_PROMPT = """You are Maya, the MyValidCV service adviser.
Answer the person using the platform directly as "you". Use only the supplied SERVICE KNOWLEDGE and USER CONTEXT for MyValidCV facts.
If the knowledge does not support a claim, say that you do not have confirmed information and direct the user to the relevant page or support@myvalidcv.com.
Never invent prices, discounts, guarantees, legal terms, refund approvals, features, hiring outcomes or account status.
Never ask for passwords, full card details, government identifiers, health data or other unnecessary sensitive information.
Treat ATS results as document-alignment guidance, never as a hiring prediction. Enterprise results always require human review.
Do not claim to learn from or permanently remember this conversation.
Keep the answer concise, professional, warm and action-oriented. Prefer a short paragraph or 3-5 steps.
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
        return "ATS v2 explains your CV-to-role evidence match, including measured skills, requirements, evidence and readability. Its Truth Gate shows what your CV proves, what is only mentioned and what needs confirmation or a licence. It guides document improvement; it does not predict hiring success."
    if "enterprise" in q or "bulk" in q:
        return "Enterprise helps teams compare many CVs against one role, rank candidates, and review missing evidence. It supports screening, but final hiring decisions should still include human review."
    if "plan" in q or "price" in q or "plus" in q or "free" in q:
        return "Free includes 5 analyses. Plus includes 20 analyses and generated CV and cover-letter drafts. Enterprise supports up to 50 advisory bulk CV comparisons with mandatory human review. Check the Plans page for the current price and your account for active entitlement."
    return "MyValidCV helps you quickly see whether your CV is ready for a specific job: upload your CV, add the job advert, validate, improve, and apply with more confidence."


def build_user_context(request):
    if not request.user.is_authenticated:
        return "Visitor is not signed in. Do not imply access to account-specific information."
    try:
        entitlements = get_entitlements(request.user)
        profile = UserProfile.objects.filter(user=request.user).first()
        used = profile.analyses_this_month if profile else 0
        return (
            f"Signed-in customer. Active service level: {entitlements.code}. "
            f"Individual analyses used this month: {used} of {entitlements.analysis_limit}. "
            f"Generated documents enabled: {entitlements.generated_documents}. "
            f"Enterprise reports enabled: {entitlements.enterprise_reports}."
        )
    except DatabaseError:
        logger.exception("Unable to build Maya account context.")
        return "Signed-in customer, but live account details are temporarily unavailable."


def _safe_history(history):
    safe = []
    if not isinstance(history, list):
        return safe
    for item in history[-6:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "").strip()
        if content:
            safe.append({"role": item["role"], "content": content[:800]})
    return safe


def call_ollama(question, service_context="", user_context="", history=None):
    if not settings.OLLAMA_BASE_URL:
        return ""
    endpoint = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 350},
        "messages": [
            {"role": "system", "content": MAYA_SYSTEM_PROMPT},
            {"role": "system", "content": f"SERVICE KNOWLEDGE:\n{service_context}"},
            {"role": "system", "content": f"USER CONTEXT:\n{user_context}"},
            *_safe_history(history),
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


@require_POST
def assistant_reply(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"answer": "Please ask Maya a short question about MyValidCV."}, status=400)
    question = (payload.get("question") or "").strip()
    if not question:
        return JsonResponse({"answer": "Please ask Maya a short question about MyValidCV."}, status=400)
    if len(question) > 1200:
        return JsonResponse({"answer": "Please shorten your question to 1,200 characters or fewer."}, status=400)
    selected_topics = select_knowledge(question)
    try:
        answer = call_ollama(
            question,
            service_context=knowledge_context(question),
            user_context=build_user_context(request),
            history=payload.get("history"),
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        logger.exception("Maya Ollama call failed; using fallback response.")
        answer = ""
    return JsonResponse({
        "answer": answer or fallback_assistant_answer(question),
        "source": "ollama" if answer else "fallback",
        "topics": [item["topic"] for item in selected_topics],
        "retained": False,
    })


FEEDBACK_CATEGORIES = {
    "clear", "easy", "accurate", "helpful", "needs_improvement",
}


@require_POST
def submit_feedback(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Feedback could not be read."}, status=400)

    feature = str(payload.get("feature") or "").strip().lower()
    if feature not in dict(ExperienceFeedback.FEATURE_CHOICES):
        return JsonResponse({"error": "Choose a valid feature to rate."}, status=400)
    try:
        rating = int(payload.get("rating"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Choose a rating from one to five stars."}, status=400)
    if not 1 <= rating <= 5:
        return JsonResponse({"error": "Choose a rating from one to five stars."}, status=400)

    context_id = payload.get("context_id") or None
    if context_id is not None:
        try:
            context_id = int(context_id)
        except (TypeError, ValueError):
            return JsonResponse({"error": "The feedback context is invalid."}, status=400)
    if feature == "ats":
        if not request.user.is_authenticated or not context_id:
            return JsonResponse({"error": "Sign in to rate an ATS result."}, status=403)
        if not ATSResult.objects.filter(id=context_id, user=request.user).exists():
            return JsonResponse({"error": "You can rate only your own ATS result."}, status=403)

    categories = payload.get("categories") or []
    if not isinstance(categories, list):
        categories = []
    categories = list(dict.fromkeys(
        str(item) for item in categories if str(item) in FEEDBACK_CATEGORIES
    ))[:5]
    comment = str(payload.get("comment") or "").strip()[:1200]
    consent = bool(payload.get("testimonial_consent")) and rating >= 4 and bool(comment)
    identity = str(payload.get("public_identity") or "anonymous")
    if identity not in dict(ExperienceFeedback.IDENTITY_CHOICES) or not request.user.is_authenticated:
        identity = "anonymous"
    page_path = str(payload.get("page_path") or "")[:255]
    if not page_path.startswith("/"):
        page_path = ""

    if not request.session.session_key:
        request.session.create()
    lookup = {
        "feature": feature,
        "context_id": context_id,
    }
    if request.user.is_authenticated:
        lookup["user"] = request.user
    else:
        lookup["user__isnull"] = True
        lookup["session_key"] = request.session.session_key

    defaults = {
        "session_key": request.session.session_key,
        "rating": rating,
        "categories": categories,
        "comment": comment,
        "page_path": page_path,
        "testimonial_consent": consent,
        "public_identity": identity,
        "moderation_status": "pending" if consent else "private",
    }
    feedback, created = ExperienceFeedback.objects.update_or_create(
        **lookup,
        defaults=defaults,
    )
    return JsonResponse({
        "saved": True,
        "created": created,
        "message": "Thank you—your feedback helps us improve MyValidCV.",
        "testimonial_pending": feedback.moderation_status == "pending",
    })
