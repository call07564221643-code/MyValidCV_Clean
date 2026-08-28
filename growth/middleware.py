from datetime import timedelta

from django.utils import timezone

from .models import AnalyticsEvent, ReferralAttribution, ReferralPartner


class ReferralAttributionMiddleware:
    """Keep first-touch referral data in-session; persist only after analytics consent."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        referral_code = request.GET.get("ref", "").strip()
        if referral_code and "mvcv_referral" not in request.session:
            partner = ReferralPartner.objects.select_related(
                "organisation", "organisation__partner_profile",
            ).filter(referral_code__iexact=referral_code).first()
            if partner and partner.is_eligible():
                request.session["mvcv_referral"] = {
                    "partner_id": partner.id,
                    "landing_path": request.path[:500],
                    "source": request.GET.get("utm_source", "")[:120],
                    "medium": request.GET.get("utm_medium", "")[:120],
                    "campaign": request.GET.get("utm_campaign", "")[:180],
                    "captured_at": timezone.now().isoformat(),
                }
        if (
            request.user.is_authenticated
            and request.COOKIES.get("mvcv_referral_consent") == "granted"
            and request.session.get("mvcv_referral")
        ):
            data = request.session.pop("mvcv_referral")
            partner = ReferralPartner.objects.select_related(
                "organisation", "organisation__partner_profile",
            ).filter(pk=data["partner_id"]).first()
            captured_at = timezone.datetime.fromisoformat(data["captured_at"])
            if not partner or not partner.is_eligible() or captured_at + timedelta(days=partner.cookie_days) < timezone.now():
                return self.get_response(request)
            attribution, _created = ReferralAttribution.objects.get_or_create(
                user=request.user, converted_at__isnull=True,
                defaults={
                    "partner": partner, "landing_path": data["landing_path"],
                    "source": data["source"], "medium": data["medium"],
                    "campaign": data["campaign"],
                    "expires_at": captured_at + timedelta(days=partner.cookie_days),
                    "consent_source": "affiliate_consent",
                },
            )
            AnalyticsEvent.objects.create(
                name="referral_attributed", user=request.user,
                organisation=attribution.partner.organisation,
                source=attribution.source, campaign=attribution.campaign,
                properties={"attribution_id": attribution.id},
            )
        return self.get_response(request)
