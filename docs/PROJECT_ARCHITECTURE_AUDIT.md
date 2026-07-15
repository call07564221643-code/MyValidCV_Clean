# MyValidCV Architecture and Code Audit

## Purpose

This document explains how the project applications connect, which database
records they own, where users are authorised, and exactly when payment unlocks
paid services. It reflects the source code in this repository; it is not a
substitute for production-provider configuration or operational monitoring.

## Request and application map

1. Heroku starts `gunicorn config.wsgi` from `Procfile`.
2. `config/settings.py` loads applications, middleware, database, storage,
   social-login credentials, email and payment environment variables.
3. `config/urls.py` sends requests to the owning app:
   - `/`, legacy analysis links: `core`
   - `/register/`, `/login/`, `/settings/`: `accounts`
   - `/accounts/...`: django-allauth provider callbacks
   - `/pricing/`, `/stripe/...`, receipts: `payments`
   - `/dashboard/`: `dashboard`
   - `/ats/...`: `ats`
   - `/analytics/health/`: `analytics`
4. Django views read/write model objects through the ORM. All installed apps use
   the single `DATABASES['default']` connection.
5. Templates render view context. Templates do not authorise access; decorators,
   ownership filters and subscription checks in Python do.

## Database selection

`config/settings.py` selects the database in this order:

1. `TEST_USE_SQLITE=True`: isolated SQLite test database.
2. `DATABASE_URL`: production URL, normally Heroku Postgres.
3. Individual `DB_NAME`, `DB_HOST`, `DB_USER`, etc.: explicit PostgreSQL.
4. Otherwise `db.sqlite3`: local development fallback.

Migrations inside each app create its tables. Foreign keys and one-to-one fields
are the actual connections between apps; imports alone do not create database
relationships.

## App responsibility and database links

### `accounts`

- Django `auth.User` stores identity, hashed password, email and staff flags.
- `UserProfile.user -> User` is one-to-one and stores the fast plan/usage state.
- `accounts/signals.py` creates `UserProfile` after a User is created.
- `SocialAuthProvider` stores display/administration metadata. OAuth secrets are
  environment variables and must not be stored in this table.
- `accounts/views.py` validates local credentials using Django `authenticate()`
  and establishes the session using `login()`.
- `@login_required` on protected views rejects anonymous access.
- `safe_next_url()` prevents a supplied `next` URL becoming an open redirect.

Social registration sequence:

1. `social_login_start()` confirms the provider and required credentials.
2. It redirects Google or LinkedIn to django-allauth.
3. The provider authenticates the person and calls the allauth callback.
4. Allauth creates or retrieves `auth.User` and starts the Django session.
5. The User signal ensures `UserProfile` exists.
6. The user continues to the dashboard.

### `subscriptions`

- `SubscriptionPlan` is the commercial catalogue and feature/usage definition.
- `CustomerSubscription.user -> User` is one-to-one: one current subscription
  state per user.
- `CustomerSubscription.plan -> SubscriptionPlan` identifies purchased access.
- Stripe customer/subscription IDs connect local state to provider state.
- `DiscountCode` validates dates/redemptions and calculates a discounted amount.

Important: there are currently two sources of plan limits: fields on
`SubscriptionPlan` and methods/hard-coded values based on `UserProfile.plan`.
They must remain synchronised until limits are consolidated into one service.

### `payments`

- `PaymentTransaction.user -> User` records who initiated payment.
- `PaymentTransaction.plan -> SubscriptionPlan` freezes the selected plan link.
- `PaymentTransaction.subscription -> CustomerSubscription` links a confirmed
  payment to the access it activated.
- `Invoice.transaction -> PaymentTransaction` is one-to-one.
- `Refund.transaction -> PaymentTransaction` records refund administration.
- `PaymentWebhookLog.event_id` uniquely deduplicates Stripe events.
- `payments/services.py` owns provider HTTP calls and Stripe signature checking.
- `payments/views.py` owns checkout orchestration and subscription activation.

Stripe authorisation and activation sequence:

1. Pricing reads active `SubscriptionPlan` rows.
2. A logged-in user POSTs a Pay Now form; Django CSRF protects the request.
3. `start_stripe_checkout()` creates pending `PaymentTransaction` and `Invoice`
   rows. No paid access is granted here.
4. `create_stripe_checkout_session()` creates hosted recurring Checkout and puts
   the local checkout reference into Stripe metadata.
5. Stripe collects payment; card details never pass through this application.
6. The success return retrieves the Session from Stripe, or Stripe sends a
   signed webhook. Both compare provider state/reference before activation.
