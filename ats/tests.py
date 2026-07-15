from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from .forms import ATSAnalysisForm, MultipleFileField
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
