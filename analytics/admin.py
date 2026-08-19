from django.contrib import admin

from .models import FinanceFeedConnection, FinancialAssumption, FinancialEntry


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


@admin.register(FinancialEntry)
class FinancialEntryAdmin(admin.ModelAdmin):
    list_display = ("occurred_on", "direction", "category", "description", "amount", "currency", "source", "status")
    list_filter = ("direction", "status", "source", "currency", "category")
    search_fields = ("description", "external_reference", "provider", "notes")
    date_hierarchy = "occurred_on"
    autocomplete_fields = ("entered_by",)

    def save_model(self, request, obj, form, change):
        if not obj.entered_by_id:
            obj.entered_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(FinanceFeedConnection)
class FinanceFeedConnectionAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "status", "currency", "last_synced_at", "last_sync_status")
    list_filter = ("provider", "status", "currency")
    search_fields = ("name", "account_reference", "last_sync_status")
    readonly_fields = ("last_synced_at", "last_sync_status", "created_at", "updated_at")
