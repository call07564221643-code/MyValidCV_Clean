from django.core.management.base import BaseCommand
from django.utils import timezone

from ats.models import EnterprisePilot


class Command(BaseCommand):
    help = "Permanently delete expired Enterprise pilot data and uploaded files. Run hourly."

    def handle(self, *args, **options):
        pilots = EnterprisePilot.objects.filter(expires_at__lte=timezone.now()).prefetch_related("candidates")
        pilot_count = pilots.count()
        file_count = 0
        for pilot in pilots:
            for candidate in pilot.candidates.all():
                if candidate.cv_file:
                    candidate.cv_file.delete(save=False)
                    file_count += 1
            pilot.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {pilot_count} expired pilot(s) and {file_count} CV file(s)."))