7. `activate_paid_transaction()` runs inside a database transaction and updates:
   payment -> paid; invoice -> paid; `CustomerSubscription` -> active; and
   `UserProfile.plan` -> purchased plan. This function is the access boundary.
8. Subscription/invoice webhooks later renew, mark past due, cancel or restore
   the subscription and update `UserProfile.plan` accordingly.

The Stripe webhook is CSRF-exempt because it is not a browser request. It is
authorised by `verify_stripe_signature()` using `STRIPE_WEBHOOK_SECRET`.

### `ats`

- `CVStorage.user -> User` owns per-user storage accounting.
- `CV.user -> User`; `CV.storage -> CVStorage` owns uploaded CVs.
- `JobRole.user -> User` owns job text, URL/file source and inferred deadline.
- `ATSResult.user/CV/JobRole` stores the comparison and result metrics.
- `GeneratedCV` and `GeneratedCoverLetter` are one-to-one with an ATS result.
- `ApplicationReminder.user/JobRole` schedules application email reminders.
- `EnterpriseBatch.user/JobRole` groups an enterprise screening run.
- `EnterpriseCandidateResult.batch -> EnterpriseBatch` stores ranked candidates.

Individual analysis sequence:

1. `@login_required` identifies the user.
2. `UserProfile.can_run_analysis()` checks monthly usage.
3. Forms restrict selectable CVs to the current user.
4. Upload validation and plan storage limits run before persistence.
5. Job input is assembled from text, file or URL.
6. `JobRole`, `ATSResult` and metrics are written for that user.
7. Plus/Professional authorization creates CV and cover-letter drafts.
8. Free users receive the online result without generated downloads.
9. If a deadline is found and requested, `ApplicationReminder` is created.
10. Usage is incremented only after a completed analysis.

Enterprise sequence:

1. `user_can_use_enterprise()` requires superuser or a current active Enterprise
   `CustomerSubscription`.
2. `enterprise_monthly_usage()` enforces the plan's bulk limit.
3. Valid CVs are scored, stored in an `EnterpriseBatch`, ranked, and displayed.
4. Enterprise does not use the individual generated CV/cover-letter function.

Result/detail/download queries include `user=request.user`. Enterprise reports
are likewise owner-filtered except for superusers. These filters are essential
object-level authorisation, not merely presentation logic.

### `dashboard`

`dashboard/views.py` composes account-owned CVs, results, jobs, reminders and
batches. It considers a paid plan effective only when `CustomerSubscription` is
active and not expired; otherwise it falls back to Free. Superusers receive the
owner dashboard, while Enterprise receives enterprise-specific usage and tools.

### `analytics`

The health view aggregates operational/database/payment information. Access is
restricted in its view and it should remain an operations tool, not a public
health endpoint exposing business figures.

### `core`

Owns the read-only landing page. All analysis persistence, engine logic and
authorization now live in `ats`, so the marketing page cannot bypass quotas or
paid feature checks.

### Placeholder or lightly connected apps

`backend`, `ai`, `organizations`, `api`, `reviews`, `notifications`, `billing`,
`career`, and `jobs` remain as reserved source folders but are no longer in
`INSTALLED_APPS`. They add no startup, model, admin or migration overhead.

## Scheduled and operational processes

- `purge_expired_cvs`: deletes CV data older than the retention threshold. It
  must be scheduled (for example Heroku Scheduler); merely having the command
  does not run it automatically.
- `send_application_reminders`: sends due reminder emails and must also be
  scheduled.
- `seed_plans`: creates/updates plan catalogue data during setup/deployment.
- `seed_demo`: development/demo data only; do not run casually in production.

## Dependency audit

- Django: web framework, ORM, sessions, security and admin.
- django-allauth: Google OAuth and LinkedIn OIDC account flow.
- psycopg: PostgreSQL driver used with Heroku Postgres.
- gunicorn: Heroku WSGI server.
- whitenoise: production static-file serving.
- pypdf and python-docx: uploaded CV/job-document text extraction.

Provider APIs are called with Python's standard HTTP library, so no Stripe SDK is
listed. This reduces dependencies but means endpoint schemas, error handling and
API-version compatibility are maintained by this project.

## Code-reference walkthrough for project presentations

Use this order when explaining the implementation to another party:

