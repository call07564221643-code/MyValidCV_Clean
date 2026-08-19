from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class FinancialAssumption(models.Model):
    """Admin-maintained assumptions used by management finance reports."""

    name = models.CharField(max_length=120, default="Default SaaS finance assumptions")
    is_active = models.BooleanField(default=True)
    currency = models.CharField(max_length=3, default="GBP")

    hosting_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("35.00"))
    database_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("20.00"))
    storage_backup_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("12.00"))
    email_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("8.00"))
    monitoring_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("10.00"))
    software_tools_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("15.00"))
    marketing_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("50.00"))
    accounting_admin_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("25.00"))

    free_user_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.25"))
    plus_user_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.85"))
    professional_user_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.40"))
    enterprise_user_monthly_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("8.00"))
    enterprise_batch_delivery_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("4.50"))

    ai_cost_per_validation = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0.0400"))
    generated_cv_cost = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0.0800"))
    payment_percent_fee = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.0290"),
        help_text="Use 0.0290 for 2.9%.",
    )
    payment_fixed_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.20"))

    cash_reserve = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    accounts_payable = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tax_accrual_percent = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Use 0.1900 for 19%. Leave 0 during MVP testing.",
    )

    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Financial assumption"
        verbose_name_plural = "Financial assumptions"
        ordering = ["-is_active", "-updated_at"]

    def __str__(self):
        return self.name

    @classmethod
    def current(cls):
        assumption = cls.objects.filter(is_active=True).first()
        if assumption:
            return assumption
        return cls.objects.create()

    def fixed_monthly_cost_total(self):
        return sum(
            [
                self.hosting_monthly_cost,
                self.database_monthly_cost,
                self.storage_backup_monthly_cost,
                self.email_monthly_cost,
                self.monitoring_monthly_cost,
                self.software_tools_monthly_cost,
                self.marketing_monthly_cost,
                self.accounting_admin_monthly_cost,
            ],
            Decimal("0.00"),
        )


class FinancialEntry(models.Model):
    """Auditable money-in/money-out feed entry; never stores bank credentials."""

    DIRECTION_CHOICES = [("income", "Money in"), ("expense", "Money out")]
    SOURCE_CHOICES = [
        ("manual", "Manual entry"),
        ("import", "CSV/accounting import"),
        ("provider", "Connected provider"),
        ("recurring", "Recurring schedule"),
    ]
    STATUS_CHOICES = [
        ("forecast", "Forecast"),
        ("recorded", "Recorded"),
        ("reconciled", "Reconciled"),
        ("void", "Void"),
    ]

    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, db_index=True)
    category = models.CharField(max_length=80, db_index=True)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="GBP")
    occurred_on = models.DateField(default=timezone.localdate, db_index=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="recorded", db_index=True)
    provider = models.CharField(max_length=40, blank=True)
    external_reference = models.CharField(max_length=160, blank=True)
    evidence_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="financial_entries_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_on", "-created_at"]
        indexes = [
            models.Index(fields=["direction", "status", "-occurred_on"], name="finance_entry_period_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="finance_entry_amount_gte_0"),
            models.UniqueConstraint(
                fields=["provider", "external_reference"],
                condition=~models.Q(external_reference=""),
                name="unique_finance_provider_reference",
            ),
        ]

    def __str__(self):
        return f"{self.occurred_on} · {self.get_direction_display()} · {self.currency} {self.amount}"


class FinanceFeedConnection(models.Model):
    """Non-secret configuration and sync status for an external finance feed."""

    PROVIDER_CHOICES = [
        ("stripe", "Stripe"), ("sumup", "SumUp"), ("bank_csv", "Bank CSV"),
        ("xero", "Xero"), ("quickbooks", "QuickBooks"), ("other", "Other"),
    ]
    STATUS_CHOICES = [("draft", "Draft"), ("ready", "Ready"), ("connected", "Connected"), ("error", "Error"), ("disabled", "Disabled")]

    name = models.CharField(max_length=120)
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    currency = models.CharField(max_length=3, default="GBP")
    account_reference = models.CharField(max_length=120, blank=True, help_text="Non-secret merchant/account label only.")
    configuration = models.JSONField(default=dict, blank=True, help_text="Non-secret mapping options only; keep API keys in environment variables.")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=120, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider", "name"]
        permissions = [("sync_finance_feed", "Can synchronize finance feeds")]

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"

    def clean(self):
        forbidden = {"secret", "password", "token", "api_key", "private_key", "client_secret"}
        supplied = {str(key).lower() for key in self.configuration}
        if supplied & forbidden:
            raise ValidationError({"configuration": "Store credentials in environment variables, never in this database field."})
