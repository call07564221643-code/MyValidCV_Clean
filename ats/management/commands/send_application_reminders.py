from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from ats.models import ApplicationReminder


class Command(BaseCommand):
    help = "Email due application-deadline reminders and mark successful deliveries as sent."

    def handle(self, *args, **options):
        reminders = ApplicationReminder.objects.filter(
            is_sent=False,
            reminder_date__lte=timezone.localdate(),
        ).select_related("user", "job_role")
        sent_count = 0
        for reminder in reminders:
            if not reminder.user.email:
                self.stderr.write(f"Skipped reminder {reminder.id}: user has no email address.")
                continue
            role = reminder.job_role
            deadline = role.deadline.strftime("%d %B %Y") if role.deadline else "the advertised closing date"
            delivered = send_mail(
                subject=f"Application deadline reminder: {role.title}",
                message=(
                    f"Hello {reminder.user.get_full_name() or reminder.user.username},\n\n"
                    f"Your application for {role.title}"
                    f"{' at ' + role.company if role.company else ''} is due by {deadline}.\n\n"
                    f"{reminder.note}\n\nMyValidCV"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[reminder.user.email],
                fail_silently=False,
            )
            if delivered:
                reminder.is_sent = True
                reminder.save(update_fields=["is_sent"])
                sent_count += 1
        self.stdout.write(self.style.SUCCESS(f"Sent {sent_count} application reminder(s)."))
