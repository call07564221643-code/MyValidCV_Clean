from django.core.management.base import BaseCommand

from analytics.services.alerts import evaluate_storage_pressure


class Command(BaseCommand):
    help = "Evaluate platform thresholds and optionally send new owner alerts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--send",
            action="store_true",
            help="Deliver newly-created alerts through enabled, configured channels.",
        )

    def handle(self, *args, **options):
        alert = evaluate_storage_pressure(send_notifications=options["send"])
        if alert:
            self.stdout.write(self.style.WARNING(
                f"{alert.severity.upper()}: {alert.title} ({alert.metric_value}%, occurrence {alert.occurrence_count})"
            ))
        else:
            self.stdout.write(self.style.SUCCESS("Platform capacity thresholds are healthy."))
