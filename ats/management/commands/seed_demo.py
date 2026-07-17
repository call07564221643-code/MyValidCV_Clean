from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import SocialAuthProvider, UserProfile
from ats.models import (
    ApplicationReminder,
    ATSResult,
    CV,
    CVStorage,
    EnterpriseBatch,
    EnterpriseCandidateResult,
    GeneratedCoverLetter,
    GeneratedCV,
    JobRole,
)
from payments.models import Invoice, PaymentTransaction, PaymentWebhookLog, Refund
from subscriptions.models import CustomerSubscription, DiscountCode, SubscriptionPlan


ROLE_DATA = [
    ("demo_alice", "Alice", "Morgan", "alice@example.com", "Django Developer", 88, "free"),
    ("demo_ben", "Ben", "Carter", "ben@example.com", "Data Analyst", 74, "free"),
    ("demo_chloe", "Chloe", "Patel", "chloe@example.com", "Frontend Developer", 67, "plus"),
    ("demo_daniel", "Daniel", "Evans", "daniel@example.com", "Project Manager", 81, "plus"),
    ("demo_emma", "Emma", "Wright", "emma@example.com", "Customer Success Manager", 62, "free"),
    ("demo_faisal", "Faisal", "Khan", "faisal@example.com", "Backend API Engineer", 91, "plus"),
    ("demo_grace", "Grace", "Taylor", "grace@example.com", "Junior Python Developer", 58, "free"),
    ("demo_hannah", "Hannah", "Brown", "hannah@example.com", "Business Analyst", 70, "plus"),
    ("demo_isaac", "Isaac", "Wilson", "isaac@example.com", "DevOps Engineer", 76, "enterprise"),
    ("demo_julia", "Julia", "Green", "julia@example.com", "Product Coordinator", 64, "enterprise"),
    ("demo_kareem", "Kareem", "Saleh", "kareem@example.com", "Cloud Support Engineer", 84, "plus"),
    ("demo_lina", "Lina", "Haddad", "lina@example.com", "HR Coordinator", 69, "free"),
    ("demo_marcus", "Marcus", "Reed", "marcus@example.com", "QA Tester", 73, "plus"),
    ("demo_nora", "Nora", "Ali", "nora@example.com", "Marketing Specialist", 86, "free"),
    ("demo_omar", "Omar", "Nasser", "omar@example.com", "Database Administrator", 79, "enterprise"),
    ("demo_priya", "Priya", "Shah", "priya@example.com", "Product Manager", 82, "plus"),
    ("demo_quinn", "Quinn", "Miller", "quinn@example.com", "Technical Writer", 61, "free"),
    ("demo_rania", "Rania", "Yousef", "rania@example.com", "Finance Analyst", 77, "plus"),
    ("demo_sam", "Sam", "Brooks", "sam@example.com", "IT Support Analyst", 72, "free"),
    ("demo_tara", "Tara", "Stone", "tara@example.com", "Recruitment Lead", 90, "enterprise"),
]


