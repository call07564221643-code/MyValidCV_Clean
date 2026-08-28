from django.contrib import admin
from django.db.models import Sum
from django.utils import timezone
from governance.forms import OptimisticLockAdminForm

from .models import (
    AccessVoucher, AffiliateAgreementAcceptance, AnalyticsEvent, BulkPurchase, CampaignApproval,
    CommissionEntry, ConsentRecord, MarketingCampaign, PartnerProfile,
    ProviderConnection, ReferralAttribution, ReferralPartner, VoucherRedemption,
)


@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    form = OptimisticLockAdminForm
    list_display = ("organisation", "stage", "account_manager", "commission_type", "commission_value", "updated_at")
    list_filter = ("stage", "commission_type")
    search_fields = ("organisation__name", "agreement_reference", "account_manager__email")
    autocomplete_fields = ("organisation", "account_manager")
    readonly_fields = ("version",)


@admin.register(BulkPurchase)
class BulkPurchaseAdmin(admin.ModelAdmin):
    form = OptimisticLockAdminForm
    list_display = ("organisation", "plan", "quantity", "allocated_quantity", "status", "expires_at")
    list_filter = ("status", "plan", "currency")
    search_fields = ("organisation__name", "purchaser__email")
    autocomplete_fields = ("organisation", "purchaser", "plan", "transaction")
    readonly_fields = ("allocated_quantity", "created_at", "updated_at", "version")


@admin.register(AccessVoucher)
class AccessVoucherAdmin(admin.ModelAdmin):
    list_display = ("code", "organisation", "plan", "redemptions", "max_redemptions", "is_active", "valid_until")
    list_filter = ("is_active", "plan", "organisation__organisation_type")
    search_fields = ("code", "campaign_name", "organisation__name", "allowed_email_domain")
    autocomplete_fields = ("bulk_purchase", "organisation", "plan", "created_by")
    readonly_fields = ("redemptions", "created_at")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(VoucherRedemption)
class VoucherRedemptionAdmin(admin.ModelAdmin):
    list_display = ("voucher", "user", "redeemed_at", "expires_at")
    search_fields = ("voucher__code", "user__email", "voucher__organisation__name")
    readonly_fields = ("voucher", "user", "redeemed_at", "expires_at")

    def has_add_permission(self, request):
        return False


@admin.register(ReferralPartner)
class ReferralPartnerAdmin(admin.ModelAdmin):
    list_display = ("referral_code", "organisation", "is_active", "cookie_days", "commission_hold_days", "minimum_payout", "approved_at")
    list_filter = ("is_active",)
    search_fields = ("referral_code", "organisation__name")
    autocomplete_fields = ("organisation",)


@admin.register(AffiliateAgreementAcceptance)
class AffiliateAgreementAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("partner", "terms_version", "legal_name", "country", "accepted_by", "accepted_at")
    search_fields = ("partner__referral_code", "partner__organisation__name", "legal_name", "accepted_by__email")
    readonly_fields = tuple(field.name for field in AffiliateAgreementAcceptance._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ReferralAttribution)
class ReferralAttributionAdmin(admin.ModelAdmin):
    list_display = ("partner", "user", "source", "campaign", "first_seen_at", "converted_at")
    list_filter = ("source", "first_seen_at", "converted_at")
    search_fields = ("partner__referral_code", "user__email", "campaign", "conversion_reference")
    readonly_fields = ("first_seen_at",)


