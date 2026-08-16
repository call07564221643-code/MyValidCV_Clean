# MyValidCV Agile Operating Model

MyValidCV should be managed as a lean micro-SaaS: small releases, visible work,
fast feedback and constant focus on the shortest path from visitor anxiety to a
validated CV report.

## Product North Star

The fastest and simplest way to know if your CV is ready for a specific job.

The core journey must stay protected:

1. Register or log in.
2. Upload a CV.
3. Add a job description, vacancy URL or advert.
4. Click Validate.
5. Receive a clear report, suggested CV wording and cover-letter support.

## Delivery Cadence

Use one-week sprints until the MVP is stable.

- Monday: choose sprint goal and pull only the highest-value work into `Doing`.
- Daily: review blockers, live errors, payments, signups and validation success.
- Thursday: test the release candidate on local and Heroku.
- Friday: deploy, record results, move completed items to `Done`.

For urgent production defects, pause feature work and use a hotfix lane.

## MVP Delivery Sprint: 20-21 July 2026

The final MVP increment is a two-day delivery sprint ending on **21 July 2026**.
No new product features enter this sprint. Work is pulled in this order:

1. Validate the full user journey and account boundaries.
2. Confirm ATS scoring and report readability.
3. Confirm live checkout, receipt and subscription activation.
4. Confirm legal/trust content and production performance evidence.
5. Capture screenshots, run the demo script and finish the presentation/README.

The release candidate is frozen after the final critical fix. PageSpeed evidence
or an external-provider check that cannot be completed must be recorded as a
known delivery exception, not silently marked `Done`.

### 21 July Definition Of Delivery

- All Must Have release gates have an evidence note.
- There are no unresolved critical defects in the core journey.
- Free, Plus, Enterprise and owner access boundaries are verified.
- Login accepts username or email and has a useful failure state.
- Owner reporting remains separate from the Enterprise dashboard.
- The live application URL, screenshots and demo script are ready to present.
- Deferred work is explicitly moved to the post-delivery backlog.

## Roles

- Product Owner: decides priority, pricing, user promise and launch scope.
- Tech Lead: protects architecture, security, deployment and data integrity.
- UX Lead: keeps the journey simple and emotionally clear.
- QA Owner: tests authentication, payments, CV upload, ATS report and dashboards.
- Website Owner: reviews `/owner/`, refunds, subscriptions, reports and health.

One person can hold several roles, but each decision still needs an owner.

## Definition Of Ready

A task can enter `Doing` only when it has:

- A user or business outcome.
- A clear page, model, view, payment flow or report area affected.
- Acceptance criteria.
- Test steps.
- A rollback or low-risk release path.

## Definition Of Done

A task is done only when:

- The core journey still works.
- Normal users, enterprise users and superusers see only what they should see.
- `python manage.py check` passes.
- Migrations are created when models change.
- Heroku release succeeds.
- The user-facing result is checked in the browser.
- The Kanban board is updated.

## Release Gates

Every production release should check:

- Landing page loads and primary CTA works.
- Register, login, logout and account page work.
- Dashboard works for free, plus, enterprise and superuser.
- CV upload validates the document as a CV.
- ATS analysis creates a result for the logged-in user only.
- Pricing and Stripe Checkout work.
- `/owner/` is accessible only to superusers.
- No new 500 errors appear in Heroku logs.

## Metrics

Track these weekly:

- Visitor to signup conversion.
- Signup to first validation conversion.
- CV upload failure rate.
- Validation completion rate.
- Free to Plus conversion.
- Payment success rate.
- Refund requests and reasons.
- Average ATS report usefulness feedback.
- Owner console health issues.

## Working Agreement

Prefer small, complete improvements over large unfinished redesigns. MyValidCV
wins by being calm, fast and clear, not by having many features.
