import json
import re
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from accounts.models import UserProfile
from subscriptions.models import CustomerSubscription, DiscountCode, SubscriptionPlan

from .models import Invoice, PaymentTransaction, PaymentWebhookLog
from .services import (
    StripeAPIError,
    StripeConfigurationError,
    SumUpAPIError,
    SumUpConfigurationError,
    create_stripe_checkout_session,
    create_sumup_checkout,
    retrieve_sumup_checkout,
)


def pricing(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)
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
def start_checkout(request, plan_code):
    plan = get_object_or_404(SubscriptionPlan, code=plan_code, is_active=True)
    discount = None
    amount = plan.price

    if request.method == "POST":
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
        provider="sumup",
        status="pending",
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
        activate_paid_transaction(transaction, raw_response={"discounted_to_zero": True})
        messages.success(request, f"{plan.name} activated with your discount code.")
        return redirect("payment_receipt", checkout_reference=transaction.checkout_reference)

    return_url = request.build_absolute_uri(reverse("sumup_return", args=[transaction.checkout_reference]))
    try:
        checkout = create_sumup_checkout(transaction, return_url)
    except SumUpConfigurationError:
        if settings.STRIPE_MOCK_MODE or settings.STRIPE_SECRET_KEY:
            transaction.provider = "stripe"
            transaction.raw_response = {"internal_fallback": "card_checkout"}
            transaction.save(update_fields=["provider", "raw_response", "updated_at"])
            return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction))
        messages.warning(request, "Live card checkout is not connected yet. Configure payment credentials to take payments.")
        return render(request, "payments/sumup_setup.html", {"transaction": transaction})
    except SumUpAPIError as exc:
        messages.error(request, "Payment checkout could not be started. Please try again or contact support.")
        return redirect("pricing")

    transaction.provider_checkout_id = checkout.get("id", "")
    transaction.hosted_checkout_url = checkout.get("hosted_checkout_url", "")
    transaction.raw_response = checkout
    transaction.save(update_fields=["provider_checkout_id", "hosted_checkout_url", "raw_response", "updated_at"])

    if transaction.hosted_checkout_url:
        return redirect(transaction.hosted_checkout_url)

    messages.error(request, "Payment checkout could not be started. Please try again.")
    return redirect("pricing")


