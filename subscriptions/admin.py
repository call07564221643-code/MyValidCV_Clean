from django.contrib import admin

from .models import CustomerSubscription, DiscountCode, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "price",
        "currency",
        "billing_interval",
        "stripe_price_id",
        "cv_limit",
        "daily_analysis_limit",
        "monthly_bulk_cv_limit",
        "is_active",
    )
    list_filter = ("is_active", "billing_interval", "currency")
    search_fields = ("name", "code", "description", "stripe_price_id")
    list_editable = ("is_active", "price", "cv_limit", "daily_analysis_limit", "monthly_bulk_cv_limit")


@admin.register(CustomerSubscription)
class CustomerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "stripe_subscription_id", "started_at", "current_period_end", "updated_at")
    list_filter = ("status", "plan", "started_at")
    search_fields = ("user__username", "user__email", "plan__name", "stripe_customer_id", "stripe_subscription_id")
    autocomplete_fields = ("user", "plan")
    actions = ("mark_active", "mark_cancelled", "mark_past_due")

    @admin.action(description="Mark selected subscriptions active")
    def mark_active(self, request, queryset):
        queryset.update(status="active", cancelled_at=None)

    @admin.action(description="Mark selected subscriptions cancelled")
    def mark_cancelled(self, request, queryset):
        queryset.update(status="cancelled")

    @admin.action(description="Mark selected subscriptions past due")
    def mark_past_due(self, request, queryset):
        queryset.update(status="past_due")


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "percent_off", "amount_off", "currency", "redemptions", "max_redemptions", "is_active")
    list_filter = ("is_active", "currency")
    search_fields = ("code", "description")
    list_editable = ("is_active",)
