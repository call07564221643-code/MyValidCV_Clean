
# MyValidCV Backend - Presentation Explanation

## 1. Platform structure

MyValidCV is a Django modular monolith: one deployed platform divided into
**seven custom apps**. The apps share one database and communicate through
Python services, model relationships and controlled URL routes.

```text
Browser -> main URL router -> app URL router -> view
        -> service/scoring logic -> model/database -> HTML, JSON or file response
```

The browser never accesses the database directly. Django authenticates the
user, validates input, applies permissions and plan limits, calls the required
business logic, saves the result and returns a response.

## 2. The seven apps and their code size

| App | Main responsibility | Code files | Source lines |
|---|---|---:|---:|
| `core` | Landing pages, feedback and Maya assistant | 7 | 498 |
| `accounts` | Registration, login, profiles and social authentication | 9 | 364 |
| `subscriptions` | Plans, entitlements, usage limits and discounts | 8 | 304 |
| `payments` | Stripe checkout, webhooks, invoices, refunds and receipts | 7 | 768 |
| `ats` | CV extraction, validation, scoring, generation and bulk screening | 18 | 4,020 |
| `dashboard` | Customer, Enterprise and owner reporting views | 4 | 294 |
| `analytics` | Superuser platform-health and commercial reporting | 6 | 500 |
| **Total** | **All seven custom apps** | **59** | **6,748** |

These figures count production `.py`, `.html`, `.css` and `.js` files inside
the seven app folders. They exclude tests, migrations and generated cache files.
They are a repository snapshot and should be recounted as the platform changes.

## 3. How the apps are wired

- `config/settings.py` registers all seven apps and configures the database,
  middleware, templates, authentication, email, Stripe and security settings.
- `config/urls.py` sends each URL group to the responsible app.
- An app's `urls.py` maps a route to a view.
- Views coordinate requests and enforce authentication and permissions.
- Services and scoring modules contain reusable business rules.
- Models define data and relationships in the shared database.
- Migrations safely version database changes.

For example, `/ats/analyse/` is passed from the project router to the ATS app.
The ATS view validates the request, checks the user's subscription allowance,
calls the scoring engine, saves the result and returns the report.

## 4. Job description versus JobRole

The **job description** is the advert text analysed by the scoring engine. It
contains responsibilities, skills, experience and qualifications.

A **JobRole** is the structured database record around that text. It stores the
title, company, deadline, source, owner and description. ATS results, reminders,
generated documents and Enterprise screening batches can therefore remain
linked to the same saved vacancy.

## 5. How ATS supports different and future jobs without an external LLM

The ATS is job-agnostic because the pasted vacancy is its live specification.
It does not need a separate hard-coded scoring function for every profession.
For each check, the local deterministic Python engine:

1. validates that the input resembles a complete job advert;
2. normalises the CV and advert text;
3. loads any matching database taxonomy, skills and qualifications;
4. dynamically extracts relevant requirements and keywords from the new advert;
5. distinguishes mandatory and preferred wording;
6. searches the CV for truthful supporting evidence;
7. scores skills, requirements, title alignment, keywords, mandatory items,
   evidence quality and CV format; and
8. returns matched items, gaps, confidence and recommendations.

This design can process an advert for software, healthcare, aviation, finance,
administration or a newly created future role because unfamiliar requirements
can be extracted directly from its wording. Administrators can also extend the
database taxonomy without changing the scoring architecture. The same input
always follows explainable rules, no CV data needs to be sent to an external
LLM, and mandatory gaps can cap an otherwise misleading score.

This does **not** mean perfect understanding of every job. A rules-based ATS may
miss synonyms, unusual wording, implied experience or specialist context.
Coverage depends on a complete advert, accurate extraction and maintained
taxonomies. The score is decision support for a human, not a hiring decision or
a guarantee of suitability.

## 6. One end-to-end example

Sarah uploads her CV and pastes a Software Developer advert requiring Python,
Django, PostgreSQL and three years of experience.

1. The browser posts the form to `/ats/analyse/`.
2. The ATS view authenticates Sarah, validates both texts and checks her plan.
3. It saves a JobRole containing the advert and its structured details.
4. The local scoring engine extracts the advert's requirements and checks the
   CV for evidence. It might verify Python and Django but flag PostgreSQL and
   the required experience as unsupported.
5. An ATSResult stores the score, evidence, gaps and recommendation, linked to
   Sarah's CV and JobRole.
6. Sarah sees the report, while the dashboard can later show the same linked
   result in her history and use it for reminders or document generation.

## 7. Presentation summary

> MyValidCV has seven connected Django apps and 6,748 lines of production app
> code in this measured snapshot. Its ATS does not depend on an external LLM:
> it treats each job advert as a live specification, extracts its requirements,
> checks the CV for evidence and produces a deterministic, explainable score.
> This lets the same architecture assess current and future roles, while clear
> confidence limits and human review prevent the score becoming a hiring verdict.
