from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ats.models import CV, EnterpriseCandidateResult


class Command(BaseCommand):
    help = "Delete CV records and files older than the configured retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report expired CVs without deleting them.",
        )

    def handle(self, *args, **options):
        retention_days = getattr(settings, "CV_RETENTION_DAYS", 30)
        if retention_days < 1:
            raise CommandError("CV_RETENTION_DAYS must be at least 1.")

        cutoff = timezone.now() - timedelta(days=retention_days)
        cvs = CV.objects.filter(uploaded_at__lt=cutoff).order_by("pk")
        candidates = EnterpriseCandidateResult.objects.filter(created_at__lt=cutoff).order_by("pk")
        cv_count = cvs.count()
        candidate_count = candidates.count()

        if options["dry_run"]:
            self.stdout.write(
                f"Would delete {cv_count} individual CV(s) and "
                f"{candidate_count} enterprise candidate CV(s) uploaded before {cutoff.isoformat()}."
            )
            return

        deleted_files = 0
        with transaction.atomic():
            for cv in cvs.iterator(chunk_size=100):
                if cv.file:
                    cv.file.delete(save=False)
                    deleted_files += 1
                cv.delete()

            for candidate in candidates.iterator(chunk_size=100):
                if candidate.cv_file:
                    candidate.cv_file.delete(save=False)
                    deleted_files += 1
                candidate.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {cv_count} individual CV(s), {candidate_count} enterprise candidate CV(s), "
                f"and {deleted_files} stored file(s)."
            )
        )