@admin.register(CommissionEntry)
class CommissionEntryAdmin(admin.ModelAdmin):
    list_display = ("partner", "amount", "currency", "status", "matures_at", "approved_by", "created_at", "paid_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("partner__referral_code", "transaction__checkout_reference")
    autocomplete_fields = ("partner", "attribution", "transaction", "approved_by")
    readonly_fields = (
        "status", "approved_by", "commissionable_amount", "commission_rate",
        "matures_at", "reversal_reason", "created_at", "paid_at",
    )
    actions = ("approve_commissions", "release_mature_commissions", "record_external_payout")

    @admin.action(description="Approve selected valid commissions")
    def approve_commissions(self, request, queryset):
        queryset.filter(status="pending").update(status="approved", approved_by=request.user)

    @admin.action(description="Release approved commissions whose hold period has ended")
    def release_mature_commissions(self, request, queryset):
        queryset.filter(status="approved", matures_at__lte=timezone.now()).update(status="payable")

    @admin.action(description="Record selected payable commissions as paid after external payout")
    def record_external_payout(self, request, queryset):
        recorded = 0
        for partner_id, currency in queryset.values_list("partner_id", "currency").distinct():
            partner_entries = queryset.filter(partner_id=partner_id, currency=currency, status="payable")
            total = partner_entries.aggregate(total=Sum("amount"))["total"] or 0
            partner = ReferralPartner.objects.get(pk=partner_id)
            if total >= partner.minimum_payout:
                recorded += partner_entries.update(status="paid", paid_at=timezone.now())
        self.message_user(request, f"Recorded {recorded} commission entries as externally paid. Below-threshold groups were left payable.")


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "provider", "is_granted", "policy_version", "granted_at", "withdrawn_at")
    list_filter = ("purpose", "provider", "is_granted")
    search_fields = ("user__email", "provider", "policy_version")
    readonly_fields = ("granted_at",)


@admin.register(ProviderConnection)
class ProviderConnectionAdmin(admin.ModelAdmin):
    form = OptimisticLockAdminForm
    list_display = ("provider", "status", "external_account_hint", "configured_by", "last_checked_at", "updated_at")
    list_filter = ("status", "provider")
    readonly_fields = ("connected_at", "last_checked_at", "updated_at", "version")

    def save_model(self, request, obj, form, change):
        obj.configured_by = request.user
        super().save_model(request, obj, form, change)


class CampaignApprovalInline(admin.TabularInline):
    model = CampaignApproval
    extra = 0
    readonly_fields = ("reviewer", "decision", "campaign_version", "notes", "decided_at")
    can_delete = False


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(admin.ModelAdmin):
    form = OptimisticLockAdminForm
    list_display = ("name", "channel", "objective", "budget", "currency", "status", "created_by", "approved_by", "updated_at")
    list_filter = ("channel", "status", "currency")
    search_fields = ("name", "objective", "audience_summary", "content_brief")
    readonly_fields = ("status", "approved_by", "published_at", "created_at", "updated_at", "version")
    actions = ("submit_for_review",)
    inlines = (CampaignApprovalInline,)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if change and form.changed_data:
            if obj.status in {"approved", "published"}:
                obj.status = "review"
                obj.approved_by = None
        super().save_model(request, obj, form, change)

    @admin.action(description="Submit selected campaigns for review")
    def submit_for_review(self, request, queryset):
        queryset.filter(status__in=["draft", "paused"]).update(status="review")

@admin.register(CampaignApproval)
class CampaignApprovalAdmin(admin.ModelAdmin):
    list_display = ("campaign", "reviewer", "decision", "campaign_version", "decided_at")
    list_filter = ("decision", "decided_at")
    readonly_fields = ("reviewer", "campaign_version", "decided_at")

    def has_add_permission(self, request):
        return request.user.has_perm("growth.approve_campaign")

    def save_model(self, request, obj, form, change):
        obj.reviewer = request.user
        obj.campaign_version = obj.campaign.version
        super().save_model(request, obj, form, change)
        campaign = obj.campaign
        if obj.decision == "approved":
            campaign.status = "approved"
            campaign.approved_by = request.user
        else:
            campaign.status = "draft" if obj.decision == "changes" else "paused"
            campaign.approved_by = None
        campaign.save(update_fields=["status", "approved_by", "updated_at"])


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "name", "user", "organisation", "source", "campaign")
    list_filter = ("name", "source", "occurred_at")
    search_fields = ("name", "user__email", "organisation__name", "campaign", "anonymous_id")
    readonly_fields = tuple(field.name for field in AnalyticsEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
