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
Sound like a thoughtful human adviser, not a policy document or scripted bot. Acknowledge what the person is trying to do before explaining.
Use contractions and plain everyday English where natural. Vary sentence structure, and do not repeat the same introduction or disclaimer.
Answer the question first. Add one useful next step, and ask no more than one short follow-up question when it would genuinely help.
Keep the answer concise, warm and action-oriented. Use a short paragraph by default; use 3-5 steps only when the person asks how to do something.
"""


def _conversation_query(question, history=None):
    """Add the latest user turn when a short follow-up needs conversational context."""
    q = question.strip()
    if len(q.split()) > 5:
        return q
    prior_users = [
        item["content"] for item in _safe_history(history)
        if item["role"] == "user"
    ]
    return f"{prior_users[-1]} {q}" if prior_users else q


def fallback_assistant_answer(question, history=None, is_authenticated=False):
    """Natural, deterministic guidance when no hosted language model is available."""
    q = question.lower().strip()
    contextual_q = _conversation_query(question, history).lower()
    words = set(q.replace("?", "").replace("!", "").split())

    if words & {"hi", "hello", "hey", "morning", "afternoon", "evening"} and len(words) <= 5:
        return "Hi! What are you working on today—checking a CV against a role, understanding a report, or choosing a plan?"
    if any(phrase in q for phrase in ("thank you", "thanks", "that helps", "got it")):
        return "You’re welcome. If you tell me where you are in the application process, I can help with the next step."
    if any(phrase in q for phrase in ("who are you", "are you a bot", "what are you")):
        return (
            "I’m Maya, the MyValidCV service adviser. I can explain the platform and help you find the right next step. "
            "I don’t make hiring decisions, and I won’t ask you for passwords or sensitive payment details."
        )
    if "discount" in q or "offer" in q or "coupon" in q:
        return "I can’t see an active public offer from here. Any official discount will appear on the Plans page or come directly from support. Would you like help comparing the plans instead?"
    if "refund" in q or "cancel" in q or "terms" in q or "privacy" in q:
        return "That depends on your plan, usage and timing. Check the Terms or Privacy link in the footer, then email support@myvalidcv.com if it concerns your account. Don’t share payment details in this chat."
    if "payment" in q or "pay" in q or "card" in q or "receipt" in q:
        return "Choose the plan you want and complete the secure checkout. Once payment is confirmed, your account access updates automatically. The payment provider handles the card details, not Maya."
    if "enterprise" in contextual_q or "bulk" in contextual_q:
        return "Enterprise is designed for teams comparing several CVs with one role. It produces a concise ranked review and highlights evidence gaps, but a person must still review every candidate before any decision. Are you screening for one role or several?"
    if "plan" in contextual_q or "price" in contextual_q or "plus" in contextual_q or "free" in contextual_q:
        account_note = "Since you’re signed in, your account page shows your current allowance. " if is_authenticated else ""
        return (
            f"{account_note}Free is best for trying the analysis, Plus adds 20 analyses and editable CV and cover-letter drafts, "
            "and Enterprise is for advisory bulk comparison. The Plans page has the current prices. Are you applying for yourself or reviewing candidates?"
        )
    if "report" in contextual_q or "ats" in contextual_q or "score" in contextual_q or "truth gate" in contextual_q:
        return "Think of the ATS result as a document check, not a prediction. It shows how well your CV evidences this particular job, then the Truth Gate separates proven strengths from claims you still need to confirm. Which part of your report is unclear?"
    if any(term in contextual_q for term in ("cv", "cover", "rewrite", "draft", "bullet", "summary")):
        return "Yes—I can help you use the evidence already in your CV more effectively for the role. MyValidCV can propose a summary, experience bullets and a cover letter, but you should verify every fact before downloading. Are you working on the summary, experience section or cover letter?"
    if any(term in contextual_q for term in ("how", "work", "start", "upload", "validate")):
        return "Start by uploading your CV and adding the job advert you want to target. Run the validation, review the evidence gaps, then improve only the wording your CV can genuinely support. Do you already have the job advert?"
    return "I can help with CV validation, ATS results, document drafts, plans, payments or Enterprise screening. Tell me what you’re trying to do, and I’ll point you to the next step."


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
        "options": {"temperature": 0.55, "num_predict": 350},
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
        "answer": answer or fallback_assistant_answer(
            question,
            history=payload.get("history"),
            is_authenticated=request.user.is_authenticated,
        ),
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
