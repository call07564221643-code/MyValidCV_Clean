# MyValidCV

MyValidCV is a Django micro-SaaS for CV-to-job ATS analysis, paid individual
document generation, Enterprise bulk screening, recurring Stripe subscriptions,
social login and 30-day CV retention.

## Product plans

| Plan | Monthly allowance | Included services |
| --- | ---: | --- |
| Free | 5 analyses | One retained CV, online ATS result, job text/URL/file and deadline alert |
| Plus (GBP 4.99/month) | 20 analyses | Job URL/file input, tailored CV, cover letter, deadline alert |
| Enterprise (GBP 49/month) | 50 bulk CV scans | Bulk ranking and reports; no generated CV or cover letter |

The database plan catalogue is authoritative. `subscriptions.services` resolves
entitlements from a current `CustomerSubscription`; `UserProfile.plan` alone
never grants paid access.

## Active Django apps

- `core`: read-only landing page.
- `accounts`: local/social authentication, settings and usage profile.
- `subscriptions`: plans, subscriptions, discounts and entitlement policy.
- `payments`: Stripe Checkout, signed webhooks, invoices and receipts.
- `ats`: CV storage/extraction, individual analysis, generated documents,
  deadline reminders and Enterprise batches.
- `dashboard`: customer/Enterprise/owner dashboard composition.
- `analytics`: superuser-only operational and financial health report.

See [docs/PROJECT_ARCHITECTURE_AUDIT.md](docs/PROJECT_ARCHITECTURE_AUDIT.md) for
the full request, database, authorization and payment sequence.

## Agile and UX workflow

The project is managed as a lean Agile micro-SaaS:

- [Agile operating model](docs/AGILE_OPERATING_MODEL.md)
- [UX playbook](docs/USER_EXPERIENCE_PLAYBOOK.md)
- [Product backlog](docs/PRODUCT_BACKLOG.md)
- [Kanban board](docs/KANBAN_BOARD.md)
- [GitHub Project setup](docs/GITHUB_PROJECT_SETUP.md)
- [GitHub Project issue register](docs/GITHUB_PROJECT_ISSUE_REGISTER.md)

Keep the Kanban board updated after each deployment. Protect the core user
journey: Upload CV -> Add Job -> Validate -> Improve -> Apply.

## Local setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_plans
python manage.py createsuperuser
python manage.py runserver
```

Copy secrets into a local `.env`; never commit it. SQLite is the local fallback.
Production uses Heroku PostgreSQL through `DATABASE_URL`.

## Required production configuration

```text
SECRET_KEY
DEBUG=False
ALLOWED_HOSTS
DATABASE_URL
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET
LINKEDIN_OAUTH_CLIENT_ID
LINKEDIN_OAUTH_CLIENT_SECRET
EMAIL_BACKEND
EMAIL_HOST
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
DEFAULT_FROM_EMAIL
```

Stripe webhook URL:

```text
https://<host>/stripe/webhook/
```

Google callback:

```text
https://<host>/accounts/google/login/callback/
```

LinkedIn callback:

```text
https://<host>/accounts/oidc/linkedin/login/callback/
```

## Deployment and scheduled work

The `Procfile` release phase applies migrations and synchronizes the plan
catalogue. Configure Heroku Scheduler to run:

```text
python manage.py purge_expired_cvs
python manage.py send_application_reminders
```

Run retention daily and reminders at least daily. CV file bytes are retained in
PostgreSQL so Heroku dyno restarts do not lose them; purging the CV row removes
the database bytes and associated storage file.

## Verification

```powershell
$env:TEST_USE_SQLITE='True'
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py check --deploy
```

Mock Stripe checkout is available only when both `DEBUG=True` and
`STRIPE_MOCK_MODE=True`; it is unreachable in production.