| Stage | Start with | Then show | What it proves |
| --- | --- | --- | --- |
| Application startup | `Procfile` | `config/wsgi.py`, `config/settings.py` | How Heroku starts Django and loads environment configuration |
| URL ownership | `config/urls.py` | Each active app's `urls.py` | Which app receives each browser/provider request |
| Database connection | `config/settings.py` `DATABASES` | App `models.py` and migrations | All ORM models share Heroku PostgreSQL in production |
| Local registration | `accounts/views.py:register` | `accounts/forms.py`, `accounts/signals.py` | User is validated, saved, logged in and given a profile |
| Local login | `accounts/views.py:login_view` | Django authentication backends in settings | Credentials are authorised and a server session is created |
| Social login | `accounts/views.py:social_login_start` | allauth settings and `/accounts/` URL include | OAuth/OIDC provider callback creates or logs in the same User type |
| Plan catalogue | `subscriptions/models.py:SubscriptionPlan` | `seed_plans` and pricing view/template | Prices, limits and feature flags originate in database records |
| Checkout request | `payments/views.py:start_stripe_checkout` | `PaymentTransaction`, `Invoice` | Logged-in POST creates pending audit rows but grants no access |
| Hosted payment | `payments/services.py:create_stripe_checkout_session` | Stripe metadata/reference | Stripe receives price data and the local reconciliation identifier |
| Provider authorisation | `verify_stripe_signature`, `stripe_success`, `stripe_webhook` | `PaymentWebhookLog` | Only retrieved/signed provider state can confirm payment |
| Paid activation | `payments/views.py:activate_paid_transaction` | `CustomerSubscription`, `UserProfile` | This atomic function is the exact point that grants the paid plan |
| Plan cancellation | webhook sync/set-active/inactive functions | subscription status and profile fallback | Provider lifecycle events revoke or restore access |
| Dashboard | `dashboard/views.py:dashboard` | account-owned ORM queries | Active subscription, expiry, quota and ownership decide displayed tools |
| Individual ATS | `ats/views.py:analyse_cv` | ATS forms/models and result view | Login, quota, ownership and paid generation are enforced server-side |
| Enterprise ATS | `user_can_use_enterprise`, `enterprise_bulk_upload` | batch/candidate models | Active Enterprise subscription and monthly quota protect bulk screening |
| Retention/reminders | ATS management commands | production scheduler configuration | Database/file deletion and reminder email are operational scheduled jobs |
| Operations | `analytics/views.py:website_health` | superuser decorator and aggregate queries | Only owners can inspect internal database/payment health data |

## Dependency direction

The intended source-level dependency direction is:

```text
config
  -> routes all active applications

accounts -> Django auth.User
subscriptions -> auth.User
payments -> auth.User + subscriptions
ats -> auth.User + accounts.UserProfile + subscriptions
dashboard -> accounts + subscriptions + payments + ats
analytics -> accounts + subscriptions + payments + ats + Django operations
templates -> view context and named URLs (presentation only)
```

Circular business updates are avoided by making `payments` responsible for
writing subscription activation and making `subscriptions.services` the policy
read by ATS/dashboard. `UserProfile.plan` is only a synchronized display/cache
field and is never accepted as proof of paid access.

## Audit findings and recommended order

### High priority

1. Google and LinkedIn production credentials are not configured, so deployed
   social login returns to the login page before provider authentication.
2. A real Stripe end-to-end transaction remains an operational verification:
   set keys/webhook secret/price IDs, make test purchases, inspect webhook logs.
3. Ensure the CV purge and reminder commands are actually scheduled. The
   30-day promise is otherwise not automatically enforced.
4. Configure production SMTP/transactional email; console email does not deliver
   receipts or deadline reminders to customers.

### Medium priority

1. Move CV files to encrypted durable object storage when usage grows. The
   current database byte copy is deliberate for Heroku durability and is purged
   with the CV row after the retention period.
2. Consider splitting the larger ATS and payments view modules into smaller
   orchestration services as the product grows.
3. Add a customer-facing subscription-management/cancellation portal before a
   broad paid launch.

### Lower priority / maintainability

1. Split the remaining large ATS/payments orchestration views further as new
   product features are added.
2. Replace broad webhook exception handling with structured logging and
   known exception types while still returning retryable failures.
3. Add browser/provider sandbox tests for completed Google and LinkedIn callbacks
   once production OAuth applications are configured.

## Stakeholder explanation in one sentence

The authenticated Django User owns all customer records; a verified provider
payment activates `CustomerSubscription` and updates `UserProfile.plan`; ATS and
dashboard views read those database records and enforce login, ownership, plan
and quota checks before delivering each service.
