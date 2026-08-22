from django.conf import settings


def platform_integrations(request):
    has_partner_workspace = False
    if request.user.is_authenticated:
        has_partner_workspace = request.user.organisation_memberships.filter(is_active=True).exists()
    return {
        "canonical_url": request.build_absolute_uri(request.path),
        "google_analytics_id": settings.GOOGLE_ANALYTICS_ID,
        "google_site_verification": settings.GOOGLE_SITE_VERIFICATION,
        "analytics_consent": request.COOKIES.get("mvcv_analytics_consent", ""),
        "has_partner_workspace": has_partner_workspace,
        "seo_robots": "index, follow" if request.path in {"/", "/pricing/", "/privacy-policy/"} else "noindex, nofollow",
    }
