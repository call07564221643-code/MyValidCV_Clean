# MyValidCV

MyValidCV is a Django micro-SaaS for CV-to-job ATS analysis, paid individual
document generation, Enterprise bulk screening, recurring Stripe subscriptions,
social login and 30-day CV retention.

## ATS v2

ATS v2 provides an explainable **CV-to-role evidence match**, not a prediction
of hiring success. It validates the job advert, separates mandatory, required,
preferred and responsibility requirements, and links detected requirements to
the supporting CV passage.

The Truth Gate classifies each item as:

- verified in the CV;
- mentioned without supporting evidence;
- candidate confirmation required; or
- proof, training, qualification or licence required.

Only verified CV evidence is eligible for automatic reuse. Component scores for
skills, requirements, evidence and readability are measured independently, and
the report includes an assessment-confidence indicator. Enterprise rankings are
advisory, preserve equal ranks for tied scores and always require human review.

## Maya service adviser

Maya is grounded at request time from the maintained MyValidCV service knowledge
in `core/maya_knowledge.py`. Relevant topics are supplied to Ollama alongside
safe, minimal account context such as the signed-in user's active service level
and analysis allowance. Maya can explain ATS v2, Truth Gate evidence, plans,
documents, Enterprise screening, payments, privacy and service limitations.

Chat messages are not used to train the model or permanently retained by this
feature. Only a bounded recent conversation is sent for continuity. Maya must
not invent prices, discounts, entitlements, refund decisions or hiring outcomes,
and account-specific support remains with `support@myvalidcv.com`.

## Experience feedback

ATS results and Maya include an accessible five-star experience rating with
optional feedback categories and comments. Feedback is private by default.
Four- and five-star comments can enter testimonial moderation only when the user
explicitly grants permission. The owner feedback report shows aggregate ratings
and recent comments; only owner-approved, opted-in testimonials can appear on
the public landing page.

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

- `core`: landing page, Maya service adviser and experience feedback.
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
- [Testing and release evidence](docs/TESTING.md)

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

## Google PageSpeed Insights

### Desktop loading speed

![MyValidCV Google PageSpeed Insights desktop loading speed result](static/images/MVCV-%20Desk%20Top%20Speed%20test%20%26%20performance.png)

### Mobile loading speed

![MyValidCV Google PageSpeed Insights mobile loading speed result](static/images/MVCV-%20Mobil%20Speed%20test%20%26%20performance.png)

## W3C HTML validation

The W3C Nu HTML Checker completed validation with no errors or warnings.

![MyValidCV W3C Nu HTML Checker validation result](static/images/MVCV-%20html%20test%20%26%20performance.png)
