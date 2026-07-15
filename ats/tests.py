from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from .forms import ATSAnalysisForm, MultipleFileField
from .views import _validate_public_job_url


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
