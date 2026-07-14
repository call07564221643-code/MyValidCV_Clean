from django.contrib import admin

from .models import FinancialAssumption


@admin.register(FinancialAssumption)
class FinancialAssumptionAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "currency", "fixed_monthly_cost_total", "updated_at")
    list_filter = ("is_active", "currency")
    search_fields = ("name", "notes")
    fieldsets = (
        ("General", {
            "fields": ("name", "is_active", "currency", "notes"),
        }),
        ("Fixed Supplier Costs", {
            "fields": (
                "hosting_monthly_cost",
                "database_monthly_cost",
                "storage_backup_monthly_cost",
                "email_monthly_cost",
                "monitoring_monthly_cost",
                "software_tools_monthly_cost",
                "marketing_monthly_cost",
                "accounting_admin_monthly_cost",
            ),
        }),
        ("Plan Unit Costs", {
            "fields": (
                "free_user_monthly_cost",
                "plus_user_monthly_cost",
                "professional_user_monthly_cost",
                "enterprise_user_monthly_cost",
                "enterprise_batch_delivery_cost",
            ),
        }),
        ("Variable Processing Costs", {
            "fields": (
                "ai_cost_per_validation",
                "generated_cv_cost",
                "payment_percent_fee",
                "payment_fixed_fee",
            ),
        }),
        ("Balance Sheet Inputs", {
            "fields": ("cash_reserve", "accounts_payable", "tax_accrual_percent"),
        }),
    )
