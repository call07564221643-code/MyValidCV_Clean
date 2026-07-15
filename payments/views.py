import json
import logging
import re
from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import IntegrityError, transaction as db_transaction
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import UserProfile
from subscriptions.models import CustomerSubscription, DiscountCode, SubscriptionPlan

from .models import Invoice, PaymentTransaction, PaymentWebhookLog
from .services import (
    StripeAPIError,
    StripeConfigurationError,
    StripeSignatureError,
    create_stripe_checkout_session,
    retrieve_stripe_checkout_session,
    verify_stripe_signature,
)


logger = logging.getLogger(__name__)


def pricing(request):
    """Stage 1 of payment: read the seeded plan catalogue without mutating it."""
    plans = SubscriptionPlan.objects.filter(is_active=True, code__in=["free", "plus", "enterprise"])
    return render(request, "payments/pricing.html", {"plans": plans})


def demo_checkout_context(transaction, form_data=None):
    default_form_data = {
        "cardholder_name": transaction.user.get_full_name() or transaction.user.username,
        "card_number": "4242 4242 4242 4242",
        "expiry": "12/34",
        "cvc": "123",
        "billing_postcode": "",
        "billing_email": transaction.user.email,
    }
    if form_data:
        default_form_data.update(form_data)
    return {"transaction": transaction, "form_data": default_form_data}


@login_required(login_url="login")
@require_POST
def start_stripe_checkout(request, plan_code):
    """Create the pending local payment/invoice, then redirect to Stripe.

    Login and POST/CSRF protection establish who is paying. This view does not
    grant service access; access is granted only after provider verification in
    ``stripe_success`` or ``stripe_webhook`` calls ``activate_paid_transaction``.
    """
    plan = get_object_or_404(SubscriptionPlan, code=plan_code, is_active=True)
    discount = None
    amount = plan.price
    code = request.POST.get("discount_code", "").strip()
    if code:
        discount = DiscountCode.objects.filter(code__iexact=code).first()
        if not discount or not discount.is_valid_now():
            messages.error(request, "This discount code is not valid.")
            return redirect("pricing")
        amount = discount.apply_to(amount)

    transaction = PaymentTransaction.objects.create(
        user=request.user,
        plan=plan,
        discount_code=discount,
        amount=amount,
        currency=plan.currency,
        provider="stripe",
        status="pending",
        raw_response={"requested_provider": "stripe"},
    )
    Invoice.objects.create(
        user=request.user,
        transaction=transaction,
        invoice_number=f"MVCV-{transaction.id:06d}",
        amount=amount,
        currency=plan.currency,
        status="open",
    )

    if amount == Decimal("0.00"):
        activate_paid_transaction(transaction, raw_response={"stripe_free_plan": True})
        messages.success(request, f"{plan.name} activated.")
        return redirect("payment_receipt", checkout_reference=transaction.checkout_reference)

    if settings.STRIPE_MOCK_MODE:
        return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction))

    success_url = request.build_absolute_uri(reverse("stripe_success", args=[transaction.checkout_reference]))
    success_url = f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = request.build_absolute_uri(reverse("pricing"))
    try:
        session = create_stripe_checkout_session(transaction, success_url, cancel_url)
    except StripeConfigurationError:
        logger.exception("Stripe checkout is not configured for plan %s.", plan.code)
        if settings.STRIPE_MOCK_MODE:
            messages.warning(request, "Live card checkout is not connected yet. Demo checkout is available.")
            return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction))
        messages.error(request, "Stripe checkout is not configured. Please contact support.")
        return redirect("pricing")
    except StripeAPIError:
        logger.exception("Stripe checkout API failed for plan %s and transaction %s.", plan.code, transaction.checkout_reference)
        messages.error(request, "Stripe checkout could not be started. Please try again.")
        return redirect("pricing")

    transaction.provider_checkout_id = session.get("id", "")
    transaction.hosted_checkout_url = session.get("url", "")
    transaction.raw_response = session
    transaction.save(update_fields=["provider_checkout_id", "hosted_checkout_url", "raw_response", "updated_at"])

    if transaction.hosted_checkout_url:
        return redirect(transaction.hosted_checkout_url)
    messages.error(request, "Payment checkout could not be started. Please try again.")
    return redirect("pricing")


