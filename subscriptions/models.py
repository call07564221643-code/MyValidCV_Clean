from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class SubscriptionPlan(models.Model):
    INTERVAL_CHOICES = [
        ("month", "Monthly"),
        ("year", "Yearly"),
    ]

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="GBP")
    billing_interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, default="month")
    cv_limit = models.PositiveIntegerField(default=1)
    daily_analysis_limit = models.PositiveIntegerField(default=2)
    monthly_bulk_cv_limit = models.PositiveIntegerField(default=0)
    includes_generated_cv = models.BooleanField(default=False)
    includes_job_url = models.BooleanField(default=False)
    includes_deadline_alerts = models.BooleanField(default=False)
    includes_enterprise_reports = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "price"]

    def __str__(self):
        return self.name


class CustomerSubscription(models.Model):
    STATUS_CHOICES = [
        ("trialing", "Trialing"),
        ("active", "Active"),
        ("past_due", "Past due"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    started_at = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user} - {self.plan} ({self.status})"


class DiscountCode(models.Model):
    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=180, blank=True)
    percent_off = models.PositiveIntegerField(default=0)
    amount_off = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="GBP")
    max_redemptions = models.PositiveIntegerField(default=0, help_text="0 means unlimited.")
    redemptions = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    def is_valid_now(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from > now:
            return False
        if self.valid_until and self.valid_until < now:
            return False
        if self.max_redemptions and self.redemptions >= self.max_redemptions:
            return False
        return True

    def apply_to(self, amount):
        discounted = amount
        if self.percent_off:
            discounted = discounted * (Decimal("100") - Decimal(self.percent_off)) / Decimal("100")
        if self.amount_off:
            discounted = discounted - self.amount_off
        return max(Decimal("0.00"), discounted.quantize(Decimal("0.01")))
