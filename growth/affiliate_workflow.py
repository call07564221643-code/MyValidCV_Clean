"""Audited affiliate onboarding, email delivery and cancellation."""
import logging
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from governance.models import AuditEvent, Organisation, OrganisationMembership
from .models import AffiliateApplication, PartnerProfile, ReferralPartner

logger = logging.getLogger(__name__)


def require_reviewer(actor):
    if not (actor.is_active and (actor.is_superuser or actor.has_perm("growth.review_affiliate_application"))):
        raise PermissionDenied


def email_referral_code(partner_id, force=False):
    partner = ReferralPartner.objects.select_related("organisation__primary_contact").get(pk=partner_id)
    if partner.cancelled_at or (partner.code_emailed_at and not force):
        return
    recipient = partner.organisation.primary_contact
    try:
        if settings.EMAIL_BACKEND in {
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.dummy.EmailBackend",
            "django.core.mail.backends.filebased.EmailBackend",
        }:
            raise ValueError("A delivering email backend must be configured")
        if not recipient or not recipient.email:
            raise ValueError("Affiliate email missing")
        sent = send_mail(
            "Your MyValidCV affiliate code",
            f"Your affiliate application is approved. Your code is {partner.referral_code}.\n"
            f"Customers receive {partner.customer_discount_percent}% off. You earn 20% of the discounted payment retained by MyValidCV.\n"
            f"Valid until {partner.valid_until:%d %B %Y %H:%M UTC}.\n"
            "Before sharing it, enter your payout details and accept the agreement in your dashboard.\n"
            f"Dashboard: {settings.PUBLIC_SITE_URL}{reverse('partner_dashboard')}\n"
            f"Referral link: {settings.PUBLIC_SITE_URL}/?ref={partner.referral_code}\n"
            "The agreement explains refunds, the hold period, minimum payout and cancellation following a dashboard warning.",
            settings.DEFAULT_FROM_EMAIL, [recipient.email], fail_silently=False,
        )
        if not sent:
            raise ValueError("Email backend did not confirm delivery")
        ReferralPartner.objects.filter(pk=partner_id).update(code_emailed_at=timezone.now(), email_error="")
    except Exception:
        logger.exception("Affiliate code email failed for partner %s", partner_id)
        ReferralPartner.objects.filter(pk=partner_id).update(email_error="Email could not be sent; use Resend code to retry.")


@transaction.atomic
def approve_application(application_id, actor, waiver_reason=""):
    require_reviewer(actor)
    app = AffiliateApplication.objects.select_for_update().select_related("user", "partner").get(pk=application_id)
    if app.status in {"declined", "withdrawn"}:
        raise ValueError("Declined or withdrawn applications cannot be approved.")
    if app.partner_id:
        return app.partner
    if app.status != "approved" and app.meeting_status != "completed" and not waiver_reason.strip():
        raise ValueError("Complete the meeting or provide a reason for a meeting waiver.")
    now = timezone.now()
    try:
        end = now.replace(year=now.year + 1)
    except ValueError:
        end = now.replace(year=now.year + 1, day=28)
    organisation = Organisation.objects.create(
        name=app.legal_name, slug=f"affiliate-{app.pk}-{secrets.token_hex(6)}",
        organisation_type=app.applicant_type if app.applicant_type in dict(Organisation.TYPE_CHOICES) else "other",
        status="active", primary_contact=app.user, approved_at=now, website=app.website,
    )
    OrganisationMembership.objects.create(organisation=organisation, user=app.user, role="owner", invited_by=actor)
    PartnerProfile.objects.create(organisation=organisation, stage="active", commission_type="percent",
                                  commission_value=Decimal("20.00"), agreement_starts_at=now.date(), agreement_ends_at=end.date())
    # Globally unique application id makes collisions impossible between approvals.
    code = f"{slugify(app.legal_name)[:35] or 'affiliate'}-{app.pk}-{secrets.token_hex(5)}".lower()
    partner = ReferralPartner.objects.create(organisation=organisation, referral_code=code,
        approved_at=now, valid_until=end, customer_discount_percent=20, terms_version="affiliate-20-v2")
    app.partner = partner
    app.status = "approved"
    app.reviewed_by = actor
    app.decided_at = app.decided_at or now
    if waiver_reason.strip():
        app.owner_notes = (app.owner_notes + "\nMeeting waived: " + waiver_reason.strip()).strip()
    app.save(update_fields=["partner", "status", "reviewed_by", "decided_at", "owner_notes", "updated_at"])
    AuditEvent.objects.create(actor=actor, action="affiliate.approved_and_provisioned", target_type="AffiliateApplication",
        target_id=str(app.pk), summary="Approved and issued one-year code: 20% customer discount and 20% affiliate commission.",
        metadata={"waiver_reason": waiver_reason.strip(), "partner_id": partner.pk, "valid_until": end.isoformat()})
    transaction.on_commit(lambda: email_referral_code(partner.pk))
    return partner


@transaction.atomic
def manage_code(partner_id, actor, action, message=""):
    require_reviewer(actor)
    partner = ReferralPartner.objects.select_for_update().get(pk=partner_id)
    now = timezone.now()
    if action == "warn":
        if partner.cancelled_at or not message.strip():
            raise ValueError("Enter a warning for an uncancelled code.")
        partner.warning_message = message.strip()[:4000]
        partner.warned_at = now
        partner.save(update_fields=["warning_message", "warned_at"])
    elif action == "cancel":
        if not partner.warned_at or not partner.warning_message:
            raise ValueError("Send a dashboard warning before cancelling this code.")
        if partner.cancelled_at:
            return partner
        partner.is_active = False
        partner.cancelled_at = now
        partner.save(update_fields=["is_active", "cancelled_at"])
    elif action == "resend":
        transaction.on_commit(lambda: email_referral_code(partner.pk, force=True))
    else:
        raise ValueError("Unknown code action.")
    AuditEvent.objects.create(actor=actor, action=f"affiliate.code_{action}", target_type="ReferralPartner",
        target_id=str(partner.pk), summary=f"Affiliate code action: {action}.")
    return partner
