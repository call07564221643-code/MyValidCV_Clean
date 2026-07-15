from django.contrib import admin
from django.utils import timezone

from accounts.models import UserProfile

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
        "monthly_analysis_limit",
        "monthly_bulk_cv_limit",
        "is_active",
    )
    list_filter = ("is_active", "billing_interval", "currency")
    search_fields = ("name", "code", "description", "stripe_price_id")
    list_editable = ("is_active", "price", "cv_limit", "monthly_analysis_limit", "monthly_bulk_cv_limit")


@admin.register(CustomerSubscription)
class CustomerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "stripe_subscription_id", "started_at", "current_period_end", "updated_at")
    list_filter = ("status", "plan", "started_at")
    search_fields = ("user__username", "user__email", "plan__name", "stripe_customer_id", "stripe_subscription_id")
    autocomplete_fields = ("user", "plan")
    actions = ("mark_active", "mark_cancelled", "mark_past_due")

    @admin.action(description="Mark selected subscriptions active")
    def mark_active(self, request, queryset):
        for subscription in queryset.select_related("user", "plan"):
            subscription.status = "active"
            subscription.cancelled_at = None
            subscription.save(update_fields=["status", "cancelled_at", "updated_at"])
            UserProfile.objects.update_or_create(user=subscription.user, defaults={"plan": subscription.plan.code})

    @admin.action(description="Mark selected subscriptions cancelled")
    def mark_cancelled(self, request, queryset):
        for subscription in queryset.select_related("user"):
            subscription.status = "cancelled"
            subscription.cancelled_at = timezone.now()
            subscription.save(update_fields=["status", "cancelled_at", "updated_at"])
            UserProfile.objects.update_or_create(user=subscription.user, defaults={"plan": "free"})

    @admin.action(description="Mark selected subscriptions past due")
    def mark_past_due(self, request, queryset):
        for subscription in queryset.select_related("user"):
            subscription.status = "past_due"
            subscription.save(update_fields=["status", "updated_at"])
            UserProfile.objects.update_or_create(user=subscription.user, defaults={"plan": "free"})


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "percent_off", "amount_off", "currency", "redemptions", "max_redemptions", "is_active")
    list_filter = ("is_active", "currency")
    search_fields = ("code", "description")
    list_editable = ("is_active",)
