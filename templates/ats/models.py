from django.db import models
from django.contrib.auth.models import User


class CV(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cvs")
    title = models.CharField(max_length=150)
    file = models.FileField(upload_to="cvs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ATSResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ats_results")
    cv = models.ForeignKey(CV, on_delete=models.CASCADE, related_name="results")
    job_title = models.CharField(max_length=150)
    job_description = models.TextField()
    score = models.IntegerField(default=0)
    matched_skills = models.TextField(blank=True)
    missing_skills = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cv.title} - {self.job_title} - {self.score}%"