def stripe_mock_checkout(request, checkout_reference):
    if not settings.DEBUG or not settings.STRIPE_MOCK_MODE:
        raise Http404("This checkout route is unavailable.")
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")
    transaction = get_object_or_404(PaymentTransaction, checkout_reference=checkout_reference, user=request.user)
    if request.method == "POST":
        card_number = request.POST.get("card_number", "").replace(" ", "")
        cardholder_name = request.POST.get("cardholder_name", "").strip()
        expiry = request.POST.get("expiry", "").strip()
        cvc = request.POST.get("cvc", "").strip()
        billing_postcode = request.POST.get("billing_postcode", "").strip()
        billing_email = request.POST.get("billing_email", "").strip()

        form_data = {
            "cardholder_name": cardholder_name,
            "card_number": request.POST.get("card_number", ""),
            "expiry": expiry,
            "cvc": cvc,
            "billing_postcode": billing_postcode,
            "billing_email": billing_email,
        }

        if not cardholder_name:
            messages.error(request, "Enter the cardholder name.")
            return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction, form_data))
        if not re.match(r"^\S+@\S+\.\S+$", billing_email):
            messages.error(request, "Enter a valid billing email address.")
            return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction, form_data))
        if not billing_postcode:
            messages.error(request, "Enter the billing postcode or ZIP code.")
            return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction, form_data))
        if card_number != "4242424242424242":
            messages.error(request, "Use test card 4242 4242 4242 4242 for a successful demo payment.")
            return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction, form_data))
        if not re.match(r"^(0[1-9]|1[0-2])\/?([0-9]{2}|[0-9]{4})$", expiry):
            messages.error(request, "Enter a valid expiry date, for example 12/34.")
            return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction, form_data))
        if not re.match(r"^[0-9]{3,4}$", cvc):
            messages.error(request, "Enter a valid 3 or 4 digit security code.")
            return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction, form_data))

        if billing_email and transaction.user.email != billing_email:
            transaction.user.email = billing_email
            transaction.user.save(update_fields=["email"])

        activate_paid_transaction(
            transaction,
            raw_response={
                "demo_checkout": True,
                "test_card_last4": card_number[-4:],
                "cardholder_name": cardholder_name,
                "billing_postcode": billing_postcode,
                "billing_email": billing_email,
            },
        )
        messages.success(request, "Payment confirmed. Your subscription is active.")
        return redirect("payment_receipt", checkout_reference=transaction.checkout_reference)
    return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction))


@login_required(login_url="login")
def stripe_success(request, checkout_reference):
    """Verify the returning user's Checkout Session before activation."""
    transaction = get_object_or_404(PaymentTransaction, checkout_reference=checkout_reference, user=request.user)
    session_id = request.GET.get("session_id", "")
    if not session_id or session_id != transaction.provider_checkout_id:
        messages.warning(request, "Payment is awaiting Stripe confirmation.")
        return render(request, "payments/payment_pending.html", {"transaction": transaction})
    try:
        session = retrieve_stripe_checkout_session(session_id)
    except (StripeConfigurationError, StripeAPIError):
        logger.exception("Stripe checkout verification failed for transaction %s.", transaction.checkout_reference)
        messages.warning(request, "Payment is awaiting Stripe confirmation.")
        return render(request, "payments/payment_pending.html", {"transaction": transaction})
    reference = session.get("metadata", {}).get("checkout_reference", "")
    if (
        reference == str(transaction.checkout_reference)
        and session.get("mode") == "subscription"
        and session.get("payment_status") in ("paid", "no_payment_required")
        and session.get("status") == "complete"
    ):
        try:
            activate_paid_transaction(
                transaction,
                raw_response=session,
                stripe_customer_id=session.get("customer", "") or "",
                stripe_subscription_id=session.get("subscription", "") or "",
            )
        except Exception:
            logger.exception("Payment activation failed for transaction %s.", transaction.checkout_reference)
            messages.warning(request, "Payment is confirmed by Stripe and is being activated. Please check again shortly.")
            return render(request, "payments/payment_pending.html", {"transaction": transaction})
        messages.success(request, "Payment confirmed. Your subscription is active.")
        return redirect("payment_receipt", checkout_reference=transaction.checkout_reference)
    messages.warning(request, "Payment has not been confirmed by Stripe yet.")
    return render(request, "payments/payment_pending.html", {"transaction": transaction})


