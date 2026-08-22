import json
import hashlib
import hmac
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation

from django.conf import settings


class StripeConfigurationError(Exception):
    pass


class StripeAPIError(Exception):
    pass


class StripeSignatureError(Exception):
    pass


class SumUpConfigurationError(Exception):
    pass


class SumUpAPIError(Exception):
    pass


def is_sumup_configured():
    return bool(settings.SUMUP_API_KEY and settings.SUMUP_MERCHANT_CODE)


def _sumup_request(path, method="GET", payload=None, idempotency_key=""):
    if not is_sumup_configured():
        raise SumUpConfigurationError("SUMUP_API_KEY and SUMUP_MERCHANT_CODE are required.")
    headers = {
        "Authorization": f"Bearer {settings.SUMUP_API_KEY}",
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    request = urllib.request.Request(
        f"https://api.sumup.com{path}", data=data, headers=headers, method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")[:1000]
        raise SumUpAPIError(f"SumUp request failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SumUpAPIError(f"Could not reach SumUp: {exc}") from exc


def create_sumup_checkout(transaction, webhook_url, redirect_url):
    payload = {
        "checkout_reference": str(transaction.checkout_reference),
        "amount": float(transaction.amount),
        "currency": transaction.currency.upper(),
        "merchant_code": settings.SUMUP_MERCHANT_CODE,
        "description": f"MyValidCV {transaction.plan.name}",
        "return_url": webhook_url,
        "redirect_url": redirect_url,
        "hosted_checkout": {"enabled": True},
    }
    return _sumup_request(
        "/v0.1/checkouts", method="POST", payload=payload,
        idempotency_key=f"mvcv-{transaction.checkout_reference}",
    )


def retrieve_sumup_checkout(checkout_id):
    if not checkout_id:
        raise SumUpAPIError("Missing SumUp checkout ID.")
    return _sumup_request(f"/v0.1/checkouts/{checkout_id}")


def refund_sumup_transaction(transaction, amount):
    """Issue an owner-approved partial or full refund against a verified payment."""
    if transaction.provider != "sumup" or transaction.status not in ("paid", "refunded"):
        raise SumUpAPIError("Only confirmed SumUp payments can be refunded.")
    try:
        refund_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SumUpAPIError("Refund amount is invalid.") from exc
    already_refunded = sum(
        (item.amount for item in transaction.refunds.filter(status="processed")), Decimal("0.00")
    )
    refundable = transaction.amount - already_refunded
    if refund_amount <= 0 or refund_amount > refundable:
        raise SumUpAPIError("Refund amount exceeds the remaining refundable payment amount.")

    transactions = (transaction.raw_response or {}).get("transactions") or []
    payment_id = transactions[-1].get("id", "") if transactions else ""
    if not payment_id:
        raise SumUpAPIError("The verified SumUp payment ID is unavailable; reconcile this payment in SumUp first.")
    path = (
        f"/v1.0/merchants/{settings.SUMUP_MERCHANT_CODE}"
        f"/payments/{payment_id}/refunds"
    )
    return _sumup_request(path, method="POST", payload={"amount": float(refund_amount)})


def is_stripe_configured():
    return bool(settings.STRIPE_SECRET_KEY)


def create_stripe_checkout_session(transaction, success_url, cancel_url):
    """Stage 2 of payment: create a hosted recurring Stripe Checkout session.

    The local PaymentTransaction reference is copied into Stripe metadata so
    the signed callback/webhook can safely reconnect the provider event to the
    correct user and plan without trusting browser-submitted plan data.
    """
    if not is_stripe_configured():
        raise StripeConfigurationError("STRIPE_SECRET_KEY is not configured.")

    payload = {
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": transaction.checkout_reference,
        "line_items[0][quantity]": "1",
        "metadata[checkout_reference]": transaction.checkout_reference,
        "subscription_data[metadata][checkout_reference]": transaction.checkout_reference,
    }
    if transaction.user.email:
        payload["customer_email"] = transaction.user.email
    payload.update({
        "line_items[0][price_data][currency]": transaction.currency.lower(),
        "line_items[0][price_data][product_data][name]": f"MyValidCV {transaction.plan.name}",
        "line_items[0][price_data][unit_amount]": str(int(transaction.amount * 100)),
        "line_items[0][price_data][recurring][interval]": transaction.plan.billing_interval,
    })

    request = urllib.request.Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=urlencode(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Idempotency-Key": f"mvcv-checkout-{transaction.checkout_reference}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise StripeAPIError(f"Stripe checkout failed: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise StripeAPIError(f"Could not reach Stripe: {exc}") from exc


def retrieve_stripe_checkout_session(session_id):
    if not is_stripe_configured():
        raise StripeConfigurationError("STRIPE_SECRET_KEY is not configured.")
    request = urllib.request.Request(
        f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
        headers={"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise StripeAPIError(f"Stripe checkout verification failed: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise StripeAPIError(f"Could not reach Stripe: {exc}") from exc


def verify_stripe_signature(payload, signature_header, tolerance=300):
    """Authorise an incoming Stripe webhook using its HMAC signature."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise StripeSignatureError("STRIPE_WEBHOOK_SECRET is not configured.")
    parts = {}
    for item in signature_header.split(","):
        key, separator, value = item.partition("=")
        if separator:
            parts.setdefault(key, []).append(value)
    try:
        timestamp = int(parts["t"][0])
        signatures = parts["v1"]
    except (KeyError, ValueError, IndexError) as exc:
        raise StripeSignatureError("Invalid Stripe-Signature header.") from exc
    if abs(int(time.time()) - timestamp) > tolerance:
        raise StripeSignatureError("Stripe webhook timestamp is outside the allowed tolerance.")
    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(
        settings.STRIPE_WEBHOOK_SECRET.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise StripeSignatureError("Stripe webhook signature verification failed.")
