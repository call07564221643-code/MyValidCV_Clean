import platform
from decimal import Decimal

import django
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from accounts.models import SocialAuthProvider, UserProfile
from analytics.models import FinancialAssumption
from ats.models import ATSResult, CV, CVStorage, EnterpriseBatch, EnterpriseCandidateResult, GeneratedCV
from payments.models import Invoice, PaymentTransaction, PaymentWebhookLog, Refund
from subscriptions.models import CustomerSubscription, SubscriptionPlan


def _money(value):
    return value or Decimal("0.00")


def _currency(value):
    return _money(value).quantize(Decimal("0.01"))


def _percent(part, whole):
    if not whole:
        return 0
    return round((part / whole) * 100, 1)


def _check(title, status, detail, action, category="System"):
    return {
        "title": title,
        "status": status,
        "detail": detail,
        "action": action,
        "category": category,
    }


def _migration_status():
    try:
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        return len(pending)
    except Exception:
        return None


@user_passes_test(lambda user: user.is_superuser, login_url="login")
def website_health(request):
    """Admin health report for product, database, payments, and operating risks."""
    now = timezone.now()
    last_7_days = now - timezone.timedelta(days=7)
    last_30_days = now - timezone.timedelta(days=30)

    users_total = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()
    profiles_total = UserProfile.objects.count()
    missing_profiles = max(users_total - profiles_total, 0)

    cvs_total = CV.objects.count()
    valid_cvs = CV.objects.filter(is_valid_cv=True).count()
    rejected_cvs = CV.objects.filter(Q(is_valid_cv=False) | Q(validation_status="rejected")).count()
    cvs_without_storage = CV.objects.filter(storage__isnull=True).count()
    storage_total = CVStorage.objects.count()
    storage_warning_count = CVStorage.objects.filter(used_storage__gte=0.8 * 10 * 1024 * 1024).count()

    ats_total = ATSResult.objects.count()
    ats_completed = ATSResult.objects.filter(status="completed").count()
    ats_failed = ATSResult.objects.filter(status="failed").count()
    ats_last_7_days = ATSResult.objects.filter(created_at__gte=last_7_days).count()
    ats_avg_score = ATSResult.objects.aggregate(avg=Avg("score"))["avg"] or 0
    low_score_results = ATSResult.objects.filter(score__lt=50).count()
    results_without_job_role = ATSResult.objects.filter(job_role__isnull=True).count()

    enterprise_batches = EnterpriseBatch.objects.count()
    enterprise_candidates = EnterpriseCandidateResult.objects.count()
    enterprise_avg_score = EnterpriseCandidateResult.objects.aggregate(avg=Avg("score"))["avg"] or 0

    plan_count = SubscriptionPlan.objects.filter(is_active=True).count()
    subscriptions_total = CustomerSubscription.objects.count()
    active_subscriptions = CustomerSubscription.objects.filter(status="active").count()
    past_due_subscriptions = CustomerSubscription.objects.filter(status="past_due").count()
    expired_active_subscriptions = CustomerSubscription.objects.filter(
        status="active",
        current_period_end__lt=now,
    ).count()

    paid_transactions = PaymentTransaction.objects.filter(status="paid")
    transactions_total = PaymentTransaction.objects.count()
    transactions_last_30_days = PaymentTransaction.objects.filter(created_at__gte=last_30_days).count()
    paid_count = paid_transactions.count()
    paid_count_30_days = paid_transactions.filter(created_at__gte=last_30_days).count()
    failed_payments = PaymentTransaction.objects.filter(status="failed").count()
    payment_success_rate = _percent(paid_count, transactions_total)
    revenue_total = _money(paid_transactions.aggregate(total=Sum("amount"))["total"])
    revenue_30_days = _money(paid_transactions.filter(created_at__gte=last_30_days).aggregate(total=Sum("amount"))["total"])
    refunds_total = _money(Refund.objects.filter(status__in=["approved", "processed"]).aggregate(total=Sum("amount"))["total"])
    open_invoice_value = _money(Invoice.objects.filter(status="open").aggregate(total=Sum("amount"))["total"])
    open_invoices = Invoice.objects.filter(status="open").count()
    paid_invoices = Invoice.objects.filter(status="paid").count()
    receipt_failures = Invoice.objects.exclude(receipt_email_status__in=["sent", "not_sent"]).count()
    receipts_not_sent = Invoice.objects.filter(status="paid", receipt_sent_at__isnull=True).count()
    webhook_errors = PaymentWebhookLog.objects.exclude(error="").count()
    unprocessed_webhooks = PaymentWebhookLog.objects.filter(is_processed=False).count()

    social_providers = SocialAuthProvider.objects.all()
    active_social = social_providers.filter(is_active=True).count()
    configured_social = social_providers.filter(is_active=True, is_configured=True).count()

    pending_migrations = _migration_status()
    db_ok = True
    db_detail = connection.vendor
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        db_ok = False
        db_detail = str(exc)

    provider_readiness = {
        "stripe_live": bool(getattr(settings, "STRIPE_SECRET_KEY", "")) and not getattr(settings, "STRIPE_MOCK_MODE", True),
        "stripe_mock": getattr(settings, "STRIPE_MOCK_MODE", True),
        "email_console": "console" in getattr(settings, "EMAIL_BACKEND", ""),
    }

    finance_assumption = FinancialAssumption.current()
    payment_processing_cost = (
        revenue_30_days * finance_assumption.payment_percent_fee
    ) + (Decimal(str(paid_count_30_days)) * finance_assumption.payment_fixed_fee)
    ai_processing_cost = Decimal(str(ats_last_7_days)) * finance_assumption.ai_cost_per_validation
    supplier_expenses = [
        {"name": "Hosting / app server", "type": "Fixed monthly", "amount": finance_assumption.hosting_monthly_cost},
        {"name": "PostgreSQL database", "type": "Fixed monthly", "amount": finance_assumption.database_monthly_cost},
        {"name": "File storage / backups", "type": "Fixed monthly", "amount": finance_assumption.storage_backup_monthly_cost},
        {"name": "Email receipts", "type": "Fixed monthly", "amount": finance_assumption.email_monthly_cost},
        {"name": "Monitoring / uptime", "type": "Fixed monthly", "amount": finance_assumption.monitoring_monthly_cost},
        {"name": "Software tools", "type": "Fixed monthly", "amount": finance_assumption.software_tools_monthly_cost},
        {"name": "Marketing", "type": "Fixed monthly", "amount": finance_assumption.marketing_monthly_cost},
        {"name": "Accounting / admin", "type": "Fixed monthly", "amount": finance_assumption.accounting_admin_monthly_cost},
        {"name": "Payment processing", "type": "Variable estimate", "amount": payment_processing_cost},
        {"name": "AI / ATS processing", "type": "Variable estimate", "amount": ai_processing_cost},
    ]
    supplier_expense_total = sum((item["amount"] for item in supplier_expenses), Decimal("0.00"))
    net_revenue_30_days = revenue_30_days - refunds_total
    estimated_profit_30_days = net_revenue_30_days - supplier_expense_total
    estimated_margin = _percent(float(estimated_profit_30_days), float(net_revenue_30_days)) if net_revenue_30_days > 0 else 0
    tax_accrual = estimated_profit_30_days * finance_assumption.tax_accrual_percent if estimated_profit_30_days > 0 else Decimal("0.00")
    cash_estimate = finance_assumption.cash_reserve + revenue_total - refunds_total - supplier_expense_total
    current_assets = cash_estimate + open_invoice_value
    monthly_obligations = supplier_expense_total
    deferred_service_liability = active_subscriptions * Decimal("3.00")
    current_liabilities = monthly_obligations + deferred_service_liability + finance_assumption.accounts_payable + tax_accrual
    owner_equity_estimate = current_assets - current_liabilities
    finance_status = "ok" if estimated_profit_30_days >= 0 else "warning"

    plan_cost_fields = {
        "free": finance_assumption.free_user_monthly_cost,
        "plus": finance_assumption.plus_user_monthly_cost,
        "professional": finance_assumption.professional_user_monthly_cost,
        "enterprise": finance_assumption.enterprise_user_monthly_cost,
    }
    plan_labels = {
        "free": "Free",
        "plus": "Plus",
        "professional": "Professional",
        "enterprise": "Enterprise",
    }
    plan_economics = []
    fixed_cost_total = finance_assumption.fixed_monthly_cost_total()
    generated_30_days = GeneratedCV.objects.filter(created_at__gte=last_30_days).count()
    for plan_code, label in plan_labels.items():
        plan_users = UserProfile.objects.filter(plan=plan_code).count()
        active_plan_users = UserProfile.objects.filter(plan=plan_code, user__is_active=True).count()
        plan_validations = ATSResult.objects.filter(user__profile__plan=plan_code, created_at__gte=last_30_days).count()
        plan_generated = GeneratedCV.objects.filter(user__profile__plan=plan_code, created_at__gte=last_30_days).count()
        plan_enterprise_batches = EnterpriseBatch.objects.filter(user__profile__plan=plan_code, created_at__gte=last_30_days).count()
        plan_revenue = _money(paid_transactions.filter(plan__code=plan_code, created_at__gte=last_30_days).aggregate(total=Sum("amount"))["total"])
        plan_refunds = _money(Refund.objects.filter(transaction__plan__code=plan_code, status__in=["approved", "processed"]).aggregate(total=Sum("amount"))["total"])
        plan_paid_count = paid_transactions.filter(plan__code=plan_code, created_at__gte=last_30_days).count()
        plan_variable_cost = (
            Decimal(str(plan_users)) * plan_cost_fields[plan_code]
            + Decimal(str(plan_validations)) * finance_assumption.ai_cost_per_validation
            + Decimal(str(plan_generated)) * finance_assumption.generated_cv_cost
            + Decimal(str(plan_enterprise_batches)) * finance_assumption.enterprise_batch_delivery_cost
        )
        plan_payment_cost = (plan_revenue * finance_assumption.payment_percent_fee) + (
            Decimal(str(plan_paid_count)) * finance_assumption.payment_fixed_fee
        )
        plan_fixed_allocation = fixed_cost_total * Decimal(str(plan_users)) / Decimal(str(users_total)) if users_total else Decimal("0.00")
        plan_total_cost = plan_variable_cost + plan_payment_cost + plan_fixed_allocation
        plan_net_revenue = plan_revenue - plan_refunds
        plan_profit = plan_net_revenue - plan_total_cost
        plan_economics.append(
            {
                "code": plan_code,
                "label": label,
                "users": plan_users,
                "active_users": active_plan_users,
                "validations": plan_validations,
                "generated_cvs": plan_generated,
                "revenue": _currency(plan_revenue),
                "refunds": _currency(plan_refunds),
                "cost": _currency(plan_total_cost),
                "profit": _currency(plan_profit),
                "benefit_ratio": _percent(float(plan_net_revenue), float(plan_total_cost)) if plan_total_cost > 0 else 0,
                "status": "Profitable" if plan_profit >= 0 else "Investment",
            }
        )
    total_plan_cost = sum((Decimal(str(item["cost"])) for item in plan_economics), Decimal("0.00"))
    free_cost = next((item["cost"] for item in plan_economics if item["code"] == "free"), Decimal("0.00"))
    paid_users = sum(item["users"] for item in plan_economics if item["code"] != "free")
    free_users = next((item["users"] for item in plan_economics if item["code"] == "free"), 0)
    free_to_paid_ratio = _percent(paid_users, free_users + paid_users)

    checks = [
        _check(
            "Database connection",
            "ok" if db_ok else "critical",
            f"Connected through Django using {db_detail}.",
            "Keep PostgreSQL running before starting Django." if db_ok else "Restart PostgreSQL and confirm .env credentials.",
            "System",
        ),
        _check(
            "Pending migrations",
            "ok" if pending_migrations == 0 else "warning" if pending_migrations else "critical",
            "All migrations are applied." if pending_migrations == 0 else f"{pending_migrations or 'Unknown'} pending migration(s).",
            "Run python manage.py migrate after each model change.",
            "System",
        ),
        _check(
            "Production safety",
            "warning" if settings.DEBUG else "ok",
            "DEBUG is currently on." if settings.DEBUG else "DEBUG is off.",
            "Before launch, set DEBUG=False, configure ALLOWED_HOSTS, HTTPS, and secure cookies.",
            "Compatibility",
        ),
        _check(
            "Profile creation",
            "ok" if missing_profiles == 0 else "critical",
            f"{missing_profiles} user(s) are missing UserProfile records.",
            "Run a backfill if this number is above zero; new users should be covered by signals.",
            "Data Quality",
        ),
        _check(
            "CV storage relationships",
            "ok" if cvs_without_storage == 0 else "warning",
            f"{cvs_without_storage} CV upload(s) are not linked to CVStorage.",
            "Backfill CV storage links so quota and storage reports stay accurate.",
            "Data Quality",
        ),
        _check(
            "CV quality gate",
            "ok" if rejected_cvs == 0 else "warning",
            f"{rejected_cvs} uploaded document(s) were rejected or marked invalid.",
            "Review rejected uploads to improve the user message and CV acceptance rules.",
            "ATS",
        ),
        _check(
            "ATS processing",
            "ok" if ats_failed == 0 else "warning",
            f"{ats_failed} failed ATS result(s), {ats_completed} completed.",
            "Investigate failed results and add logging if failures continue.",
            "ATS",
        ),
        _check(
            "Payment success",
            "ok" if payment_success_rate >= 85 or transactions_total == 0 else "warning",
            f"{payment_success_rate}% payment success rate across {transactions_total} transaction(s).",
            "Review failed payments, abandoned checkouts, and provider errors weekly.",
            "Payments",
        ),
        _check(
            "Receipt delivery",
            "ok" if receipts_not_sent == 0 and receipt_failures == 0 else "warning",
            f"{receipts_not_sent} paid invoice receipt(s) not sent; {receipt_failures} receipt issue(s).",
            "Move from console email to SMTP or a transactional email provider before launch.",
            "Payments",
        ),
        _check(
            "Payment provider readiness",
            "ok" if provider_readiness["stripe_live"] else "warning",
            "Stripe live mode is configured." if provider_readiness["stripe_live"] else "Stripe live credentials are incomplete.",
            "Add the Stripe secret and webhook keys before accepting payments.",
            "Payments",
        ),
        _check(
            "Social login readiness",
            "ok" if active_social == configured_social else "warning",
            f"{configured_social} of {active_social} active social provider(s) are configured.",
            "Add OAuth keys for Google, LinkedIn, and any extra provider before showing them as ready.",
            "Compatibility",
        ),
        _check(
            "Webhook processing",
            "ok" if webhook_errors == 0 and unprocessed_webhooks == 0 else "warning",
            f"{webhook_errors} webhook error(s), {unprocessed_webhooks} unprocessed webhook(s).",
            "Review webhook logs after every payment provider test.",
            "Payments",
        ),
        _check(
            "Subscription status",
            "ok" if past_due_subscriptions == 0 and expired_active_subscriptions == 0 else "warning",
            f"{past_due_subscriptions} past due, {expired_active_subscriptions} active subscriptions past period end.",
            "Add a scheduled subscription audit before production billing.",
            "Subscriptions",
        ),
        _check(
            "Mini finance health",
            finance_status,
            f"Estimated 30-day profit is {finance_assumption.currency} {_currency(estimated_profit_30_days)} after supplier costs.",
            "Review the editable Financial Assumption record in admin each month.",
            "Finance",
        ),
    ]

    critical_count = sum(1 for item in checks if item["status"] == "critical")
    warning_count = sum(1 for item in checks if item["status"] == "warning")
    ok_count = sum(1 for item in checks if item["status"] == "ok")

    context = {
        "checked_at": now,
        "health_score": max(0, int((ok_count / len(checks)) * 100) - (critical_count * 8)) if checks else 0,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "ok_count": ok_count,
        "checks": checks,
        "system": {
            "python": platform.python_version(),
            "django": django.get_version(),
            "database": connection.vendor,
            "debug": settings.DEBUG,
            "allowed_hosts": ", ".join(settings.ALLOWED_HOSTS),
            "email_backend": settings.EMAIL_BACKEND,
            "static_url": settings.STATIC_URL,
            "media_url": settings.MEDIA_URL,
        },
        "usage": {
            "users_total": users_total,
            "active_users": active_users,
            "staff_users": staff_users,
            "profiles_total": profiles_total,
            "cvs_total": cvs_total,
            "valid_cvs": valid_cvs,
            "storage_total": storage_total,
            "storage_warning_count": storage_warning_count,
            "ats_total": ats_total,
            "ats_last_7_days": ats_last_7_days,
            "ats_avg_score": round(ats_avg_score, 1),
            "low_score_results": low_score_results,
            "results_without_job_role": results_without_job_role,
            "enterprise_batches": enterprise_batches,
            "enterprise_candidates": enterprise_candidates,
            "enterprise_avg_score": round(enterprise_avg_score, 1),
        },
        "financial": {
            "plan_count": plan_count,
            "subscriptions_total": subscriptions_total,
            "active_subscriptions": active_subscriptions,
            "transactions_total": transactions_total,
            "transactions_last_30_days": transactions_last_30_days,
            "payment_success_rate": payment_success_rate,
            "paid_invoices": paid_invoices,
            "open_invoices": open_invoices,
            "open_invoice_value": open_invoice_value,
            "revenue_total": revenue_total,
            "revenue_30_days": revenue_30_days,
            "refunds_total": refunds_total,
        },
        "mini_finance": {
            "currency": finance_assumption.currency,
            "assumption_id": finance_assumption.id,
            "assumption_name": finance_assumption.name,
            "gross_revenue_30_days": _currency(revenue_30_days),
            "refunds_total": _currency(refunds_total),
            "net_revenue_30_days": _currency(net_revenue_30_days),
            "supplier_expenses": [
                {**item, "amount": _currency(item["amount"])} for item in supplier_expenses
            ],
            "supplier_expense_total": _currency(supplier_expense_total),
            "estimated_profit_30_days": _currency(estimated_profit_30_days),
            "estimated_margin": estimated_margin,
            "balance_sheet": {
                "cash_estimate": _currency(cash_estimate),
                "accounts_receivable": _currency(open_invoice_value),
                "current_assets": _currency(current_assets),
                "monthly_supplier_obligations": _currency(monthly_obligations),
                "deferred_service_liability": _currency(deferred_service_liability),
                "accounts_payable": _currency(finance_assumption.accounts_payable),
                "tax_accrual": _currency(tax_accrual),
                "current_liabilities": _currency(current_liabilities),
                "owner_equity_estimate": _currency(owner_equity_estimate),
            },
        },
        "unit_economics": {
            "plan_rows": plan_economics,
            "total_plan_cost": _currency(total_plan_cost),
            "free_cost": _currency(free_cost),
            "paid_users": paid_users,
            "free_users": free_users,
            "free_to_paid_ratio": free_to_paid_ratio,
        },
        "provider_readiness": provider_readiness,
    }
    return render(request, "analytics/website_health.html", context)
