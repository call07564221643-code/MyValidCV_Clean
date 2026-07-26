# MyValidCV Architecture, Dependency and Complexity Audit

## Scope

This document describes the source code after the July 2026 hygiene audit. It
maps runtime packages, Django applications, database relationships and the
highest-maintenance areas. Provider configuration and live credentials remain
environment concerns and are not inferred from source code.

## Runtime path

1. Heroku runs the release command in `Procfile`: migrations, plan seeding and
   ATS taxonomy seeding.
2. Gunicorn loads `config.wsgi`, which loads `config.settings`.
3. `config.urls` delegates requests to the app that owns the workflow.
4. Views enforce authentication, ownership, entitlement and quota checks.
5. Models use the single configured Django database connection.
6. Templates display view context; templates never grant access.

Database selection, in order:

1. `TEST_USE_SQLITE=True`: isolated test database.
2. `DATABASE_URL`: production PostgreSQL, normally supplied by Heroku.
3. Explicit `DB_NAME`/`DB_HOST` variables: manually configured PostgreSQL.
4. `db.sqlite3`: local-development fallback.

## Direct Python dependencies

Only direct runtime packages belong in `requirements.txt`. Transitive packages
such as `asgiref`, `requests`, `cryptography` and `lxml` are installed by these
packages and must not be pinned independently without a specific reason.

| Dependency | Why it exists | Source connection | Removal impact |
| --- | --- | --- | --- |
| `Django` | Web framework, ORM, migrations, forms, sessions, admin and security middleware | Every app; startup through `manage.py` and `config` | Application cannot run |
| `gunicorn` | Production WSGI process manager | `Procfile -> config.wsgi` | Heroku web process cannot start |
| `pypdf` | Extracts text from uploaded PDF CVs and job files | `ats.engine.ATSEngine.extract_text_from_upload` | PDF analysis stops working |
| `python-docx` | Reads uploaded DOCX files and creates downloadable CV documents | `ats.engine`, `ats.cv_drafting` | DOCX upload/export stops working |
| `psycopg[binary]` | PostgreSQL driver | Django database backend selected by `DATABASE_URL` | Production database connection fails |
| `whitenoise` | Serves fingerprinted/compressed static assets from the Django slug | Middleware and static storage in `config.settings` | Production CSS/JS/image delivery fails |
| `django-allauth[socialaccount]` | OAuth/OIDC callback and account integration | Installed apps, middleware, auth backend and `/accounts/` URLs | Social login stops working |

Stripe and Ollama-compatible APIs use Python's standard `urllib` library. That
keeps the package set small, but this project must maintain provider payload,
timeout, error and API-compatibility handling itself.

The audit found no removable production dependency. `ruff` was used only as a
local audit tool and is deliberately not in `requirements.txt`.

## Django application dependency map

Arrows mean the source app imports a model or service from the target app.

```text
config
  -> core, accounts, payments, dashboard, ats, analytics

core
  -> accounts (signed-in usage context)
  -> ats (customer homepage summaries and ATS feedback ownership)
  -> subscriptions (Maya/account entitlement context)

accounts
  -> Django auth.User
  -> subscriptions.services (deferred entitlement/usage policy calls)

subscriptions
  -> Django auth.User
  -> accounts.UserProfile only in administration/synchronisation code

payments
  -> accounts.UserProfile
  -> subscriptions (plans, discounts and subscription activation)

ats
  -> accounts.UserProfile
  -> subscriptions.services (feature and quota policy)

dashboard
  -> accounts, subscriptions, payments, ats, core feedback

analytics
  -> accounts, subscriptions, payments, ats
  -> Django database/migration/runtime inspection
```

The broad dependencies in `dashboard` and `analytics` are intentional: both are
read/composition layers. Business apps must not import either of them.

## App ownership and database links

### `accounts`

- Owns `UserProfile` and `SocialAuthProvider`.
- `UserProfile.user -> auth.User` is one-to-one.
- A post-save signal creates a profile for each new Django user.
- Local login uses `EmailOrUsernameBackend`.
- Social-login entry points delegate callbacks to django-allauth.
- `UserProfile.plan` is a synchronised display/cache value. Paid access must be
  verified through `subscriptions.services`, not trusted from this field alone.

### `subscriptions`

- Owns `SubscriptionPlan`, `CustomerSubscription` and `DiscountCode`.
- `CustomerSubscription.user -> auth.User` is one-to-one.
- `CustomerSubscription.plan -> SubscriptionPlan`.
- `subscriptions.services` is the central entitlement and allowance policy used
  by ATS, dashboard and Maya.
- Plan catalogue rows are synchronised by `seed_plans` during release.

### `payments`

- Owns `PaymentTransaction`, `Invoice`, `Refund` and `PaymentWebhookLog`.
- Transactions link the user, chosen plan and activated subscription.
- Invoice and refund rows preserve the financial audit trail.
- Checkout creates pending records; it does not grant access.
- `activate_paid_transaction()` is the atomic paid-access boundary.
- Stripe return/webhook data must be verified before activation.
- Webhook event IDs are unique to prevent duplicate processing.

### `ats`

- Owns CV storage, job roles, taxonomy, scoring results, generated documents,
  reminders, Stage 2 bullet decisions and Enterprise batches.
- `CV`, `JobRole`, `ATSResult`, generated documents and batches all link to the
  owning Django user.
