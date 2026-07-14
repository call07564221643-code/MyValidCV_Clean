import json
import hashlib
import hmac
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

from django.conf import settings


class SumUpConfigurationError(Exception):
    pass


class SumUpAPIError(Exception):
    pass


class StripeConfigurationError(Exception):
    pass


class StripeAPIError(Exception):
    pass


class StripeSignatureError(Exception):
    pass


def is_sumup_configured():
    return bool(settings.SUMUP_ACCESS_TOKEN and settings.SUMUP_MERCHANT_CODE)


def is_stripe_configured():
    return bool(settings.STRIPE_SECRET_KEY)


def create_sumup_checkout(transaction, return_url):
    if not is_sumup_configured():
        raise SumUpConfigurationError("SUMUP_ACCESS_TOKEN and SUMUP_MERCHANT_CODE are not configured.")

    payload = {
        "checkout_reference": transaction.checkout_reference,
        "amount": str(transaction.amount),
        "currency": transaction.currency,
        "merchant_code": settings.SUMUP_MERCHANT_CODE,
        "description": f"MyValidCV {transaction.plan.name}",
        "return_url": return_url,
        "hosted_checkout": {"enabled": True},
    }

    request = urllib.request.Request(
        f"{settings.SUMUP_API_BASE_URL.rstrip('/')}/v0.1/checkouts",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.SUMUP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise SumUpAPIError(f"SumUp checkout failed: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise SumUpAPIError(f"Could not reach SumUp: {exc}") from exc


def retrieve_sumup_checkout(checkout_id):
    if not is_sumup_configured():
        raise SumUpConfigurationError("SUMUP_ACCESS_TOKEN and SUMUP_MERCHANT_CODE are not configured.")

    request = urllib.request.Request(
        f"{settings.SUMUP_API_BASE_URL.rstrip('/')}/v0.1/checkouts/{checkout_id}",
        headers={"Authorization": f"Bearer {settings.SUMUP_ACCESS_TOKEN}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise SumUpAPIError(f"SumUp checkout lookup failed: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise SumUpAPIError(f"Could not reach SumUp: {exc}") from exc


def create_stripe_checkout_session(transaction, success_url, cancel_url):
    if not is_stripe_configured():
        raise StripeConfigurationError("STRIPE_SECRET_KEY is not configured.")

    payload = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": transaction.checkout_reference,
        "line_items[0][price_data][currency]": transaction.currency.lower(),
        "line_items[0][price_data][product_data][name]": f"MyValidCV {transaction.plan.name}",
        "line_items[0][price_data][unit_amount]": str(int(transaction.amount * 100)),
        "line_items[0][quantity]": "1",
        "metadata[checkout_reference]": transaction.checkout_reference,
    }

    request = urllib.request.Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=urlencode(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}",
            "Content-Type": "application/x-www-form-urlencoded",
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
