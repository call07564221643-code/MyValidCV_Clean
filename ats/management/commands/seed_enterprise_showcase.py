"""Create a coherent, fictional Enterprise product showcase for local QA."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

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


CV_TEXT = """Jordan Morgan
jordan.morgan@example.test | +44 7700 900555

PROFILE
Senior talent acquisition specialist with eight years of experience delivering
high-volume recruitment, stakeholder management and evidence-led process improvement.

SKILLS
Recruitment, onboarding, workforce planning, Excel, SQL, data analysis,
project management, compliance, stakeholder communication and reporting.

EXPERIENCE
Talent Acquisition Lead, Example Services, 2021-present
Led a team of four recruiters and delivered campaigns across five departments.
Reduced time-to-shortlist by 32 percent through structured screening and reporting.
Built Excel and SQL dashboards, trained hiring managers and improved audit records.

Senior Recruitment Coordinator, Sample Group, 2018-2021
Managed candidate pipelines, interview scheduling, onboarding and compliance checks.
Delivered weekly hiring reports and improved candidate communications.

EDUCATION
BA Business Management. CIPD recruitment practice certificate.
"""


class Command(BaseCommand):
    help = "Populate a local writable Enterprise QA account with synthetic showcase data."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="enterprise_qa")

    def handle(self, *args, **options):
        username = options["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"Create the {username} Enterprise QA account first.") from exc
        if getattr(user.profile, "plan", "") != "enterprise":
            raise CommandError(f"{username} is not an Enterprise account.")

        storage, _created = CVStorage.objects.get_or_create(user=user)
        cv, _created = CV.objects.get_or_create(
            user=user,
            title="QA Senior Talent Acquisition CV",
            defaults={
                "storage": storage,
                "original_filename": "qa-senior-talent-acquisition.txt",
                "mime_type": "text/plain",
                "file_size": len(CV_TEXT.encode("utf-8")),
                "file_data": CV_TEXT.encode("utf-8"),
                "validation_status": "valid",
                "is_valid_cv": True,
                "validation_notes": "Synthetic QA document; passed structural and evidence validation.",
            },
        )
        if not cv.file:
            cv.file.save("qa-senior-talent-acquisition.txt", ContentFile(CV_TEXT.encode("utf-8")), save=False)
        cv.storage = storage
        cv.original_filename = "qa-senior-talent-acquisition.txt"
        cv.mime_type = "text/plain"
        cv.file_size = len(CV_TEXT.encode("utf-8"))
        cv.file_data = CV_TEXT.encode("utf-8")
        cv.validation_status = "valid"
        cv.is_valid_cv = True
        cv.validation_notes = "Synthetic QA document; passed structural and evidence validation."
        cv.source_purged_at = None
        cv.save()
        storage.refresh_used_storage()

        job_description = (
            "Senior Talent Acquisition Manager. Responsibilities include leading high-volume recruitment, "
            "workforce planning, hiring-manager engagement, onboarding governance and recruitment analytics. "
            "Required experience includes stakeholder management, Excel reporting, compliance and leading a "
            "recruitment team. SQL dashboard experience is preferred."
        )
        role, _created = JobRole.objects.update_or_create(
            user=user,
            title="Senior Talent Acquisition Manager",
            company="Northstar Services (QA)",
            defaults={
                "description": job_description,
                "source_type": "text",
                "deadline": timezone.localdate() + timedelta(days=21),
            },
        )
        metrics = {
            "taxonomy": {
                "detected_role": "Talent Acquisition Manager",
                "detected_family": "Human Resources",
                "mandatory_terms": ["recruitment leadership", "stakeholder management", "compliance"],
            },
            "score_components": {
                "skills": 92,
                "requirements": 86,
                "title": 80,
                "keywords": 84,
                "mandatory": 100,
                "evidence": 88,
                "format": 95,
            },
            "requirement_groups": {
                "required": ["recruitment", "stakeholder management", "compliance", "leadership"],
                "preferred": ["sql", "workforce planning"],
            },
            "evidence_map": [
                {"term": "leadership", "status": "verified", "evidence": "Led a team of four recruiters."},
                {"term": "process improvement", "status": "verified", "evidence": "Reduced time-to-shortlist by 32 percent."},
                {"term": "sql", "status": "verified", "evidence": "Built Excel and SQL dashboards."},
                {"term": "workforce planning", "status": "mentioned", "evidence": "Listed in skills."},
            ],
            "format_checks": {"contact": True, "sections": True, "experience": True, "education": True},
            "experience_alignment": {
                "label": "Strong alignment",
                "summary": "Leadership, measurable recruitment delivery and analytics evidence align with the role.",
            },
            "confidence": {
                "score": 91,
                "label": "High",
                "reasons": ["Complete job advert", "Readable CV", "Multiple evidence-backed requirements"],
            },
            "model_version": "2.3",
            "qa_showcase": True,
            "decision_notice": "Document alignment only; final recruitment decisions require human review.",
        }
        result, _created = ATSResult.objects.update_or_create(
            user=user,
            cv=cv,
            job_role=role,
            job_title=role.title,
            defaults={
                "job_description": job_description,
                "score": 87,
                "matched_skills": "recruitment, stakeholder management, leadership, compliance, excel, sql",
                "missing_skills": "advanced workforce forecasting",
                "recommendation": "Strong role fit. Keep quantified leadership and recruitment-delivery evidence prominent.",
                "metrics": metrics,
                "status": "completed",
            },
        )
        GeneratedCV.objects.update_or_create(
            user=user,
            original_cv=cv,
            ats_result=result,
            defaults={
                "title": "QA tailored CV – Senior Talent Acquisition Manager",
                "content": CV_TEXT + "\nTARGET ROLE\nSenior Talent Acquisition Manager\n",
            },
        )
        GeneratedCoverLetter.objects.update_or_create(
            user=user,
            ats_result=result,
            defaults={
                "title": "QA cover letter – Senior Talent Acquisition Manager",
                "content": (
                    "Dear Hiring Manager,\n\nThis synthetic QA letter demonstrates the generated-document workflow. "
                    "My recruitment leadership, stakeholder engagement and measurable process-improvement evidence "
                    "align with the advertised role.\n\nKind regards,\nJordan Morgan"
                ),
            },
        )
        ApplicationReminder.objects.update_or_create(
            user=user,
            job_role=role,
            defaults={
                "reminder_date": role.deadline - timedelta(days=2),
                "note": "QA reminder: review the application evidence before the deadline.",
                "is_sent": False,
            },
        )

        batch, _created = EnterpriseBatch.objects.update_or_create(
            user=user,
            job_role=role,
            title="QA Recruitment Operations Shortlist",
            defaults={
                "notes": "Synthetic showcase: evidence-led scoring with mandatory gates and human review.",
                "mandatory_requirements": "Recruitment team leadership\nStakeholder management\nRight to work evidence",
                "email_sending_authorized": False,
                "sender_email": "support@myvalidcv.com",
            },
        )
        candidates = [
            ("Alex Morgan", 91, True, "shortlisted", ["team leadership", "stakeholder management", "right to work"], []),
            ("Samira Khan", 84, True, "shortlisted", ["team leadership", "stakeholder management", "right to work"], []),
            ("Daniel Reed", 76, True, "pending", ["team leadership", "stakeholder management", "right to work"], []),
            ("Priya Shah", 69, True, "pending", ["stakeholder management", "right to work"], []),
            ("Omar Nasser", 63, False, "mandatory_failed", ["stakeholder management", "right to work"], ["recruitment team leadership"]),
            ("Julia Green", 48, False, "criteria_failed", ["right to work"], ["recruitment team leadership", "stakeholder management"]),
        ]
        for rank, (name, score, mandatory_pass, review_status, mandatory_matched, mandatory_missing) in enumerate(candidates, start=1):
            candidate, _created = EnterpriseCandidateResult.objects.update_or_create(
                batch=batch,
                candidate_name=name,
                defaults={
                    "score": score,
                    "matched_skills": "recruitment, communication, compliance",
                    "missing_skills": "workforce forecasting" if score >= 69 else "leadership, workforce forecasting",
                    "recommendation": "Human review required; validate evidence against the original application.",
                    "rank": rank,
                    "candidate_email": f"qa.candidate{rank}@example.test",
                    "mandatory_matched": mandatory_matched,
                    "mandatory_missing": mandatory_missing,
                    "mandatory_pass": mandatory_pass,
                    "review_status": review_status,
                    "reviewed_at": timezone.now() if review_status != "pending" else None,
                    "email_subject": "Your application update – QA demonstration" if review_status != "pending" else "",
                    "email_body": "Synthetic QA email draft. Review is required before any send action." if review_status != "pending" else "",
                    "source_purged_at": None,
                },
            )
            source = (CV_TEXT + f"\nQA CANDIDATE\n{name}\n").encode("utf-8")
            if not candidate.cv_file:
                candidate.cv_file.save(f"qa-candidate-{rank}.txt", ContentFile(source), save=True)

        self.stdout.write(self.style.SUCCESS(
            f"Enterprise showcase ready for {username}: 1 CV, 1 ATS result, 1 batch, {len(candidates)} candidates."
        ))
