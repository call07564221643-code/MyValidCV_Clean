from .models import AnalyticsEvent, ReferralAttribution, ReferralPartner


class ReferralAttributionMiddleware:
    """Keep first-touch referral data in-session; persist only after analytics consent."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        referral_code = request.GET.get("ref", "").strip()
        if referral_code and "mvcv_referral" not in request.session:
            partner = ReferralPartner.objects.filter(referral_code__iexact=referral_code, is_active=True).first()
            if partner:
                request.session["mvcv_referral"] = {
                    "partner_id": partner.id,
                    "landing_path": request.path[:500],
                    "source": request.GET.get("utm_source", "")[:120],
                    "medium": request.GET.get("utm_medium", "")[:120],
                    "campaign": request.GET.get("utm_campaign", "")[:180],
                }
        if (
            request.user.is_authenticated
            and request.COOKIES.get("mvcv_analytics_consent") == "granted"
            and request.session.get("mvcv_referral")
        ):
            data = request.session.pop("mvcv_referral")
            attribution = ReferralAttribution.objects.create(
                partner_id=data["partner_id"], user=request.user,
                landing_path=data["landing_path"], source=data["source"],
                medium=data["medium"], campaign=data["campaign"],
            )
            AnalyticsEvent.objects.create(
                name="referral_attributed", user=request.user,
                organisation=attribution.partner.organisation,
                source=attribution.source, campaign=attribution.campaign,
                properties={"attribution_id": attribution.id},
            )
        return self.get_response(request)
