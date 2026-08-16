"""Single source of truth for plan access and usage limits."""

from dataclasses import dataclass

from django.utils import timezone

from .models import CustomerSubscription, SubscriptionPlan


PLAN_DEFAULTS = {
    "free": {
        "cv_limit": 1,
        "analysis_limit": 5,
        "bulk_limit": 0,
        "generated_documents": False,
        "job_url": True,
        "deadline_alerts": True,
        "enterprise_reports": False,
    },
    "plus": {
        "cv_limit": 1,
        "analysis_limit": 20,
        "bulk_limit": 0,
        "generated_documents": True,
        "job_url": True,
        "deadline_alerts": True,
        "enterprise_reports": False,
    },
    "enterprise": {
        "cv_limit": 50,
        "analysis_limit": 50,
        "bulk_limit": 50,
        "generated_documents": False,
        "job_url": True,
        "deadline_alerts": False,
        "enterprise_reports": True,
    },
}


@dataclass(frozen=True)
class Entitlements:
    code: str
    cv_limit: int
    analysis_limit: int
    bulk_limit: int
    generated_documents: bool
    job_url: bool
    deadline_alerts: bool
    enterprise_reports: bool
    subscription: CustomerSubscription | None = None
    plan: SubscriptionPlan | None = None

    @property
    def is_paid(self):
        return bool(self.subscription and self.code != "free")


def get_active_subscription(user):
    """Return a current paid/trial subscription; expired rows fail closed."""
    if not getattr(user, "is_authenticated", False):
        return None
    subscription = CustomerSubscription.objects.filter(
        user=user,
        status__in=("active", "trialing"),
    ).select_related("plan").first()
    if subscription and (
        subscription.current_period_end is None
        or subscription.current_period_end > timezone.now()
    ):
        return subscription
    return None


def _values_from_plan(plan, fallback):
    if not plan:
        return fallback
    return {
        "cv_limit": plan.cv_limit,
        "analysis_limit": plan.monthly_analysis_limit,
        "bulk_limit": plan.monthly_bulk_cv_limit,
        "generated_documents": plan.includes_generated_cv,
        "job_url": plan.includes_job_url,
        "deadline_alerts": plan.includes_deadline_alerts,
        "enterprise_reports": plan.includes_enterprise_reports,
    }


def get_entitlements(user):
    """Resolve effective access from verified subscription state and plan rows.

    UserProfile.plan is a display/cache field and is deliberately not trusted as
    proof of payment. Superusers receive Enterprise operations access.
    """
    subscription = get_active_subscription(user)
    if getattr(user, "is_superuser", False):
        code = "enterprise"
        plan = SubscriptionPlan.objects.filter(code=code, is_active=True).first()
        values = _values_from_plan(plan, PLAN_DEFAULTS[code])
        return Entitlements(code=code, subscription=subscription, plan=plan, **values)

    if subscription and subscription.plan.code in PLAN_DEFAULTS:
        code = subscription.plan.code
        values = _values_from_plan(subscription.plan, PLAN_DEFAULTS[code])
        return Entitlements(code=code, subscription=subscription, plan=subscription.plan, **values)

    code = "free"
    plan = SubscriptionPlan.objects.filter(code=code, is_active=True).first()
    values = _values_from_plan(plan, PLAN_DEFAULTS[code])
    return Entitlements(code=code, plan=plan, **values)