class Command(BaseCommand):
    help = "Create 20 demo users and linked records across the main MyValidCV tables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--per-plan",
            type=int,
            default=0,
            help="Create this many demo users for each plan category: free, plus, and enterprise.",
        )

    def handle(self, *args, **options):
        self.ensure_core_reference_data()

        password = "DemoPass123!"
        role_data = self.build_role_data(options["per_plan"]) if options["per_plan"] else ROLE_DATA
        counters = {
            "users": 0,
            "profiles": 0,
            "storages": 0,
            "cvs": 0,
            "jobs": 0,
            "results": 0,
            "generated_cvs": 0,
            "generated_cover_letters": 0,
            "reminders": 0,
            "subscriptions": 0,
            "payments": 0,
            "invoices": 0,
            "refunds": 0,
            "enterprise_batches": 0,
            "enterprise_candidates": 0,
            "webhooks": 0,
        }

        for index, (username, first_name, last_name, email, job_title, score, plan_code) in enumerate(role_data, start=1):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "is_active": True,
                },
            )
            if created:
                user.set_password(password)
                user.save()
                counters["users"] += 1
            else:
                changed = False
                for field, value in {"first_name": first_name, "last_name": last_name, "email": email}.items():
                    if getattr(user, field) != value:
                        setattr(user, field, value)
                        changed = True
                if changed:
                    user.save(update_fields=["first_name", "last_name", "email"])

            profile, created = UserProfile.objects.get_or_create(user=user)
            counters["profiles"] += int(created)
            profile.plan = plan_code
            profile.analyses_this_month = 1 if plan_code == "free" else min(index % 5 + 1, profile.get_analysis_limit())
            profile.save(update_fields=["plan", "analyses_this_month"])

            storage, created = CVStorage.objects.get_or_create(
                user=user,
                defaults={
                    "storage_limit": profile.get_cv_limit() * 1024 * 1024,
                    "auto_delete_enabled": plan_code == "free",
                },
            )
            counters["storages"] += int(created)

            cv_title = f"{first_name} {last_name} CV"
            cv = CV.objects.filter(user=user, title=cv_title).first()
            cv_text = self.build_cv_text(first_name, last_name, email, job_title)
            if cv is None:
                cv = CV(
                    user=user,
                    storage=storage,
                    title=cv_title,
                    original_filename=f"{username}_cv.txt",
                    mime_type="text/plain",
                    file_size=len(cv_text.encode("utf-8")),
                    validation_status="valid",
                    is_valid_cv=True,
                    validation_notes="Demo CV passed readiness validation.",
                )
                cv.file.save(f"{username}_cv.txt", ContentFile(cv_text), save=True)
                counters["cvs"] += 1
            else:
                cv.storage = storage
                cv.original_filename = cv.original_filename or f"{username}_cv.txt"
                cv.mime_type = cv.mime_type or "text/plain"
                cv.file_size = cv.file_size or len(cv_text.encode("utf-8"))
                cv.validation_status = "valid"
                cv.is_valid_cv = True
                cv.validation_notes = "Demo CV passed readiness validation."
                cv.save(update_fields=["storage", "original_filename", "mime_type", "file_size", "validation_status", "is_valid_cv", "validation_notes", "updated_at"])
            storage.refresh_used_storage()

            job_role, created = JobRole.objects.get_or_create(
                user=user,
                title=job_title,
                defaults={
                    "company": f"Demo Company {index}",
                    "description": self.build_job_description(job_title),
                    "source_type": ["text", "url", "file"][index % 3],
                    "source_url": f"https://careers.example.com/jobs/{username}" if index % 3 == 1 else "",
                    "deadline": timezone.localdate() + timedelta(days=7 + index),
                },
            )
            counters["jobs"] += int(created)

            matched = ["python", "django", "sql", "communication"]
            missing = ["postgresql", "api testing"] if score < 80 else ["postgresql"]
            metrics = {
                "skills": score,
                "keywords": min(100, score + 4),
                "experience": min(100, score + 8),
                "format": 88,
                "total": score,
                "matched_count": len(matched),
                "missing_count": len(missing),
            }
            result, created = ATSResult.objects.get_or_create(
                user=user,
                cv=cv,
                job_role=job_role,
                job_title=job_title,
                defaults={
                    "job_description": job_role.description,
                    "score": score,
                    "matched_skills": ", ".join(matched),
                    "missing_skills": ", ".join(missing),
                    "recommendation": "Tailor the CV summary and add measurable evidence for missing skills where truthful.",
                    "metrics": metrics,
                    "status": "completed",
                },
            )
            counters["results"] += int(created)
            if not created:
                result.job_role = job_role
                result.job_description = job_role.description
                result.score = score
                result.metrics = metrics
                result.status = "completed"
                result.save(update_fields=["job_role", "job_description", "score", "metrics", "status", "updated_at"])

            generated_cv, created = GeneratedCV.objects.get_or_create(
                user=user,
                original_cv=cv,
                ats_result=result,
                defaults={
                    "title": f"{cv.title} tailored for {job_title}",
                    "content": self.build_generated_cv(cv.title, job_title, score),
                },
            )
            counters["generated_cvs"] += int(created)
            if not created:
                generated_cv.title = f"{cv.title} tailored for {job_title}"
                generated_cv.content = self.build_generated_cv(cv.title, job_title, score)
                generated_cv.save(update_fields=["title", "content"])

            cover_letter, created = GeneratedCoverLetter.objects.get_or_create(
                user=user,
                ats_result=result,
                defaults={
                    "content": self.build_cover_letter(first_name, last_name, job_title, matched, score),
                },
            )
            counters["generated_cover_letters"] += int(created)
            if not created:
                cover_letter.content = self.build_cover_letter(first_name, last_name, job_title, matched, score)
                cover_letter.save(update_fields=["content"])

            _reminder, created = ApplicationReminder.objects.get_or_create(
                user=user,
                job_role=job_role,
                defaults={
                    "reminder_date": max(timezone.localdate(), job_role.deadline - timedelta(days=2)),
                    "note": "Demo reminder: apply before the deadline.",
                    "is_sent": False,
                },
            )
            counters["reminders"] += int(created)

            plan = SubscriptionPlan.objects.get(code=plan_code)
            subscription, created = CustomerSubscription.objects.update_or_create(
                user=user,
                defaults={
                    "plan": plan,
                    "status": "active",
                    "started_at": timezone.now() - timedelta(days=index),
                    "current_period_end": None if plan.price == Decimal("0.00") else timezone.now() + timedelta(days=30 - index % 20),
                    "admin_notes": "Demo subscription created by seed_demo.",
                },
            )
            counters["subscriptions"] += int(created)

            demo_reference = f"DEMO-{username.upper()}"

            transaction, created = PaymentTransaction.objects.get_or_create(
                user=user,
                plan=plan,
                checkout_reference=demo_reference,
                defaults={
                    "subscription": subscription,
                    "provider": "manual",
                    "amount": plan.price,
                    "currency": plan.currency,
                    "status": "paid",
                    "provider_transaction_id": f"demo-txn-{username}",
                    "raw_response": {"demo": True, "user": username},
                    "admin_notes": "Demo paid transaction.",
                },
            )
            counters["payments"] += int(created)
            if transaction.subscription_id != subscription.id:
                transaction.subscription = subscription
                transaction.status = "paid"
                transaction.save(update_fields=["subscription", "status", "updated_at"])

            invoice, created = Invoice.objects.get_or_create(
                transaction=transaction,
                defaults={
                    "user": user,
                    "invoice_number": f"MVCV-{username.upper()}",
                    "amount": transaction.amount,
                    "currency": transaction.currency,
                    "status": "paid",
                    "paid_at": timezone.now() - timedelta(days=index),
                    "receipt_email": email,
                    "receipt_email_status": "sent",
                    "receipt_sent_at": timezone.now() - timedelta(days=index),
                    "next_payment_date": subscription.current_period_end,
                },
            )
            counters["invoices"] += int(created)
            if invoice.user_id != user.id:
                invoice.user = user
                invoice.save(update_fields=["user"])

            if index <= 5:
                _refund, created = Refund.objects.get_or_create(
                    transaction=transaction,
                    reason="Demo refund request for admin testing.",
                    defaults={
                        "amount": min(transaction.amount, Decimal("2.00")),
                        "status": ["requested", "approved", "processed", "rejected", "requested"][index - 1],
                        "admin_notes": "Demo refund workflow record.",
                    },
                )
                counters["refunds"] += int(created)

            _webhook, created = PaymentWebhookLog.objects.get_or_create(
                checkout_reference=demo_reference,
                provider="manual",
                event_type="demo.payment.created",
                defaults={"payload": {"demo": True, "index": index}, "is_processed": True},
            )
            counters["webhooks"] += int(created)

            if plan_code == "enterprise":
                batch, created = EnterpriseBatch.objects.get_or_create(
                    user=user,
                    job_role=job_role,
                    title=f"{first_name} Enterprise Candidate Report",
                    defaults={"notes": "Demo enterprise shortlist generated from sample CVs."},
                )
                counters["enterprise_batches"] += int(created)
                for rank in range(1, 4):
                    candidate_name = f"{first_name} Candidate {rank}"
                    candidate, created = EnterpriseCandidateResult.objects.get_or_create(
                        batch=batch,
                        candidate_name=candidate_name,
                        defaults={
                            "score": max(30, score - (rank - 1) * 11),
                            "matched_skills": ", ".join(matched),
                            "missing_skills": ", ".join(missing),
                            "recommendation": "Shortlist for interview." if rank == 1 else "Review as backup candidate.",
                            "rank": rank,
                        },
                    )
                    if created:
                        candidate.cv_file.save(
                            f"{candidate_name.lower().replace(' ', '_')}.txt",
                            ContentFile(self.build_cv_text(candidate_name, "Demo", email, job_title)),
                            save=True,
                        )
                        counters["enterprise_candidates"] += 1

        self.stdout.write(self.style.SUCCESS("Demo seed complete for PostgreSQL/Django verification."))
        if options["per_plan"]:
            self.stdout.write(f"Requested demo users per plan: {options['per_plan']}")
        self.stdout.write(f"Demo user password: {password}")
        for key, value in counters.items():
            self.stdout.write(f"{key}: {value}")

    def build_role_data(self, per_plan):
        first_names = [
            "Aisha", "Ben", "Chloe", "Daniel", "Emma", "Faisal", "Grace", "Hannah", "Isaac", "Julia",
            "Kareem", "Lina", "Marcus", "Nora", "Omar", "Priya", "Quinn", "Rania", "Sam", "Tara",
        ]
        last_names = [
            "Morgan", "Carter", "Patel", "Evans", "Wright", "Khan", "Taylor", "Brown", "Wilson", "Green",
            "Saleh", "Haddad", "Reed", "Ali", "Nasser", "Shah", "Miller", "Yousef", "Brooks", "Stone",
        ]
        job_titles = {
            "free": [
                "Office Administrator", "Customer Service Advisor", "Teaching Assistant", "Marketing Assistant",
                "Junior Data Analyst", "Receptionist", "Sales Assistant", "Finance Assistant",
            ],
            "plus": [
                "Django Developer", "Project Manager", "Business Analyst", "QA Tester",
                "Product Manager", "HR Coordinator", "Digital Marketing Specialist", "Backend API Engineer",
            ],
            "enterprise": [
                "Recruitment Lead", "Operations Manager", "Data Engineering Lead", "IT Support Manager",
                "Cloud Support Engineer", "Database Administrator", "Compliance Manager", "Product Coordinator",
            ],
        }
        base_scores = {"free": 58, "plus": 74, "enterprise": 81}
        rows = []
        for plan_code in ("free", "plus", "enterprise"):
            for number in range(1, per_plan + 1):
                name_index = (number - 1) % len(first_names)
                first_name = first_names[name_index]
                last_name = last_names[(number + len(plan_code)) % len(last_names)]
                username = f"demo_{plan_code}_{number:02d}"
                email = f"{username}@example.com"
                title_pool = job_titles[plan_code]
                job_title = title_pool[(number - 1) % len(title_pool)]
                score = min(96, base_scores[plan_code] + ((number * 7) % 19))
                rows.append((username, first_name, last_name, email, job_title, score, plan_code))
        return rows

    def ensure_core_reference_data(self):
        plans = [
            ("free", "Free", Decimal("0.00"), 1, 5, 0),
            ("plus", "Plus", Decimal("4.99"), 1, 20, 0),
            ("enterprise", "Enterprise", Decimal("49.00"), 50, 50, 50),
        ]
        for order, (code, name, price, cv_limit, daily_limit, bulk_limit) in enumerate(plans, start=1):
            SubscriptionPlan.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": f"Demo {name} plan.",
                    "price": price,
                    "currency": "GBP",
                    "billing_interval": "month",
                    "cv_limit": cv_limit,
                    "monthly_analysis_limit": daily_limit,
                    "monthly_bulk_cv_limit": bulk_limit,
                    "includes_generated_cv": code == "plus",
                    "includes_job_url": code != "free",
                    "includes_deadline_alerts": code != "free",
                    "includes_enterprise_reports": code == "enterprise",
                    "is_active": True,
                    "sort_order": order,
                },
            )
        DiscountCode.objects.get_or_create(
            code="FOUNDER25",
            defaults={"description": "Founding customer launch discount", "percent_off": 25, "currency": "GBP"},
        )
        SocialAuthProvider.objects.update_or_create(
            key="google",
            defaults={"name": "Google", "icon_label": "G", "is_active": True, "sort_order": 10},
        )
        SocialAuthProvider.objects.update_or_create(
            key="linkedin",
            defaults={"name": "LinkedIn", "icon_label": "in", "is_active": True, "sort_order": 20},
        )
        SocialAuthProvider.objects.update_or_create(
            key="facebook",
            defaults={"name": "Facebook", "icon_label": "f", "is_active": False, "sort_order": 30},
        )

    def build_cv_text(self, first_name, last_name, email, job_title):
        return f"""{first_name} {last_name}
{email}
+44 7700 900123
linkedin.com/in/{str(first_name).lower()}-{str(last_name).lower()}

Professional Summary
Experienced candidate targeting {job_title} roles with strong communication, teamwork, and delivery focus.

Experience
Worked on projects using Python, Django, SQL, Git, HTML, CSS, JavaScript, and customer-facing communication.
Delivered measurable improvements, collaborated with stakeholders, and documented project outcomes.

Skills
Python, Django, SQL, Git, HTML, CSS, JavaScript, Bootstrap, API, communication, leadership, project management.

Education
Bachelor degree or equivalent professional experience.
"""

    def build_job_description(self, job_title):
        return f"""{job_title}

We are looking for a candidate with experience in Python, Django, SQL, Git, API delivery, communication,
project management, and stakeholder collaboration. The role requires clear documentation, problem solving,
and the ability to improve systems while working with a wider team.
"""

    def build_generated_cv(self, cv_title, job_title, score):
        if score >= 75:
            decision = "It is worth applying for this job role because the CV is above the strong shortlist signal used by MyValidCV."
        elif score >= 55:
            decision = "It may be worth applying after improving the CV because the role-fit score is above the minimum review line but below the stronger shortlist signal."
        else:
            decision = "Do not apply yet. The CV does not meet the minimum role-fit standard for this job, so a cosmetic rewrite is not enough."
        return f"""Tailored CV Draft for {job_title}

Source CV: {cv_title}
ATS Match Score: {score}%

Application Decision
{decision}

Change Legend
[GREEN] Rewording only: same evidence, clearer ATS/recruiter wording.
[YELLOW] Window-dressed wording: stronger presentation of existing evidence; do not invent facts.
[RED] Evidence gap: CV owner must be ready with training, licence, certification, or truthful proof before claiming it.

Professional Summary
[GREEN] Candidate profile tailored toward {job_title}, emphasising the strongest matched evidence and measurable delivery outcomes where truthful.

Recommended Changes
1. [GREEN] Add role keywords near the top of the CV when they are already supported by evidence.
2. [YELLOW] Reframe existing duties into measurable achievements.
3. [RED] Add missing skills only when the candidate genuinely has training, licence, certification, or experience.
"""

    def build_cover_letter(self, first_name, last_name, job_title, matched, score):
        strengths = ", ".join(matched[:4]) if matched else "the evidence shown in my CV"
        return f"""Dear Hiring Manager,

I am applying for the {job_title} role. The strongest evidence in my CV aligns with {strengths}, and I have kept the application focused on experience I can discuss confidently at interview.

My background shows relevant delivery, communication, and role-specific capability for the requirements described in the advert. I would welcome the opportunity to discuss how this experience can support your team.

Yours sincerely,
{first_name} {last_name}

Draft note: personalise the greeting, company name, and any figures before sending.
"""
