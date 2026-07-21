from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .forms import ATSAnalysisForm, MultipleFileField
from .models import ATSResult, CV
from .views import _validate_public_job_url, calculate_score


class UploadAndUrlSecurityTests(SimpleTestCase):
    def test_private_job_url_is_rejected(self):
        with self.assertRaises(ValueError):
            _validate_public_job_url("http://127.0.0.1/internal")

    def test_non_http_job_url_is_rejected(self):
        with self.assertRaises(ValueError):
            _validate_public_job_url("file:///etc/passwd")

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


class ATSScoringTests(SimpleTestCase):
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
