from decimal import Decimal

from django.db import models


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
