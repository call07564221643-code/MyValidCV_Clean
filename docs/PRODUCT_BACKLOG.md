# MyValidCV Product Backlog

Priorities use:

- `Critical`: required to protect the live product or core journey.
- `High`: improves conversion, retention or paid plan value.
- `Medium`: useful after the MVP is stable.
- `Low`: polish or future expansion.

## Critical

### Core Journey Reliability

As a job seeker, I want to upload my CV, add a job and validate it without page
confusion so that I can get a report quickly.

Acceptance criteria:

- CV upload accepts PDF/DOCX and rejects weak/non-CV documents with a clear reason.
- Analysis always belongs to the logged-in user.
- Result page opens after validation.
- Dashboard shows latest CVs and reports.

### Payment Reliability

As a Plus user, I want a simple Pay Now checkout and receipt so that I trust the
subscription is active.

Acceptance criteria:

- Stripe Checkout opens from Plus plan.
- Success page confirms payment, plan and next renewal.
- Invoice and payment transaction are visible in `/owner/`.
- Failed payments do not silently upgrade users.

### Owner Separation

As the website owner, I want private website controls outside customer dashboards
so that sensitive business data is protected.

Acceptance criteria:

- `/owner/` is superuser-only.
- `/dashboard/` contains only customer or enterprise work.
- Normal users receive 403 or login redirect for owner-only pages.

## High

### Landing Page Emotional Conversion

As a cold visitor, I want to feel that MyValidCV solves my application anxiety so
that I am willing to create an account.

Acceptance criteria:

- Hero explains the product in one sentence.
- Carousel shows pain, relief and action.
- Primary CTA is visible without scrolling.
- PageSpeed and mobile layout stay healthy.

### Better Report Interpretation

As a job seeker, I want to know why my CV is weak, not only the percentage score,
so that I can fix the most important problem.

Acceptance criteria:

- Report explains recruiter risk.
- Must-have gaps are separated from nice-to-have gaps.
- Suggested CV wording uses only evidence from the CV.
- Cover letter uses matched evidence from the report.

### Enterprise Bulk Screening

As an enterprise user, I want to upload multiple CVs against one role so that I
can shortlist candidates faster.

Acceptance criteria:

- Bulk upload is limited by plan allowance.
- Each candidate gets a ranked match result.
- CSV export works.
- Enterprise users cannot see owner financial data.

## Medium

### Guided Onboarding

As a new user, I want lightweight guidance after signup so that I know exactly
what to do first.

Acceptance criteria:

- Empty dashboard shows one clear next action.
- First validation flow explains CV, job input and limits.
- No modal blocks the main action.

### Usage And Plan Messaging

As a free or Plus user, I want to understand my remaining allowance so that I know
when to upgrade.

Acceptance criteria:

- Dashboard shows remaining uses without bulky copy.
- Upgrade prompts appear only when relevant.
- Limits are enforced server-side.

### Website Health Reporting

As the owner, I want website health and financial signals so that I can prevent
issues before they affect users.

Acceptance criteria:

- Health report shows errors, payment success, usage, revenue and cost inputs.
- Financial assumptions can be edited by superuser.
- Reports are visible only to owner/superuser.

## Low

### Advanced CV Formats

As a Plus user, I may want alternative CV formats so that I can choose the most
appropriate presentation.

Acceptance criteria:

- Suggested formats remain truthful.
- User can preview before download.
- The original CV evidence is preserved.

### More Social Login Providers

As a user, I may want to register through Facebook or another provider so that
signup is faster.

Acceptance criteria:

- Provider can be enabled by owner configuration.
- OAuth secrets are stored only in environment variables.
- Existing email accounts are not duplicated.

## Final Release User Story Set

These are the final, project-closing stories for the current release window. Each
story is intentionally small, testable and aligned to the protected core journey.

### 1. Core journey completion

Priority: Critical

As a job seeker, I want to upload my CV, add a job and validate it without
confusion so that I can quickly receive a useful ATS report.

Acceptance criteria:

- CV upload accepts supported formats and rejects weak/non-CV documents clearly.
- User sees a stable progress flow from upload through validation to result.
- The result belongs only to the logged-in user.
- The dashboard shows the latest CV and report status.

### 2. Trust in payment and subscription flow

Priority: Critical

As a Plus user, I want a clear payment flow and confirmation that my subscription
is active so that I trust the purchase and can continue using the service.

Acceptance criteria:

- Stripe Checkout works end-to-end.
- Payment confirmation is visible after success.
- Subscription state is reflected in the account and plan status.
- Failed payments do not silently grant access.

### 3. Simple onboarding and first action guidance

Priority: High

As a new user, I want to know what to do next after signing up so that I can
start using the product without confusion.

Acceptance criteria:

- Empty or low-activity dashboard shows a clear next action.
- The first-time flow explains CV upload, job input and validation.
- Guidance is concise and useful, not bloated.

### 4. Better ATS explanation and actionability

Priority: High

As a job seeker, I want to understand what is going wrong in my CV and what to
fix next so that I can improve my chances for the target role.

Acceptance criteria:

- Report separates must-have gaps from nice-to-have gaps.
- Suggestions are anchored in actual CV evidence.
- Report language is understandable to users without recruiter jargon.

### 5. Clear plan and usage limits

Priority: High

As a user, I want to understand my plan allowance and remaining usage so that I
can decide whether to upgrade or continue using the service.

Acceptance criteria:

- Account or dashboard shows plan status and remaining allowance clearly.
- Upgrade prompts only appear when relevant.
- Limits are enforced on the server side, not only in the UI.

### 6. Protected owner and enterprise boundaries

Priority: Critical

As the platform owner, I want customer, enterprise and owner views to remain
separate so that sensitive business data stays protected.

Acceptance criteria:

- Owner pages remain visible only to superusers.
- Enterprise-specific content is not shown to standard users.
- Access control remains enforced consistently.

### 7. Support confidence and trust signals

Priority: Medium

As a user, I want to understand the service limits, support route and privacy
position so that I can trust the platform before and after use.

Acceptance criteria:

- Key policy and support information is easy to find.
- Service limitations are clearly communicated.
- Trust, privacy, and support language matches actual product capability.

## Final Sprint Rule

Do not pull broad feature work into the final sprint once the core journey, trust,
subscription flow, and owner boundaries are stable. The goal is to close with a
calm, trusted release, not a large unvalidated feature expansion.
