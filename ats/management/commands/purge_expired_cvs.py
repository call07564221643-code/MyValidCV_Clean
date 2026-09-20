from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ats.models import CV, CVStorage, DataDeletionAudit, EnterpriseCandidateResult


class Command(BaseCommand):
    """Enforce retention in both individual and Enterprise CV tables/files.

    Defining this command does not schedule it. Production must invoke it using
    Heroku Scheduler or another recurring worker at least daily/monthly.
    """
    help = "Purge expired raw CV sources while preserving compact validation reports."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report expired CVs without deleting them.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Maximum individual and enterprise source records to purge per run.",
        )

    def handle(self, *args, **options):
        retention_days = getattr(settings, "CV_RETENTION_DAYS", 30)
        if retention_days < 1:
            raise CommandError("CV_RETENTION_DAYS must be at least 1.")
        batch_size = options["batch_size"]
        if batch_size < 1 or batch_size > 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")

        cutoff = timezone.now() - timedelta(days=retention_days)
        cvs = CV.objects.filter(uploaded_at__lt=cutoff, source_purged_at__isnull=True).order_by("pk")
        candidates = EnterpriseCandidateResult.objects.filter(
            created_at__lt=cutoff,
            source_purged_at__isnull=True,
        ).order_by("pk")
        cv_count = cvs.count()
        candidate_count = candidates.count()

        if options["dry_run"]:
            self.stdout.write(
                f"Would purge raw sources for {cv_count} individual CV(s) and "
                f"{candidate_count} enterprise candidate CV(s) uploaded before {cutoff.isoformat()}; "
                "validation reports would be preserved."
            )
            return

        deleted_files = 0
        database_copies = 0
        failed = 0
        affected_storage_ids = set()
        policy = f"source-retention-{retention_days}-days"

        for cv in cvs[:batch_size]:
            bytes_released = cv.file_size + (len(cv.file_data) if cv.file_data else 0)
            had_file = bool(cv.file)
            had_database_copy = bool(cv.file_data)
            try:
                if cv.file:
                    cv.file.delete(save=False)
                    deleted_files += 1
                cv.file = ""
                cv.file_data = None
                cv.file_size = 0
                cv.source_purged_at = timezone.now()
                cv.save(update_fields=["file", "file_data", "file_size", "source_purged_at", "updated_at"])
                if cv.storage_id:
                    affected_storage_ids.add(cv.storage_id)
                database_copies += int(had_database_copy)
                DataDeletionAudit.objects.create(
                    record_type="individual_cv",
                    record_id=str(cv.public_id),
                    policy=policy,
                    bytes_released=bytes_released,
                    file_deleted=had_file,
                    database_copy_deleted=had_database_copy,
                )
            except Exception as exc:
                failed += 1
                DataDeletionAudit.objects.create(
                    record_type="individual_cv",
                    record_id=str(cv.public_id),
                    policy=policy,
                    status="failed",
                    error_code=type(exc).__name__[:80],
                )

        for candidate in candidates[:batch_size]:
            had_file = bool(candidate.cv_file)
            try:
                if candidate.cv_file:
                    candidate.cv_file.delete(save=False)
                    deleted_files += 1
                candidate.cv_file = ""
                candidate.source_purged_at = timezone.now()
                candidate.save(update_fields=["cv_file", "source_purged_at"])
                DataDeletionAudit.objects.create(
                    record_type="enterprise_candidate",
                    record_id=str(candidate.pk),
                    policy=policy,
                    file_deleted=had_file,
                )
            except Exception as exc:
                failed += 1
                DataDeletionAudit.objects.create(
                    record_type="enterprise_candidate",
                    record_id=str(candidate.pk),
                    policy=policy,
                    status="failed",
                    error_code=type(exc).__name__[:80],
                )

        for storage in CVStorage.objects.filter(pk__in=affected_storage_ids):
            storage.refresh_used_storage()

        self.stdout.write(
            self.style.SUCCESS(
                f"Preserved reports and purged {deleted_files} stored file(s) plus "
                f"{database_copies} database copy/copies; {failed} failure(s)."
            )
        )
