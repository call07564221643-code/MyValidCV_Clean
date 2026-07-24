from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .forms import ATSAnalysisForm, MultipleFileField, validate_document
from .models import ATSResult, CV
from .scoring import (
    _detect_mandatory_qualifications,
    calculate_score_details,
    validate_job_description,
)
from .views import (
    _validate_public_job_url,
    build_cover_letter,
    build_interview_plan,
    build_truth_gate_summary,
    calculate_score,
    humanize_requirement_term,
)


class UploadAndUrlSecurityTests(SimpleTestCase):
    def test_private_job_url_is_rejected(self):
        with self.assertRaises(ValueError):
            _validate_public_job_url("http://127.0.0.1/internal")

    def test_non_http_job_url_is_rejected(self):
        with self.assertRaises(ValueError):
            _validate_public_job_url("file:///etc/passwd")

    def test_nonstandard_job_url_port_is_rejected(self):
        with self.assertRaises(ValueError):
            _validate_public_job_url("https://example.com:8443/jobs/1")

    def test_executable_disguised_upload_extension_is_rejected(self):
        field = MultipleFileField()
        upload = SimpleUploadedFile("candidate.exe", b"not a cv")
        with self.assertRaisesMessage(Exception, "PDF, DOCX or TXT"):
            field.clean([upload])

    def test_more_than_fifty_files_is_rejected_before_processing(self):
        field = MultipleFileField()
        uploads = [SimpleUploadedFile(f"cv-{index}.txt", b"cv") for index in range(51)]
        with self.assertRaisesMessage(Exception, "no more than 50"):
            field.clean(uploads)

    def test_pdf_extension_with_binary_content_is_rejected(self):
        upload = SimpleUploadedFile("candidate.pdf", b"MZ executable content")
        with self.assertRaisesMessage(Exception, "valid PDF signature"):
            validate_document(upload)

    def test_binary_txt_file_is_rejected(self):
        upload = SimpleUploadedFile("candidate.txt", b"text\x00binary")
        with self.assertRaisesMessage(Exception, "binary data"):
            validate_document(upload)


class CoverLetterTests(SimpleTestCase):
    def test_letter_addresses_recipient_and_keeps_drafting_note_outside_content(self):
        user = SimpleNamespace(
            username="alex",
            get_full_name=lambda: "Alex Morgan",
        )
        result = SimpleNamespace(
            job_title="Operations Manager",
            job_role=SimpleNamespace(company="Northstar Logistics"),
        )

        letter = build_cover_letter(
            user,
            result,
            ["leadership", "operations"],
            "Led daily operations and improved delivery performance by 15%.",
        )

        self.assertTrue(letter.startswith("Dear Hiring Manager,"))
        self.assertIn("Yours sincerely,\nAlex Morgan", letter)
        self.assertNotIn("Dear Mr Alex", letter)
        self.assertNotIn("Draft note:", letter)


