# MyValidCV Backend - Short Presentation Guide

## Platform and app count

MyValidCV is one Django platform split into **seven custom apps**:

| App | Purpose | Files | Lines |
|---|---|---:|---:|
| `core` | Main pages, feedback and Maya | 7 | 498 |
| `accounts` | Login, registration and profiles | 9 | 364 |
| `subscriptions` | Plans, limits and entitlements | 8 | 304 |
| `payments` | Stripe payments and webhooks | 7 | 768 |
| `ats` | CV extraction, scoring and rewriting | 18 | 4,020 |
| `dashboard` | User, Enterprise and owner reporting | 4 | 294 |
| `analytics` | Platform-health reporting | 6 | 500 |
| **Total** | | **59** | **6,748** |

Counts cover production Python, HTML, CSS and JavaScript, excluding tests,
migrations and caches.

### What each app does in this project

- **`core`** provides the home page, user feedback and Maya. It supplies Maya
  with approved platform knowledge and limited signed-in user context.
- **`accounts`** manages registration, login, logout, password reset, account
  settings, user profiles and Google/LinkedIn authentication.
- **`subscriptions`** stores plans and subscriptions, checks feature access and
  usage limits, and acts as the central source for customer entitlements.
- **`payments`** creates Stripe Checkout sessions and handles verified webhooks,
  transactions, invoices, refunds and receipts. It activates access only after
  payment verification.
- **`ats`** handles CV uploads and text extraction, job adverts, evidence-based
  scoring, JobRole and ATSResult records, CV and cover-letter drafts, reminders,
  bullet reviews and Enterprise bulk screening.
- **`dashboard`** combines records from accounts, subscriptions, payments and
  ATS into customer, Enterprise and owner views. It is mainly a reporting and
  coordination app and has no models of its own.
- **`analytics`** gives superusers platform-health reports covering usage,
  database status, migrations, payments and provider readiness.

## How the Django apps are wired

**Wiring code:** `config/settings.py` registers every app, `config/urls.py` uses `include()` to connect each app's `urls.py`, and views connect apps internally by importing shared services/models and following model foreign-key relationships in the common database.

```text
Browser -> config/urls.py -> app/urls.py -> app/views.py
        -> services/scoring -> app/models.py -> shared database -> response
```

- `config/settings.py` installs the apps and configures middleware, database and
  external settings.
- `config/urls.py` connects URL prefixes to apps with Django `include()`.
- Each app's `urls.py` connects individual paths to view functions.
- Views call service functions and models. Model foreign keys connect records
  owned by different features; the dashboard reads those shared relationships.

Example: `config/urls.py` sends `/ats/` to `ats/urls.py`; its `analyse/` path
calls `ats.views.analyse_cv`, which calls subscription checks, extraction and
`ats/scoring.py`, then saves `JobRole`, `CV` and `ATSResult` records.

## How Maya works

Maya is built into the `core` app rather than installed as a separate Django
app.

1. `templates/base.html` displays the chat interface.
2. `static/js/main.js` reads the user's text and sends JSON containing
   `question` and bounded `history` to `POST /assistant/` with a CSRF token.
3. `core/urls.py` routes that request to `core.views.assistant_reply`.
4. The view validates the text, selects approved knowledge from
   `core/maya_knowledge.py`, and adds limited account context.
5. If `OLLAMA_BASE_URL` is configured, `call_ollama()` sends the bounded prompt
   to its `/api/chat` endpoint. Otherwise, or if it fails, local
   `fallback_assistant_answer()` produces the reply.
6. Django returns `{"answer": "..."}` as JSON, and JavaScript displays it.

Only a short browser-held history is sent; the response says it is not retained
as a permanent chat record.

## Where CV rewriting gets its data

`ats.views.build_generated_cv()` uses only controlled platform data:

- original CV text extracted from the user's uploaded PDF, DOCX or TXT file;
- the saved job title and job description;
- matched and missing requirements from the ATS result; and
- truthful evidence already present in the CV.

`ats/cv_drafting.py` restructures that evidence into a targeted draft. It must
not invent skills, qualifications or experience. Paid-plan entitlement controls
generation and download. Low-match CVs receive an evidence plan instead of a
cosmetic rewrite.

## How scoring and recommendations work

`ats/scoring.py` validates and normalises the advert, loads matching taxonomy
data, extracts requirements, and compares them with CV evidence. The score
combines skills, requirements, title alignment, keywords, mandatory items,
evidence and document format. Missing mandatory requirements cap the score.

The application guidance in `ats/views.py` is:

| Score | Guidance | Rewrite? |
|---:|---|---|
| **75-100** | Strong alignment; applying may be worthwhile after checking every claim and mandatory requirement | Yes |
| **55-74** | Partial alignment; strengthen truthful evidence before deciding to apply | Yes |
| **0-54** | Significant evidence gap; do not rely on a cosmetic rewrite or apply yet | No; evidence plan only |

The system recommends changes only when they can be supported truthfully. It
does not promise employment or make the hiring decision; the user must verify
the result and decide whether to apply.

## Why it can assess different future jobs without an external LLM

The job advert acts as a live specification. The deterministic Python engine
extracts requirements from each new advert, so it is not limited to a fixed list
of job titles. Database taxonomies can be expanded without redesigning the
engine. This makes scoring private, repeatable and explainable, although unusual
wording or specialist context may still require human review.

## Presentation summary

> MyValidCV's seven Django apps are connected through URL routing, views,
> services, models and one shared database. Maya receives browser JSON and uses
> approved knowledge with either configured Ollama or a local fallback. CV
> rewriting uses the original CV plus ATS evidence, never invented claims. The
> rules-based scorer recommends applying, improving, or building evidence using
> clear thresholds, while leaving the final decision to the user.
