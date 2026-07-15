from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import CustomerSubscription, SubscriptionPlan
from .services import get_entitlements


class EntitlementPolicyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("policy-user", password="password")
        self.free = SubscriptionPlan.objects.create(
            code="free", name="Free", price="0", monthly_analysis_limit=5,
        )
        self.plus = SubscriptionPlan.objects.create(
            code="plus", name="Plus", price="4.99", monthly_analysis_limit=20,
            includes_generated_cv=True, includes_job_url=True,
            includes_deadline_alerts=True,
        )

    def test_profile_label_alone_never_grants_paid_features(self):
        self.user.profile.plan = "plus"
        self.user.profile.save(update_fields=["plan"])
        access = get_entitlements(self.user)
        self.assertEqual(access.code, "free")
        self.assertFalse(access.generated_documents)

    def test_current_subscription_grants_database_plan_features(self):
        CustomerSubscription.objects.create(
            user=self.user,
            plan=self.plus,
            status="active",
            current_period_end=timezone.now() + timedelta(days=30),
        )
        access = get_entitlements(self.user)
        self.assertEqual(access.code, "plus")
        self.assertEqual(access.analysis_limit, 20)
        self.assertTrue(access.generated_documents)

    def test_expired_subscription_fails_closed_to_free(self):
        CustomerSubscription.objects.create(
            user=self.user,
            plan=self.plus,
            status="active",
            current_period_end=timezone.now() - timedelta(seconds=1),
        )
        self.assertEqual(get_entitlements(self.user).code, "free")
