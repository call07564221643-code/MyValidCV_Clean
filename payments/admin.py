from django.contrib import admin
from django.utils import timezone

from accounts.models import UserProfile
from .models import Invoice, PaymentTransaction, PaymentWebhookLog, Refund
from .views import activate_paid_transaction, send_receipt_email, set_subscription_inactive


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("checkout_reference", "user", "plan", "provider", "amount", "currency", "status", "created_at")
    list_filter = ("status", "provider", "plan", "currency", "created_at")
    search_fields = ("checkout_reference", "provider_checkout_id", "provider_transaction_id", "user__username", "user__email")
    readonly_fields = ("checkout_reference", "raw_response", "created_at", "updated_at")
    actions = ("mark_paid_and_activate", "mark_failed", "mark_refunded")

    @admin.action(description="Mark paid and activate selected user plans")
    def mark_paid_and_activate(self, request, queryset):
        for transaction in queryset.select_related("user", "plan"):
            activate_paid_transaction(transaction, raw_response={"manual_admin_activation": True})

    @admin.action(description="Mark selected payments failed")
    def mark_failed(self, request, queryset):
        queryset.update(status="failed")

    @admin.action(description="Record refund and revoke associated local access")
    def mark_refunded(self, request, queryset):
        for transaction in queryset.select_related("subscription"):
            transaction.status = "refunded"
            transaction.save(update_fields=["status", "updated_at"])
            if hasattr(transaction, "invoice"):
                transaction.invoice.status = "refunded"
                transaction.invoice.save(update_fields=["status"])
            if transaction.subscription and transaction.subscription.stripe_subscription_id:
                set_subscription_inactive(transaction.subscription.stripe_subscription_id, "cancelled")
            elif transaction.subscription:
                transaction.subscription.status = "cancelled"
                transaction.subscription.cancelled_at = timezone.now()
                transaction.subscription.save(update_fields=["status", "cancelled_at", "updated_at"])
                UserProfile.objects.update_or_create(user=transaction.user, defaults={"plan": "free"})


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "user", "amount", "currency", "status", "paid_at", "next_payment_date", "receipt_email_status")
    list_filter = ("status", "receipt_email_status", "currency", "issued_at")
    search_fields = ("invoice_number", "user__username", "user__email")
    readonly_fields = ("issued_at", "receipt_sent_at")
    actions = ("resend_receipts",)

    @admin.action(description="Resend receipt email for selected paid invoices")
    def resend_receipts(self, request, queryset):
        for invoice in queryset.select_related("transaction", "transaction__user", "transaction__plan"):
            if invoice.status != "paid":
                continue
            status = send_receipt_email(invoice.transaction)
            invoice.receipt_email_status = status
            invoice.receipt_email = invoice.transaction.user.email
            if status == "sent":
                invoice.receipt_sent_at = timezone.now()
            invoice.save(update_fields=["receipt_email_status", "receipt_email", "receipt_sent_at"])


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("transaction", "amount", "reason", "status", "created_at", "processed_at")
    list_filter = ("status", "created_at")
    search_fields = ("transaction__checkout_reference", "reason", "admin_notes")
    actions = ("approve_refunds", "mark_processed", "reject_refunds")

    @admin.action(description="Approve selected refunds")
    def approve_refunds(self, request, queryset):
        queryset.update(status="approved")

    @admin.action(description="Mark selected refunds processed")
    def mark_processed(self, request, queryset):
        queryset.update(status="processed", processed_at=timezone.now())

    @admin.action(description="Reject selected refunds")
    def reject_refunds(self, request, queryset):
        queryset.update(status="rejected")


@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "event_type", "checkout_reference", "is_processed", "created_at")
    list_filter = ("provider", "event_type", "is_processed", "created_at")
    search_fields = ("event_id", "checkout_reference", "error")
    readonly_fields = ("payload", "created_at")