@login_required(login_url="login")
def start_stripe_checkout(request, plan_code):
    plan = get_object_or_404(SubscriptionPlan, code=plan_code, is_active=True)
    amount = plan.price

    transaction = PaymentTransaction.objects.create(
        user=request.user,
        plan=plan,
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
    cancel_url = request.build_absolute_uri(reverse("pricing"))
    try:
        session = create_stripe_checkout_session(transaction, success_url, cancel_url)
    except StripeConfigurationError:
        messages.warning(request, "Live card checkout is not connected yet. Demo checkout is available.")
        return render(request, "payments/stripe_mock_checkout.html", demo_checkout_context(transaction))
    except StripeAPIError as exc:
        messages.error(request, str(exc))
        return redirect("pricing")

    transaction.provider_checkout_id = session.get("id", "")
    transaction.hosted_checkout_url = session.get("url", "")
    transaction.raw_response = session
    transaction.save(update_fields=["provider_checkout_id", "hosted_checkout_url", "raw_response", "updated_at"])

    if transaction.hosted_checkout_url:
        return redirect(transaction.hosted_checkout_url)
    messages.error(request, "Payment checkout could not be started. Please try again.")
    return redirect("pricing")


@login_required(login_url="login")
def stripe_mock_checkout(request, checkout_reference):
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
    transaction = get_object_or_404(PaymentTransaction, checkout_reference=checkout_reference, user=request.user)
    activate_paid_transaction(transaction, raw_response={"stripe_success_return": True})
    messages.success(request, "Payment confirmed. Your subscription is active.")
    return redirect("payment_receipt", checkout_reference=transaction.checkout_reference)


@csrf_exempt
def stripe_webhook(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    checkout_reference = (
        payload.get("data", {})
        .get("object", {})
        .get("metadata", {})
        .get("checkout_reference", "")
    )
    log = PaymentWebhookLog.objects.create(
        provider="stripe",
        event_type=payload.get("type", ""),
        checkout_reference=checkout_reference,
        payload=payload,
    )
    if payload.get("type") == "checkout.session.completed" and checkout_reference:
        transaction = PaymentTransaction.objects.filter(checkout_reference=checkout_reference).first()
        if transaction:
            activate_paid_transaction(transaction, raw_response=payload)
            log.is_processed = True
            log.save(update_fields=["is_processed"])
    return JsonResponse({"ok": True})


@login_required(login_url="login")
def sumup_return(request, checkout_reference):
    transaction = get_object_or_404(PaymentTransaction, checkout_reference=checkout_reference, user=request.user)
    if not transaction.provider_checkout_id:
        return render(request, "payments/payment_pending.html", {"transaction": transaction})

    try:
        checkout = retrieve_sumup_checkout(transaction.provider_checkout_id)
    except (SumUpConfigurationError, SumUpAPIError) as exc:
        messages.warning(request, f"Payment created, but status could not be verified yet: {exc}")
        return render(request, "payments/payment_pending.html", {"transaction": transaction})

    status = str(checkout.get("status", "")).upper()
    if status == "PAID":
        activate_paid_transaction(transaction, raw_response=checkout)
        messages.success(request, "Payment confirmed. Your subscription is active.")
        return redirect("payment_receipt", checkout_reference=transaction.checkout_reference)

    transaction.raw_response = checkout
    transaction.save(update_fields=["raw_response", "updated_at"])
    return render(request, "payments/payment_pending.html", {"transaction": transaction, "sumup_status": status})


@csrf_exempt
def sumup_webhook(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    checkout_reference = payload.get("checkout_reference") or payload.get("id", "")
    log = PaymentWebhookLog.objects.create(
        provider="sumup",
        event_type=payload.get("event_type", payload.get("status", "")),
        checkout_reference=checkout_reference,
        payload=payload,
    )

    transaction = PaymentTransaction.objects.filter(checkout_reference=checkout_reference).first()
    if transaction and str(payload.get("status", "")).upper() == "PAID":
        activate_paid_transaction(transaction, raw_response=payload)
        log.is_processed = True
        log.save(update_fields=["is_processed"])

    return JsonResponse({"ok": True})


@login_required(login_url="login")
def payment_receipt(request, checkout_reference):
    transaction = get_object_or_404(
        PaymentTransaction.objects.select_related("plan", "subscription", "invoice"),
        checkout_reference=checkout_reference,
        user=request.user,
    )
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


def activate_paid_transaction(transaction, raw_response=None):
    if transaction.status == "paid" and getattr(transaction, "invoice", None) and transaction.invoice.receipt_email_status == "sent":
        return transaction

    paid_at = timezone.now()
    transaction.status = "paid"
    if raw_response is not None:
        transaction.raw_response = raw_response
    transaction.save(update_fields=["status", "raw_response", "updated_at"])

    next_payment_date = next_payment_date_from_plan(transaction.plan, paid_at)
    subscription, _created = CustomerSubscription.objects.update_or_create(
        user=transaction.user,
        defaults={
            "plan": transaction.plan,
            "status": "active",
            "started_at": paid_at,
            "current_period_end": next_payment_date,
        },
    )
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
        email_status = send_receipt_email(transaction)
        transaction.invoice.receipt_email_status = email_status
        if email_status == "sent":
            transaction.invoice.receipt_sent_at = timezone.now()
        transaction.invoice.save(update_fields=["receipt_email_status", "receipt_sent_at"])

    if transaction.discount_code:
        transaction.discount_code.redemptions += 1
        transaction.discount_code.save(update_fields=["redemptions"])