- `ATSResult.cv -> CV`; `ATSResult.job_role -> JobRole`.
- `GeneratedCV` and `GeneratedCoverLetter` are one-to-one with an ATS result.
- `CVBulletSuggestion.ats_result -> ATSResult`; `applied_text` and `applied_at`
  persist whether a reviewed bullet is current in the generated CV.
- `EnterpriseCandidateResult.batch -> EnterpriseBatch`.
- Individual results/downloads are always filtered by `user=request.user`.
- Enterprise upload is limited to 15 files per request; daily candidate usage is
  separately limited by entitlement/policy (currently 50).

Document processing is deliberately split:

- `ats.engine`: PDF/DOCX/TXT extraction and structural CV validation only.
- `ats.scoring`: the single ATS scoring and evidence implementation.
- `ats.cv_drafting`: evidence-grounded CV structure and DOCX export.
- `ats.bullet_rewriting`: Stage 2 bullet extraction and application.
- `ats.views`: HTTP workflow orchestration and authorisation.

### `core`

- Owns landing-page composition, Maya and `ExperienceFeedback`.
- Maya retrieves curated facts from `core.maya_knowledge`.
- If `OLLAMA_BASE_URL` is configured, recent bounded history and selected
  knowledge are sent to the hosted model. Otherwise Maya uses the deterministic
  conversational fallback.
- Chats are not written to a conversation model.
- ATS feedback requires ownership of the referenced result.

### `dashboard`

- Composes account-owned CVs, results, reminders, subscriptions, payments,
  Enterprise usage and feedback.
- Superuser owner screens are enforced server-side, not by hidden navigation.
- This app owns no database model; it is a read/orchestration layer.

### `analytics`

- Owns `FinancialAssumption`.
- The owner-only health view aggregates database, migrations, usage, payment,
  provider-readiness and estimated finance information.
- It is an internal operations screen and must never be made public.

## Main workflow links

### Individual application

```text
auth.User
  -> CV upload and validation
  -> JobRole
  -> ATSResult + evidence map
  -> Truth Gate confirmations
  -> GeneratedCV / GeneratedCoverLetter (entitlement permitting)
  -> CVBulletSuggestion review and application
  -> save and download
```

### Paid access

```text
SubscriptionPlan
  -> pending PaymentTransaction + Invoice
  -> verified Stripe checkout/webhook
  -> active CustomerSubscription
  -> synchronised UserProfile.plan
  -> subscriptions.services entitlements
  -> ATS/dashboard feature access
```

### Enterprise screening

```text
active Enterprise entitlement
  -> one JobRole
  -> EnterpriseBatch
  -> up to 15 uploaded CVs per request
  -> EnterpriseCandidateResult rows
  -> advisory ranking/report
  -> mandatory human review
```

## Cleanup completed in this audit

- Removed an empty root `settings.py`; Django uses only `config/settings.py`.
- Removed the empty, unreferenced `core/docs` placeholder set.
- Removed `templates/ats/models.py`, an obsolete duplicate model definition
  incorrectly stored in the template tree.
- Removed unused imports and local variables reported by static analysis.
- Removed two unused database queries from every owner health-page request.
- Reduced `ats/engine.py` from 599 lines to the extraction/validation code the
  application actually calls.
- Removed optional spaCy/RapidFuzz branches that were not production
  dependencies and could silently change results between environments.
- Fixed TXT fallback decoding to reuse the uploaded bytes instead of reading an
  already-consumed file stream.

## Complexity findings

Highest-maintenance modules after cleanup:

| Module/area | Reason | Recommended boundary |
| --- | --- | --- |
| `ats/views.py` | Many individual, report and Enterprise HTTP workflows | Split by `individual`, `result`, `documents`, `enterprise` when the next major feature is added |
| `analytics/views.py:website_health` | One large owner-health aggregation | Extract finance, provider and database snapshot services |
| `ats/scoring.py` | Core scoring, taxonomy, evidence and formatting in one module | Preserve one scoring entry point; split internal evidence/taxonomy helpers only with golden-result tests |
| `payments/views.py` | Checkout, mock flow, webhook and activation orchestration | Move activation and webhook synchronisation into explicit services |
| Large ATS/result templates and inline CSS | Report presentation has grown substantially | Move report CSS into a dedicated static stylesheet and split stable template sections into includes |

These are maintainability risks, not proven dead code. Refactoring them should be
feature-led and protected by tests; deleting or moving them during a hygiene
pass would add risk without changing user value.

## Operational dependencies outside Python

- Heroku web dyno: runs Gunicorn.
- Heroku PostgreSQL: durable shared production data.
- Heroku Scheduler: must run CV retention and reminder commands.
- Stripe: checkout, lifecycle events and webhook signing.
- SMTP/transactional email: receipts, password reset and reminders.
- OAuth/OIDC provider configuration: Google/LinkedIn social login.
- Optional hosted Ollama-compatible endpoint: open-ended Maya responses.

Source code can validate configuration shape but cannot prove these external
services are funded, reachable or correctly configured. Production health and
provider sandbox tests remain necessary.

## Audit guardrails

- Do not remove migrations merely because they look old; they are the database
  history required for new environments.
- Do not delete local `db.sqlite3` or `media/` during source cleanup; they can
  contain developer/customer test data.
- Do not trust template visibility as authorisation.
- Do not merge scoring implementations again: `ats.scoring` is authoritative.
- Keep paid access derived from active subscription records and entitlements.
