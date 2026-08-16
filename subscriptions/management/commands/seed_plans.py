from decimal import Decimal

from django.core.management.base import BaseCommand

from subscriptions.models import SubscriptionPlan


class Command(BaseCommand):
    help = "Idempotently create/update the production MyValidCV plan catalogue."

    def handle(self, *args, **options):
        plans = [
            {
                "code": "free",
                "name": "Free",
                "description": "Store one CV for 30 days and test up to five job roles each month.",
                "price": Decimal("0.00"),
                "cv_limit": 1,
                "monthly_analysis_limit": 5,
                "monthly_bulk_cv_limit": 0,
                "includes_generated_cv": False,
                "includes_job_url": True,
                "includes_deadline_alerts": True,
                "includes_enterprise_reports": False,
                "sort_order": 1,
            },
            {
                "code": "plus",
                "name": "Plus",
                "description": "Twenty monthly role checks with tailored CV rewrites and cover letters.",
                "price": Decimal("4.99"),
                "cv_limit": 1,
                "monthly_analysis_limit": 20,
                "monthly_bulk_cv_limit": 0,
                "includes_generated_cv": True,
                "includes_job_url": True,
                "includes_deadline_alerts": True,
                "includes_enterprise_reports": False,
                "sort_order": 2,
            },
            {
                "code": "enterprise",
                "name": "Enterprise Starter",
                "description": "Bulk screening of 50 CVs per month without CV rewriting or cover letters.",
                "price": Decimal("49.00"),
                "cv_limit": 50,
                "monthly_analysis_limit": 50,
                "monthly_bulk_cv_limit": 50,
                "includes_generated_cv": False,
                "includes_job_url": True,
                "includes_deadline_alerts": False,
                "includes_enterprise_reports": True,
                "sort_order": 3,
            },
        ]

        for data in plans:
            SubscriptionPlan.objects.update_or_create(code=data["code"], defaults=data)

        self.stdout.write(self.style.SUCCESS("Plan catalogue synchronized: Free, Plus, Enterprise Starter."))
