from decimal import Decimal

from django.core.management.base import BaseCommand

from subscriptions.models import DiscountCode, SubscriptionPlan


class Command(BaseCommand):
    help = "Create default MyValidCV subscription plans and a demo discount code."

    def handle(self, *args, **options):
        plans = [
            {
                "code": "free",
                "name": "Free",
                "description": "Start with one CV and two ATS checks per day.",
                "price": Decimal("0.00"),
                "cv_limit": 1,
                "daily_analysis_limit": 2,
                "monthly_bulk_cv_limit": 0,
                "includes_generated_cv": False,
                "includes_job_url": False,
                "includes_deadline_alerts": False,
                "includes_enterprise_reports": False,
                "sort_order": 1,
            },
            {
                "code": "plus",
                "name": "Plus",
                "description": "For active job seekers who need tailored CV drafts and more daily checks.",
                "price": Decimal("7.99"),
                "cv_limit": 10,
                "daily_analysis_limit": 5,
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
                "description": "Bulk CV ranking for recruiters and hiring teams.",
                "price": Decimal("199.00"),
                "cv_limit": 200,
                "daily_analysis_limit": 200,
                "monthly_bulk_cv_limit": 200,
                "includes_generated_cv": True,
                "includes_job_url": True,
                "includes_deadline_alerts": True,
                "includes_enterprise_reports": True,
                "sort_order": 3,
            },
        ]

        for data in plans:
            SubscriptionPlan.objects.update_or_create(code=data["code"], defaults=data)

        DiscountCode.objects.get_or_create(
            code="FOUNDER25",
            defaults={
                "description": "Founding customer launch discount",
                "percent_off": 25,
                "currency": "GBP",
                "is_active": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("Default plans seeded: Free, Plus, Enterprise Starter. Demo discount: FOUNDER25"))
