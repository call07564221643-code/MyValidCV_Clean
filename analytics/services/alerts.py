"""Privacy-safe platform alert evaluation and delivery."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from analytics.models import NotificationAttempt, OperationalAlert, PlatformOperationsSettings
from ats.models import CVStorage


SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


def _masked(destination: str) -> str:
    if not destination:
        return ""
    if "@" in destination:
        name, domain = destination.split("@", 1)
        return f"{name[:2]}***@{domain}"
    return f"***{destination[-4:]}"


def _channel_allowed(config: PlatformOperationsSettings, severity: str) -> bool:
    return SEVERITY_ORDER[severity] >= SEVERITY_ORDER[config.minimum_severity]


@transaction.atomic
def record_condition(*, fingerprint: str, category: str, severity: str, title: str, message: str,
                     metric_value=None, threshold_value=None) -> tuple[OperationalAlert, bool]:
    alert = OperationalAlert.objects.select_for_update().filter(
        fingerprint=fingerprint,
        status__in=["open", "acknowledged"],
    ).first()
    now = timezone.now()
    if alert:
        escalated = SEVERITY_ORDER[severity] > SEVERITY_ORDER[alert.severity]
        alert.occurrence_count += 1
        alert.last_seen_at = now
        alert.metric_value = metric_value
        alert.threshold_value = threshold_value
        if escalated:
            alert.severity = severity
            alert.status = "open"
        alert.save(update_fields=[
            "occurrence_count", "last_seen_at", "metric_value", "threshold_value", "severity", "status",
        ])
        return alert, escalated
    return OperationalAlert.objects.create(
        fingerprint=fingerprint,
        category=category,
        severity=severity,
        title=title,
        message=message,
        metric_value=metric_value,
        threshold_value=threshold_value,
    ), True


def resolve_condition(fingerprint: str) -> int:
    return OperationalAlert.objects.filter(
        fingerprint=fingerprint,
        status__in=["open", "acknowledged"],
    ).update(status="resolved", resolved_at=timezone.now(), last_seen_at=timezone.now())


def deliver_alert(alert: OperationalAlert, config: PlatformOperationsSettings) -> list[NotificationAttempt]:
    """Deliver enabled channels without placing sensitive data in notifications."""
    if not _channel_allowed(config, alert.severity):
        return []
    attempts = []
    subject = f"[MyValidCV {alert.severity.upper()}] {alert.title}"
    body = f"{alert.message}\n\nOpen the Owner Operations Centre for details."

    if config.email_enabled and config.alert_email:
        attempt = NotificationAttempt.objects.create(
            alert=alert,
            channel="email",
            destination_hint=_masked(config.alert_email),
            provider="django-email",
        )
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [config.alert_email], fail_silently=False)
            attempt.status = "sent"
            attempt.delivered_at = timezone.now()
        except Exception as exc:  # delivery failure must be auditable, not fatal to health evaluation
            attempt.status = "failed"
            attempt.error_code = type(exc).__name__[:80]
            attempt.error_message = str(exc)[:255]
        attempt.save(update_fields=["status", "delivered_at", "error_code", "error_message"])
        attempts.append(attempt)

    for channel, enabled in (("sms", config.sms_enabled), ("whatsapp", config.whatsapp_enabled)):
        if not enabled:
            continue
        attempts.append(NotificationAttempt.objects.create(
            alert=alert,
            channel=channel,
            destination_hint=_masked(config.mobile_number),
            provider=config.messaging_provider,
            status="skipped",
            error_code="adapter_not_configured",
            error_message="Live provider delivery remains disabled until credentials and a test message are verified.",
        ))
    return attempts


def evaluate_storage_pressure(*, send_notifications: bool = False) -> OperationalAlert | None:
    config = PlatformOperationsSettings.current()
    percentages = [
        Decimal(row["used_storage"]) * Decimal("100") / Decimal(row["storage_limit"])
        for row in CVStorage.objects.filter(storage_limit__gt=0).values("used_storage", "storage_limit")
    ]
    maximum = max(percentages, default=Decimal("0"))
    critical = Decimal(config.critical_storage_percent)
    warning = Decimal(config.warning_storage_percent)
    fingerprint = "storage:account-capacity"

    if maximum >= critical:
        severity, threshold = "critical", critical
    elif maximum >= warning:
        severity, threshold = "warning", warning
    else:
        resolve_condition(fingerprint)
        return None

    affected = sum(1 for value in percentages if value >= warning)
    alert, created = record_condition(
        fingerprint=fingerprint,
        category="storage",
        severity=severity,
        title="Customer CV storage pressure",
        message=f"{affected} account(s) exceed the storage warning threshold; highest usage is {maximum:.1f}%.",
        metric_value=maximum,
        threshold_value=threshold,
    )
    if created and send_notifications:
        deliver_alert(alert, config)
    return alert