class ATSV2Tests(TestCase):
    def test_short_or_placeholder_job_advert_is_rejected(self):
        valid, reason = validate_job_description("Job advert URL: https://example.com/job")
        self.assertFalse(valid)
        self.assertIn("too short", reason)

    def test_job_advert_requires_meaningful_role_signals(self):
        valid, reason = validate_job_description("This is general website text. " * 20)
        self.assertFalse(valid)
        self.assertIn("complete job advert", reason)

    def test_complete_job_advert_is_accepted(self):
        advert = (
            "Software Developer role. Responsibilities include building and testing web services. "
            "Required skills include Python, Django, SQL, Git, communication and API development. "
            "Candidates must have relevant software experience and knowledge of secure deployment."
        )
        valid, reason = validate_job_description(advert)
        self.assertTrue(valid, reason)

    def test_keyword_only_match_is_not_treated_as_verified_evidence(self):
        details = calculate_score_details(
            "Profile\nSkills: Python, Django, SQL.\nExperience\nGeneral office support.\n"
            "Education\nDiploma\nalex@example.com\n" + ("Additional profile text. " * 25),
            "Developer role. Required skills include Python, Django and SQL. "
            "Responsibilities include building, testing and deploying secure web APIs. " * 3,
            "Django Developer",
        )
        django_evidence = next(item for item in details["evidence_map"] if item["term"] == "django")
        self.assertEqual(django_evidence["status"], "mentioned")
        self.assertEqual(django_evidence["strength"], "keyword only")
        self.assertEqual(details["model_version"], "2.0")
        self.assertIn("evidence", details["score_components"])
        self.assertIn("format", details["score_components"])

    def test_negated_or_preferred_qualification_is_not_mandatory(self):
        qualification = SimpleNamespace(
            normalized_name="forklift licence",
            is_license=True,
            terms=lambda: ["forklift licence"],
        )
        self.assertEqual(
            _detect_mandatory_qualifications(
                "A forklift licence is preferred but not required.",
                [qualification],
            ),
            [],
        )

    def test_candidate_can_record_truth_gate_confirmation(self):
        user = User.objects.create_user("candidate", "candidate@example.com", "password")
        cv = CV.objects.create(user=user, title="Candidate CV", file="cvs/candidate.txt")
        result = ATSResult.objects.create(
            user=user,
            cv=cv,
            job_title="Developer",
            job_description=(
                "Developer role with responsibilities for web services. Required skills include "
                "Python, Django, SQL and testing. Candidates must have software experience. " * 2
            ),
            metrics={
                "model_version": "2.0",
                "score_components": {},
                "evidence_map": [{"term": "django", "status": "mentioned"}],
                "requirement_groups": {},
                "confidence": {},
            },
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("ats_result", args=[result.id]),
            {
                "requirement": "django",
                "evidence_action": "confirmed",
                "truth_gate_item": "1",
            },
        )

        expected_url = f"{reverse('ats_result', args=[result.id])}#truth-gate-item-1"
        self.assertRedirects(response, expected_url)
        result.refresh_from_db()
        self.assertEqual(result.metrics["candidate_confirmations"]["django"], "confirmed")
        rendered = self.client.get(reverse("ats_result", args=[result.id]))
        self.assertEqual(rendered.status_code, 200)
        self.assertContains(rendered, "Evidence decision studio")
        self.assertContains(rendered, 'id="truth-gate"')
        self.assertContains(rendered, 'class="truth-gate-scroll"')
        self.assertContains(rendered, "selected-confirmed")
        self.assertContains(rendered, "I have this experience")
        self.assertContains(rendered, "Interview Studio: Developer")
        self.assertContains(rendered, "Your next action")
        self.assertContains(rendered, "--truth-card-bg:")
        self.assertContains(rendered, "--truth-selected-bg:")
        self.assertContains(rendered, ".truth-status.verified { background: #1e8e3e; color: #fff; }")
        self.assertContains(rendered, 'aria-label="Your report journey"')
        self.assertContains(rendered, "requirement-title")


class TruthGateGuidanceTests(SimpleTestCase):
    def test_requirement_labels_are_human_readable(self):
        self.assertEqual(humanize_requirement_term("skillsproficiency"), "Skills proficiency")
        self.assertEqual(humanize_requirement_term("project_management"), "Project management")

    def test_completion_summary_reflects_candidate_actions(self):
        summary = build_truth_gate_summary([
            {"term": "python", "candidate_action": "confirmed"},
            {"term": "testing", "candidate_action": "training"},
            {"term": "aws", "candidate_action": "not_have"},
        ])

        self.assertTrue(summary["complete"])
        self.assertEqual(summary["completion"], 100)
        self.assertEqual(summary["confirmed"], 1)
        self.assertEqual(summary["training"], 1)
        self.assertEqual(summary["not_have"], 1)
        self.assertIn("unsupported requirements", summary["next_action"])

    def test_interview_plan_uses_role_and_truth_gate_evidence(self):
        plan = build_interview_plan(
            [{"term": "safeguarding", "status": "mentioned", "candidate_action": "training"}],
            "Care Assistant",
        )

        self.assertEqual(plan["role"], "Care Assistant")
        self.assertIn("Care Assistant", plan["standard"][0]["prompt"])
        self.assertIn("currently learning about Safeguarding", plan["tailored"][0]["prompt"])


