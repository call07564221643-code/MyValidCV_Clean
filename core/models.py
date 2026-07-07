from django.db import models
from django.contrib.auth.models import User


class Analysis(models.Model):
    """Store analysis summaries (not CV/JD data - temp only)."""
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    overall_score = models.IntegerField()
    ats_score = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Analysis {self.id} - Score: {self.overall_score}"
