import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from subscriptions.models import CustomerSubscription, DiscountCode, SubscriptionPlan


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]

    PROVIDER_CHOICES = [
        ("sumup", "SumUp"),
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("amazon_pay", "Amazon Pay"),
        ("apple_pay", "Apple Pay"),
        ("google_pay", "Google Pay"),
        ("manual", "Manual"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_transactions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="payment_transactions")
    subscription = models.ForeignKey(CustomerSubscription, null=True, blank=True, on_delete=models.SET_NULL, related_name="payment_transactions")
    discount_code = models.ForeignKey(DiscountCode, null=True, blank=True, on_delete=models.SET_NULL, related_name="payment_transactions")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default="sumup")
    checkout_reference = models.CharField(max_length=90, unique=True, default=uuid.uuid4)
    provider_checkout_id = models.CharField(max_length=120, blank=True)
    provider_transaction_id = models.CharField(max_length=120, blank=True)
    hosted_checkout_url = models.URLField(blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default="GBP")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    raw_response = models.JSONField(default=dict, blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.checkout_reference} - {self.user} - {self.status}"


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("paid", "Paid"),
        ("void", "Void"),
        ("refunded", "Refunded"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invoices")
    transaction = models.OneToOneField(PaymentTransaction, on_delete=models.CASCADE, related_name="invoice")
    invoice_number = models.CharField(max_length=40, unique=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=3, default="GBP")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    issued_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    receipt_sent_at = models.DateTimeField(null=True, blank=True)
    receipt_email = models.EmailField(blank=True)
    receipt_email_status = models.CharField(max_length=30, default="not_sent")
    next_payment_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.invoice_number


class Refund(models.Model):
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("approved", "Approved"),
        ("processed", "Processed"),
        ("rejected", "Rejected"),
    ]

    transaction = models.ForeignKey(PaymentTransaction, on_delete=models.CASCADE, related_name="refunds")
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
    provider_refund_id = models.CharField(max_length=120, blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund {self.amount} for {self.transaction}"


class PaymentWebhookLog(models.Model):
    provider = models.CharField(max_length=20, default="sumup")
    event_type = models.CharField(max_length=120, blank=True)
    checkout_reference = models.CharField(max_length=90, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    is_processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider} webhook {self.created_at:%Y-%m-%d %H:%M}"
