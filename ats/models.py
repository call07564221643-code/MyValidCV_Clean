import uuid

from django.db import models
from django.contrib.auth.models import User


class CVStorage(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="cv_storage")
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    storage_limit = models.PositiveBigIntegerField(default=10 * 1024 * 1024)
    used_storage = models.PositiveBigIntegerField(default=0)
    auto_delete_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CV Storage"
        verbose_name_plural = "CV Storage"

    def __str__(self):
        return f"{self.user} CV storage"

    def refresh_used_storage(self):
        total = self.uploads.aggregate(total=models.Sum("file_size"))["total"] or 0
        self.used_storage = total
        self.save(update_fields=["used_storage", "updated_at"])
        return total


class JobRole(models.Model):
    SOURCE_CHOICES = [
        ("text", "Text"),
        ("url", "URL"),
        ("file", "File"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="job_roles")
    title = models.CharField(max_length=150)
    company = models.CharField(max_length=150, blank=True)
    description = models.TextField()
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="text")
    source_url = models.URLField(blank=True)
    source_file = models.FileField(upload_to="job_roles/", blank=True)
    deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.company:
            return f"{self.title} at {self.company}"
        return self.title


class CV(models.Model):
    VALIDATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("valid", "Valid CV"),
        ("rejected", "Rejected"),
    ]

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cvs")
    storage = models.ForeignKey(CVStorage, on_delete=models.SET_NULL, null=True, blank=True, related_name="uploads")
    title = models.CharField(max_length=150)
    file = models.FileField(upload_to="cvs/")
    original_filename = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=120, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    file_data = models.BinaryField(null=True, blank=True, editable=False)
    validation_status = models.CharField(max_length=20, choices=VALIDATION_STATUS_CHOICES, default="valid")
    is_valid_cv = models.BooleanField(default=True)
    validation_notes = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class ATSResult(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ats_results")
    cv = models.ForeignKey(CV, on_delete=models.CASCADE, related_name="results")
    job_role = models.ForeignKey(JobRole, on_delete=models.SET_NULL, null=True, blank=True, related_name="results")
    job_title = models.CharField(max_length=150)
    job_description = models.TextField()
    score = models.IntegerField(default=0)
    matched_skills = models.TextField(blank=True)
    missing_skills = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completed")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.cv.title} - {self.job_title} - {self.score}%"


class GeneratedCV(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="generated_cvs")
    original_cv = models.ForeignKey(CV, on_delete=models.CASCADE, related_name="generated_versions")
    ats_result = models.OneToOneField(ATSResult, on_delete=models.CASCADE, related_name="generated_cv")
    title = models.CharField(max_length=180)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ApplicationReminder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="application_reminders")
    job_role = models.ForeignKey(JobRole, on_delete=models.CASCADE, related_name="reminders")
    reminder_date = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["reminder_date", "-created_at"]

    def __str__(self):
        return f"{self.job_role} reminder on {self.reminder_date}"


class EnterpriseBatch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enterprise_batches")
    job_role = models.ForeignKey(JobRole, on_delete=models.CASCADE, related_name="enterprise_batches")
    title = models.CharField(max_length=180)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class EnterpriseCandidateResult(models.Model):
    batch = models.ForeignKey(EnterpriseBatch, on_delete=models.CASCADE, related_name="candidate_results")
    candidate_name = models.CharField(max_length=180)
    cv_file = models.FileField(upload_to="enterprise_cvs/")
    score = models.IntegerField(default=0)
    matched_skills = models.TextField(blank=True)
    missing_skills = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    rank = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["rank", "-score", "candidate_name"]

    def __str__(self):
        return f"{self.candidate_name} - {self.score}%"
