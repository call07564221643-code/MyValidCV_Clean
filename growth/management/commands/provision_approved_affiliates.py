from django.contrib.auth.models import Permission, User
from django.core.management.base import BaseCommand, CommandError

from governance.models import AuditEvent
from growth.affiliate_workflow import approve_application
from growth.models import AffiliateApplication


class Command(BaseCommand):
    help = "Provision previously approved applications and optionally grant a named reviewer limited affiliate permissions."

    def add_arguments(self, parser):
        parser.add_argument("--reviewer-email", required=True)
        parser.add_argument("--grant-reviewer", action="store_true")

    def handle(self, *args, **options):
        try:
            reviewer = User.objects.get(email__iexact=options["reviewer_email"], is_active=True)
        except (User.DoesNotExist, User.MultipleObjectsReturned) as exc:
            raise CommandError("Exactly one active reviewer account must match the email.") from exc
        if options["grant_reviewer"]:
            permissions = Permission.objects.filter(content_type__app_label="growth",
                codename__in=["review_affiliate_application", "approve_commission"])
            reviewer.user_permissions.add(*permissions)
            AuditEvent.objects.create(actor=reviewer, action="affiliate.reviewer_access_granted",
                target_type="User", target_id=str(reviewer.pk),
                summary="Owner-authorised affiliate review and payout permissions granted; no staff/superuser elevation.")
            reviewer = User.objects.get(pk=reviewer.pk)
        for application in AffiliateApplication.objects.filter(status="approved", partner__isnull=True):
            partner = approve_application(application.pk, reviewer)
            self.stdout.write(f"Provisioned application {application.pk}, partner {partner.pk}, expires {partner.valid_until.isoformat()}.")
