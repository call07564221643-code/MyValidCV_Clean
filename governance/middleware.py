from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


OWNER_STEP_UP_SECONDS = 15 * 60


class OwnerGovernanceStepUpMiddleware:
    """Require recent owner password verification for new governance admin areas."""

    protected_prefixes = ("/admin/governance/", "/admin/growth/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.is_superuser and request.path.startswith(self.protected_prefixes):
            verified_at = request.session.get("owner_governance_verified_at", 0)
            if timezone.now().timestamp() - verified_at > OWNER_STEP_UP_SECONDS:
                target = reverse("owner_governance_unlock")
                return redirect(f"{target}?{urlencode({'next': request.get_full_path()})}")
        return self.get_response(request)