@csrf_exempt
def stripe_webhook(request):
    """Process signed, idempotent Stripe lifecycle events server-to-server.

    CSRF is intentionally exempt because Stripe cannot send a Django token;
    ``verify_stripe_signature`` is the stronger provider authentication here.
    The unique Stripe event ID prevents the same event being applied twice.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    try:
        verify_stripe_signature(request.body, request.headers.get("Stripe-Signature", ""))
    except StripeSignatureError:
        return HttpResponseBadRequest("Invalid Stripe signature")
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    event_id = payload.get("id")
    event_type = payload.get("type", "")
    stripe_object = payload.get("data", {}).get("object", {})
    checkout_reference = stripe_object.get("metadata", {}).get("checkout_reference", "")
    if not event_id or not event_type:
        return HttpResponseBadRequest("Invalid Stripe event")
    try:
        log, created = PaymentWebhookLog.objects.get_or_create(
            event_id=event_id,
            defaults={
                "provider": "stripe",
                "event_type": event_type,
                "checkout_reference": checkout_reference,
                "payload": payload,
            },
        )
    except IntegrityError:
        return JsonResponse({"ok": True, "duplicate": True})
    if not created:
        return JsonResponse({"ok": True, "duplicate": True})

    try:
        if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            if checkout_reference and stripe_object.get("payment_status") in ("paid", "no_payment_required"):
                payment = PaymentTransaction.objects.filter(
                    checkout_reference=checkout_reference,
                    provider="stripe",
                ).first()
                if payment:
                    session_id = stripe_object.get("id", "")
                    if payment.provider_checkout_id and session_id != payment.provider_checkout_id:
                        raise ValueError("Checkout Session does not match the payment transaction.")
                    if not payment.provider_checkout_id:
                        payment.provider_checkout_id = session_id
                        payment.save(update_fields=["provider_checkout_id", "updated_at"])
                    activate_paid_transaction(
                        payment,
                        raw_response=payload,
                        stripe_customer_id=stripe_object.get("customer", "") or "",
                        stripe_subscription_id=stripe_object.get("subscription", "") or "",
                    )
                    log.is_processed = True
        elif event_type == "checkout.session.expired":
            PaymentTransaction.objects.filter(
                checkout_reference=checkout_reference,
                provider="stripe",
                status="pending",
            ).update(status="cancelled")
            log.is_processed = True
        elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
            sync_stripe_subscription(stripe_object, deleted=event_type.endswith("deleted"))
            log.is_processed = True
        elif event_type == "invoice.paid":
            stripe_subscription_id = stripe_invoice_subscription_id(stripe_object)
            set_subscription_active(stripe_subscription_id)
            log.is_processed = True
        elif event_type == "invoice.payment_failed":
            stripe_subscription_id = stripe_invoice_subscription_id(stripe_object)
            set_subscription_inactive(stripe_subscription_id, "past_due")
            log.is_processed = True
    except Exception as exc:
        log.error = str(exc)
        log.save(update_fields=["error"])
        return JsonResponse({"ok": False}, status=500)

    log.save(update_fields=["is_processed"])
    return JsonResponse({"ok": True})


@login_required(login_url="login")
def payment_receipt(request, checkout_reference):
    transaction = get_object_or_404(
        PaymentTransaction.objects.select_related("plan", "subscription", "invoice"),
        checkout_reference=checkout_reference,
        user=request.user,
    )
    if not hasattr(transaction, "invoice"):
        logger.error("Paid transaction %s has no invoice record.", transaction.checkout_reference)
        messages.warning(request, "Your payment exists, but the receipt is still being prepared.")
        return render(request, "payments/payment_pending.html", {"transaction": transaction})
    return render(request, "payments/receipt.html", {"transaction": transaction})


def next_payment_date_from_plan(plan, paid_at):
    if plan.price == Decimal("0.00"):
        return None
    if plan.billing_interval == "year":
        return paid_at + timedelta(days=365)
    return paid_at + timedelta(days=30)


def send_receipt_email(transaction):
    if not getattr(transaction.user, "email", ""):
        return "no_email"

    invoice = getattr(transaction, "invoice", None)
    if not invoice:
        return "no_invoice"

    next_payment = invoice.next_payment_date.strftime("%d %b %Y") if invoice.next_payment_date else "No future payment scheduled"
    subject = f"MyValidCV payment receipt {invoice.invoice_number}"
    body = (
        f"Thank you for your MyValidCV payment.\n\n"
        f"Receipt: {invoice.invoice_number}\n"
        f"Plan: {transaction.plan.name}\n"
        f"Amount: {transaction.currency} {transaction.amount}\n"
        f"Status: {transaction.status}\n"
        f"Next payment date: {next_payment}\n\n"
        f"Your subscription is active."
    )
    try:
        sent = send_mail(
            subject,
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", "receipts@myvalidcv.local"),
            [transaction.user.email],
            fail_silently=False,
        )
    except Exception:
        return "failed"
    return "sent" if sent else "failed"


@db_transaction.atomic
def activate_paid_transaction(
    transaction,
    raw_response=None,
    stripe_customer_id="",
    stripe_subscription_id="",
    current_period_end=None,
):
    """Stage 3 of payment: atomically grant the purchased service level.

    This is the central activation function. It marks payment/invoice paid,
    creates or updates CustomerSubscription, copies the plan code to
    UserProfile for ATS feature checks, and sends one receipt. Row locking and
    the ``was_paid`` check make repeated provider notifications safe.
    """
    transaction = PaymentTransaction.objects.select_for_update().select_related("user", "plan").get(pk=transaction.pk)
    was_paid = transaction.status == "paid"
    paid_at = timezone.now()
    transaction.status = "paid"
    if raw_response is not None:
        transaction.raw_response = raw_response
    if stripe_subscription_id:
        transaction.provider_transaction_id = stripe_subscription_id
    transaction.save(update_fields=["status", "raw_response", "provider_transaction_id", "updated_at"])

    next_payment_date = current_period_end or next_payment_date_from_plan(transaction.plan, paid_at)
    subscription, created = CustomerSubscription.objects.get_or_create(
        user=transaction.user,
        defaults={"plan": transaction.plan, "started_at": paid_at},
    )
    subscription.plan = transaction.plan
    subscription.status = "active"
    subscription.cancelled_at = None
    subscription.current_period_end = next_payment_date
    if stripe_customer_id:
        subscription.stripe_customer_id = stripe_customer_id
    if stripe_subscription_id:
        subscription.stripe_subscription_id = stripe_subscription_id
    subscription.save()
    transaction.subscription = subscription
    transaction.save(update_fields=["subscription", "updated_at"])

    profile, _profile_created = UserProfile.objects.get_or_create(user=transaction.user)
    profile.plan = transaction.plan.code
    profile.save(update_fields=["plan"])

    if hasattr(transaction, "invoice"):
        transaction.invoice.status = "paid"
        transaction.invoice.paid_at = paid_at
        transaction.invoice.next_payment_date = next_payment_date
        transaction.invoice.receipt_email = transaction.user.email
        transaction.invoice.save(update_fields=["status", "paid_at", "next_payment_date", "receipt_email"])
        if not was_paid or transaction.invoice.receipt_email_status != "sent":
            email_status = send_receipt_email(transaction)
            transaction.invoice.receipt_email_status = email_status
            if email_status == "sent":
                transaction.invoice.receipt_sent_at = timezone.now()
            transaction.invoice.save(update_fields=["receipt_email_status", "receipt_sent_at"])

    if transaction.discount_code and not was_paid:
        transaction.discount_code.redemptions += 1
        transaction.discount_code.save(update_fields=["redemptions"])
    return transaction


def stripe_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=datetime_timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def stripe_invoice_subscription_id(stripe_object):
    subscription = stripe_object.get("subscription", "")
    if isinstance(subscription, dict):
        return subscription.get("id", "")
    if subscription:
        return subscription
    parent = stripe_object.get("parent", {}) or {}
    details = parent.get("subscription_details", {}) or {}
    nested = details.get("subscription", "")
    return nested.get("id", "") if isinstance(nested, dict) else nested


@db_transaction.atomic
def sync_stripe_subscription(stripe_object, deleted=False):
    stripe_subscription_id = stripe_object.get("id", "")
    checkout_reference = stripe_object.get("metadata", {}).get("checkout_reference", "")
    subscription = CustomerSubscription.objects.select_for_update().filter(
        stripe_subscription_id=stripe_subscription_id
    ).select_related("user").first()
    if not subscription and checkout_reference:
        payment = PaymentTransaction.objects.filter(checkout_reference=checkout_reference).select_related("subscription").first()
        subscription = payment.subscription if payment else None
    if not subscription:
        return

    stripe_status = "cancelled" if deleted else stripe_object.get("status", "")
    status_map = {
        "active": "active",
        "trialing": "trialing",
        "past_due": "past_due",
        "unpaid": "past_due",
        "canceled": "cancelled",
        "cancelled": "cancelled",
        "incomplete_expired": "expired",
    }
    subscription.status = status_map.get(stripe_status, subscription.status)
    subscription.stripe_subscription_id = stripe_subscription_id or subscription.stripe_subscription_id
    subscription.stripe_customer_id = stripe_object.get("customer", "") or subscription.stripe_customer_id
    subscription.current_period_end = stripe_timestamp(stripe_object.get("current_period_end")) or subscription.current_period_end
    if subscription.status in ("cancelled", "expired"):
        subscription.cancelled_at = timezone.now()
    subscription.save()
    profile, _created = UserProfile.objects.get_or_create(user=subscription.user)
    profile.plan = subscription.plan.code if subscription.status in ("active", "trialing") else "free"
    profile.save(update_fields=["plan"])


@db_transaction.atomic
def set_subscription_inactive(stripe_subscription_id, status):
    if not stripe_subscription_id:
        return
    subscription = CustomerSubscription.objects.select_for_update().filter(
        stripe_subscription_id=stripe_subscription_id
    ).select_related("user").first()
    if not subscription:
        return
    subscription.status = status
    subscription.save(update_fields=["status", "updated_at"])
    profile, _created = UserProfile.objects.get_or_create(user=subscription.user)
    profile.plan = "free"
    profile.save(update_fields=["plan"])


@db_transaction.atomic
def set_subscription_active(stripe_subscription_id):
    if not stripe_subscription_id:
        return
    subscription = CustomerSubscription.objects.select_for_update().filter(
        stripe_subscription_id=stripe_subscription_id
    ).select_related("user", "plan").first()
    if not subscription:
        return
    subscription.status = "active"
    subscription.cancelled_at = None
    subscription.save(update_fields=["status", "cancelled_at", "updated_at"])
    profile, _created = UserProfile.objects.get_or_create(user=subscription.user)
    profile.plan = subscription.plan.code
    profile.save(update_fields=["plan"])
