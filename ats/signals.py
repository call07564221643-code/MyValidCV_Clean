"""Delete storage-backend files whenever their owning database row is deleted."""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import CV, EnterpriseCandidateResult, JobRole


def _delete_field_file(field_file):
    if field_file and field_file.name:
        field_file.delete(save=False)


@receiver(post_delete, sender=CV)
def delete_cv_file(sender, instance, **kwargs):
    _delete_field_file(instance.file)


@receiver(post_delete, sender=EnterpriseCandidateResult)
def delete_enterprise_cv_file(sender, instance, **kwargs):
    _delete_field_file(instance.cv_file)


@receiver(post_delete, sender=JobRole)
def delete_job_source_file(sender, instance, **kwargs):
    _delete_field_file(instance.source_file)