class ATSScoringTests(TestCase):
    def test_admin_cv_is_capped_for_dentist_role(self):
        cv_text = """
        Office Administrator
        Profile: organised administrator with five years of experience.
        Skills: administration, scheduling, records management, data entry,
        customer service, Excel, document control and compliance.
        Experience: managed appointments, supported customers, coordinated
        reports, improved filing accuracy by 20%, and trained two new staff.
        Education: business administration diploma.
        """
        dentist_job = """
        Dentist required for a busy dental clinic. Responsibilities include
        clinical assessment, oral health diagnosis, treatment planning,
        restorative dentistry, patient care, infection control, radiography,
        x-ray review and compliance with GDC standards.
        """

        score, matched, missing, recommendation = calculate_score(cv_text, dentist_job, "Dentist")

        self.assertLess(score, 50)
        self.assertIn("dentist", missing)
        self.assertIn("dental", missing)
        self.assertIn("High role mismatch", recommendation)


    def test_admin_cv_gets_partial_fit_for_airport_admin_role(self):
        cv_text = """
        Office Administrator
        Profile: organised administrator with five years of experience.
        Skills: administration, scheduling, records management, data entry,
        customer service, Excel, document control and compliance.
        Experience: managed appointments, supported customers, coordinated
        reports, improved filing accuracy by 20%, and trained two new staff.
        Education: business administration diploma.
        """
        airport_admin_job = """
        Airport administrator required to support airport operations. The role
        includes passenger service records, scheduling, document control,
        compliance, coordination with terminal teams, flight administration,
        email correspondence and accurate data entry.
        """

        score, matched, missing, recommendation = calculate_score(cv_text, airport_admin_job, "Airport Administrator")

        self.assertGreaterEqual(score, 50)
        self.assertLess(score, 90)
        self.assertIn("administration", matched)
        self.assertIn("airport", missing)
        self.assertNotIn("High role mismatch", recommendation)

    def test_software_cv_scores_well_for_software_role(self):
        cv_text = """
        Backend Software Engineer
        Skills: Python, Django, SQL, PostgreSQL, API development, Git, testing.
        Experience: developed REST APIs, improved database performance by 30%,
        deployed services, fixed defects, and worked with product teams.
        Education: computer science degree.
        """
        software_job = """
        Senior Django Developer required. Must have Python, Django, REST API,
        PostgreSQL, SQL, Git, testing experience, database optimisation and
        ability to deploy backend services.
        """

        score, matched, missing, recommendation = calculate_score(cv_text, software_job, "Senior Django Developer")

        self.assertGreaterEqual(score, 70)
        self.assertIn("django", matched)
        self.assertNotIn("High role mismatch", recommendation)

    def test_software_cv_is_capped_for_finance_role(self):
        cv_text = """
        Backend Software Engineer
        Skills: Python, Django, SQL, PostgreSQL, API development, Git, testing.
        Experience: developed REST APIs, improved database performance by 30%,
        deployed services, fixed defects, and worked with product teams.
        Education: computer science degree.
        """
        accountant_job = """
        Management Accountant required. Responsibilities include month-end
        accounts, reconciliations, budgeting, forecasting, variance analysis,
        balance sheet control, VAT returns, payroll journals and financial
        reporting using accounting software.
        """

        score, matched, missing, recommendation = calculate_score(cv_text, accountant_job, "Management Accountant")

        self.assertLess(score, 50)
        self.assertIn("accountant", missing)
        self.assertIn("High role mismatch", recommendation)


@override_settings(SECURE_SSL_REDIRECT=False)
class CVManagementTests(TestCase):
    """Prove front-end CV update/delete CRUD and object ownership rules."""

    def setUp(self):
        self.owner = User.objects.create_user("cv-owner", "owner@example.com", "password")
        self.other_user = User.objects.create_user("other-user", "other@example.com", "password")
        self.cv = CV.objects.create(
            user=self.owner,
            title="Original CV",
            file="cvs/original.txt",
            original_filename="original.txt",
            file_size=100,
        )

    def test_manage_page_reads_only_the_users_cvs(self):
        CV.objects.create(user=self.other_user, title="Private CV", file="cvs/private.txt")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("upload_cv"))
        self.assertContains(response, "Original CV")
        self.assertNotContains(response, "Private CV")
        self.assertContains(response, reverse("update_cv", args=[self.cv.public_id]))
        self.assertContains(response, reverse("delete_cv", args=[self.cv.public_id]))

    def test_owner_can_update_cv_title(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("update_cv", args=[self.cv.public_id]),
            {"title": "Django Developer CV"},
        )
        self.assertRedirects(response, reverse("upload_cv"))
        self.cv.refresh_from_db()
        self.assertEqual(self.cv.title, "Django Developer CV")

    def test_user_cannot_update_another_users_cv(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("update_cv", args=[self.cv.public_id]),
            {"title": "Changed without permission"},
        )
        self.assertEqual(response.status_code, 404)
        self.cv.refresh_from_db()
        self.assertEqual(self.cv.title, "Original CV")

    def test_delete_requires_confirmation_post(self):
        self.client.force_login(self.owner)
        url = reverse("delete_cv", args=[self.cv.public_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Yes, delete CV")
        self.assertTrue(CV.objects.filter(pk=self.cv.pk).exists())

        response = self.client.post(url)
        self.assertRedirects(response, reverse("upload_cv"))
        self.assertFalse(CV.objects.filter(pk=self.cv.pk).exists())

    def test_deleting_cv_cascades_to_related_result(self):
        result = ATSResult.objects.create(
            user=self.owner,
            cv=self.cv,
            job_title="Developer",
            job_description="Python and Django developer",
        )
        self.client.force_login(self.owner)
        self.client.post(reverse("delete_cv", args=[self.cv.public_id]))
        self.assertFalse(ATSResult.objects.filter(pk=result.pk).exists())

    def test_user_cannot_delete_another_users_cv(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse("delete_cv", args=[self.cv.public_id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(CV.objects.filter(pk=self.cv.pk).exists())
