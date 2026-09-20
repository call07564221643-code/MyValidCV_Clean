from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
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


class PlatformOperationsSettings(models.Model):
    """Owner-managed alert destinations and thresholds; credentials stay in env vars."""

    SEVERITY_CHOICES = [
        ("info", "Information and above"),
        ("warning", "Warning and critical"),
        ("critical", "Critical only"),
    ]
    PROVIDER_CHOICES = [
        ("disabled", "Not configured"),
        ("twilio", "Twilio-compatible"),
        ("meta", "Meta WhatsApp Cloud API"),
        ("custom", "Custom provider adapter"),
    ]
    e164_validator = RegexValidator(
        regex=r"^\+[1-9]\d{7,14}$",
        message="Enter the number in international E.164 format, for example +447700900123.",
    )

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    owner_name = models.CharField(max_length=120, blank=True)
    timezone_name = models.CharField(max_length=64, default="Europe/London")
    alert_email = models.EmailField(blank=True)
    mobile_number = models.CharField(max_length=16, blank=True, validators=[e164_validator])
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    whatsapp_enabled = models.BooleanField(default=False)
    minimum_severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="warning")
    messaging_provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default="disabled")
    warning_storage_percent = models.PositiveSmallIntegerField(default=70)
    critical_storage_percent = models.PositiveSmallIntegerField(default=90)
    monthly_ai_budget = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    monthly_messaging_budget = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="GBP")
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    daily_digest_enabled = models.BooleanField(default=True)
    daily_digest_time = models.TimeField(default="08:00")
    email_verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    sms_verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    whatsapp_verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform operations settings"
        verbose_name_plural = "Platform operations settings"

    def __str__(self):
        return "Owner operations and alert settings"

    def clean(self):
        errors = {}
        if self.warning_storage_percent < 1 or self.warning_storage_percent > 98:
            errors["warning_storage_percent"] = "Use a warning threshold from 1 to 98 percent."
        if self.critical_storage_percent <= self.warning_storage_percent or self.critical_storage_percent > 99:
            errors["critical_storage_percent"] = "Critical must be above warning and no more than 99 percent."
        if self.email_enabled and not self.alert_email:
            errors["alert_email"] = "Add an owner email or disable email alerts."
        if (self.sms_enabled or self.whatsapp_enabled) and not self.mobile_number:
            errors["mobile_number"] = "Add an international mobile number for SMS or WhatsApp alerts."
        if (self.sms_enabled or self.whatsapp_enabled) and self.messaging_provider == "disabled":
            errors["messaging_provider"] = "Choose a messaging provider before enabling SMS or WhatsApp."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def current(cls):
        settings_record = cls.objects.first()
        if settings_record:
            return settings_record
        return cls.objects.create(email_enabled=False)


class OperationalAlert(models.Model):
    SEVERITY_CHOICES = [("info", "Information"), ("warning", "Warning"), ("critical", "Critical")]
    STATUS_CHOICES = [("open", "Open"), ("acknowledged", "Acknowledged"), ("resolved", "Resolved")]

    fingerprint = models.CharField(max_length=160, db_index=True)
    category = models.CharField(max_length=40, db_index=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    title = models.CharField(max_length=180)
    message = models.TextField(help_text="Operational metadata only; never include CV content or candidate details.")
    metric_value = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    threshold_value = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    occurrence_count = models.PositiveIntegerField(default=1)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="operational_alerts_acknowledged",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen_at"]
        indexes = [models.Index(fields=["status", "severity", "-last_seen_at"], name="ops_alert_status_idx")]

    def __str__(self):
        return f"{self.get_severity_display()}: {self.title}"


class NotificationAttempt(models.Model):
    CHANNEL_CHOICES = [("email", "Email"), ("sms", "SMS"), ("whatsapp", "WhatsApp")]
    STATUS_CHOICES = [("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")]

    alert = models.ForeignKey(OperationalAlert, on_delete=models.CASCADE, related_name="notification_attempts")
    channel = models.CharField(max_length=12, choices=CHANNEL_CHOICES)
    destination_hint = models.CharField(max_length=80, blank=True, help_text="Masked destination only.")
    provider = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending", db_index=True)
    provider_reference = models.CharField(max_length=160, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    attempted_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-attempted_at"]

    def __str__(self):
        return f"{self.get_channel_display()} {self.get_status_display()} for alert {self.alert_id}"
