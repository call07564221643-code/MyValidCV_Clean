from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


ROLE_PERMISSIONS = {
    "Partnerships Manager": [
        "view_organisation", "add_organisation", "change_organisation",
        "view_organisationmembership", "add_organisationmembership", "change_organisationmembership",
        "view_partnerprofile", "add_partnerprofile", "change_partnerprofile",
        "view_referralpartner", "add_referralpartner", "change_referralpartner",
    ],
    "Bulk Access Manager": [
        "view_organisation", "view_bulkpurchase", "add_bulkpurchase", "change_bulkpurchase",
        "approve_bulk_purchase", "view_accessvoucher", "add_accessvoucher",
        "change_accessvoucher", "issue_access_voucher", "view_voucherredemption",
    ],
    "Marketing Manager": [
        "view_marketingcampaign", "add_marketingcampaign", "change_marketingcampaign",
        "view_referralpartner", "view_referralattribution", "view_analyticsevent",
    ],
    "Campaign Approver": [
        "view_marketingcampaign", "approve_campaign", "publish_campaign",
        "view_campaignapproval", "add_campaignapproval",
    ],
    "Partner Finance Manager": [
        "view_bulkpurchase", "view_commissionentry", "change_commissionentry",
        "approve_commission", "view_paymenttransaction", "view_invoice", "view_refund",
        "view_financialentry", "add_financialentry", "change_financialentry",
        "view_financefeedconnection", "add_financefeedconnection", "change_financefeedconnection",
        "sync_finance_feed", "view_financialassumption", "change_financialassumption",
    ],
    "Privacy Manager": [
        "view_consentrecord", "change_consentrecord", "view_auditevent",
        "view_sensitive_audit",
    ],
    "Integration Manager": [
        "view_providerconnection", "add_providerconnection", "change_providerconnection",
        "configure_provider",
    ],
    "Growth Analyst": [
        "view_analyticsevent", "view_referralattribution", "view_referralpartner",
        "view_marketingcampaign", "view_bulkpurchase", "view_voucherredemption",
        "view_commissionentry",
    ],
    "Recruitment Insights Manager": [
        "view_atsresult", "view_enterprisebatch", "view_enterprisecandidateresult",
        "view_jobfamily", "view_roletemplate", "view_skill", "view_qualification",
    ],
    "Customer Experience Manager": [
        "view_experiencefeedback",
    ],
}


class Command(BaseCommand):
    help = "Create idempotent least-privilege management roles."

    def handle(self, *args, **options):
        for role_name, codenames in ROLE_PERMISSIONS.items():
            group, _created = Group.objects.get_or_create(name=role_name)
            permissions = Permission.objects.filter(codename__in=codenames)
            group.permissions.set(permissions)
        self.stdout.write(self.style.SUCCESS(f"Management roles synchronized: {len(ROLE_PERMISSIONS)}."))
