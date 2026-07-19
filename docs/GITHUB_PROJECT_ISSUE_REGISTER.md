# MyValidCV GitHub Project Issue Register

Use this file to create the GitHub Issues that populate Project 7.

Milestone for all MVP/review items:

```text
MVP v1.0
```

Recommended Project fields:

- Status
- Estimate
- Sprint / Iteration
- Labels
- Milestone

## Summary Counts

| Status | Count | Meaning |
| --- | ---: | --- |
| Done | 18 | MVP work already completed during project build |
| In review | 5 | Needs final testing, score capture or quality review |
| Ready | 5 | Final submission/presentation work ready to start |
| Backlog | 2 | Valuable improvements after MVP |
| Total | 30 | Full Agile issue set |

## Done

### 1. Landing page and emotional carousel

Status: `Done`  
Estimate: `3`  
Labels: `Must Have`, `ux`  
Sprint: Completed sprint  

As a cold visitor, I want the landing page to explain the pain of CV uncertainty so that I feel MyValidCV can help me before I apply.

Acceptance criteria:

- Landing page explains CV validation clearly.
- Emotional carousel addresses application anxiety, recruiter view and relief.
- Main CTA points to signup or dashboard.
- Page remains responsive.

### 2. Register, login, logout and account page

Status: `Done`  
Estimate: `5`  
Labels: `Must Have`  
Sprint: Completed sprint  

As a user, I want to register, log in, log out and manage my account so that I can safely use saved CVs and reports.

Acceptance criteria:

- Register works.
- Login works.
- Logout works.
- `/settings/` is labelled as Account.
- UserProfile is created automatically.

### 3. Google and LinkedIn social login setup

Status: `Done`  
Estimate: `3`  
Labels: `Should Have`  
Sprint: Completed sprint  

As a user, I want to sign up with Google or LinkedIn so that account creation is faster.

Acceptance criteria:

- Social login buttons appear in auth pages.
- Provider settings exist in Django.
- OAuth secrets are stored in environment variables.

### 4. Dashboard for normal users

Status: `Done`  
Estimate: `5`  
Labels: `Must Have`  
Sprint: Completed sprint  

As a job seeker, I want a dashboard showing my CVs, reports and usage so that I can continue my job search quickly.

Acceptance criteria:

- Dashboard loads for normal users.
- Saved CVs are visible.
- Recent reports are visible.
- Usage allowance is shown without clutter.

### 5. Enterprise dashboard and bulk CV reports

Status: `Done`  
Estimate: `8`  
Labels: `Must Have`  
Sprint: Completed sprint  

As an enterprise user, I want bulk CV screening against a role so that I can shortlist candidates faster.

Acceptance criteria:

- Enterprise bulk upload route exists.
- Candidate results are ranked.
- CSV export is available.
- Enterprise users do not see owner financial data.

### 6. Owner control centre separated at /owner/

Status: `Done`  
Estimate: `3`  
Labels: `Must Have`  
Sprint: Completed sprint  

As the website owner, I want website controls separated from customer dashboards so that sensitive controls are protected.

Acceptance criteria:

- `/owner/` exists.
- Superusers can access it.
- Normal users cannot access it.
- `/dashboard/owner/` redirects to `/owner/`.

### 7. CV upload and CV quality validation

Status: `Done`  
Estimate: `5`  
Labels: `Must Have`  
Sprint: Completed sprint  

As a user, I want to upload a real CV and be warned if the document is not strong enough as a CV so that analysis quality improves.

Acceptance criteria:

- PDF/DOCX upload works.
- CV ownership is linked to the logged-in user.
- Weak/non-CV documents produce a clear warning.

### 8. ATS analysis and result page

Status: `Done`  
Estimate: `8`  
Labels: `Must Have`  
Sprint: Completed sprint  

As a user, I want to compare my CV with a job role so that I can see my match and what to improve.

Acceptance criteria:

- Job text, URL or advert input is supported.
- ATSResult is saved to the logged-in user.
- Result page opens after validation.
- Matched and missing skills are visible.

### 9. Suggested CV draft and cover letter output

Status: `Done`  
Estimate: `8`  
Labels: `Should Have`  
Sprint: Completed sprint  

As a Plus user, I want suggested CV wording and cover-letter support so that I can apply with stronger relevant evidence.

Acceptance criteria:

- Suggested CV section appears on report page.
- Cover letter uses CV/job matched evidence.
- Wording avoids invented experience.

### 10. Pricing page with Free, Plus and Enterprise plans

Status: `Done`  
Estimate: `5`  
Labels: `Must Have`  
Sprint: Completed sprint  

As a visitor, I want clear pricing so that I can choose the right plan without confusion.

Acceptance criteria:

- Free, Plus and Enterprise plans are shown.
- Features and limits are clear.
- Pay Now uses provider-neutral wording.

### 11. Stripe checkout and receipt flow

Status: `Done`  
Estimate: `8`  
Labels: `Must Have`  
Sprint: Completed sprint  

As a paid user, I want secure checkout and a receipt so that I trust my subscription is active.

Acceptance criteria:

- Stripe Checkout opens.
- Success page confirms payment.
- Subscription is updated.
- Receipt and transaction records are available.

### 12. PostgreSQL and Heroku deployment

Status: `Done`  
Estimate: `8`  
Labels: `Must Have`  
Sprint: Completed sprint  

As the website owner, I want the project deployed on Heroku with PostgreSQL so that the SaaS is live and persistent.

Acceptance criteria:

- Heroku app is live.
- PostgreSQL is connected through `DATABASE_URL`.
- Release command runs migrations and seed tasks.

### 13. Static files, HTTPS and PageSpeed readiness

Status: `Done`  
Estimate: `3`  
Labels: `Should Have`  
Sprint: Completed sprint  

As a visitor, I want the site to load quickly and securely so that I trust the platform.

Acceptance criteria:

- Static files are collected.
- Hashed static files are long-cache immutable.
- HTTPS redirect and HSTS are active.
- Scripts are deferred.

### 14. Dark and light mode across website

Status: `Done`  
Estimate: `3`  
Labels: `Could Have`, `ux`  
Sprint: Completed sprint  

As a user, I want light and dark modes to apply across the full site so that the interface remains comfortable and readable.

Acceptance criteria:

- Toggle is icon-only.
- Theme applies beyond navbar.
- Buttons remain readable in dark mode.

### 15. Admin branding and owner access rules

Status: `Done`  
Estimate: `3`  
Labels: `Should Have`  
Sprint: Completed sprint  

As the owner, I want admin branding and access rules to match MyValidCV so that management feels professional.

Acceptance criteria:

- Admin header uses MyValidCV branding.
- Owner-only data is restricted.
- Superuser access is preserved.

### 16. Demo data and seeded plans/taxonomy

Status: `Done`  
Estimate: `5`  
Labels: `Should Have`  
Sprint: Completed sprint  

As the owner, I want seeded demo users, plans and taxonomy so that the database can demonstrate platform behaviour.

Acceptance criteria:

- Plans are seeded.
- Demo users can be created.
- Taxonomy seed command runs during release.

### 17. Agile documentation, backlog and Kanban documents

Status: `Done`  
Estimate: `2`  
Labels: `Must Have`  
Sprint: Completed sprint  

As the project owner, I want Agile documentation so that the project is managed professionally.

Acceptance criteria:

- Agile operating model exists.
- UX playbook exists.
- Product backlog exists.
- Markdown Kanban board exists.

### 18. GitHub issue template and project setup guide

Status: `Done`  
Estimate: `2`  
Labels: `Must Have`  
Sprint: Completed sprint  

As the project owner, I want GitHub issue templates and setup instructions so that Project 7 can be populated correctly.

Acceptance criteria:

- User Story issue template exists.
- GitHub Project setup guide exists.
- README links to setup guide.

## In Review

### 19. Final UX smoke test

Status: `In review`  
Estimate: `3`  
Labels: `review`, `Must Have`  
Sprint: Current iteration  

As the owner, I want a full UX smoke test so that final issues are found before presentation.

Acceptance criteria:

- Home, register, login, dashboard, validate, result, pricing, payment and owner pages are checked.
- Any 500 error becomes a hotfix.
- Mobile and desktop are reviewed.

### 20. Manual Google PageSpeed test

Status: `In review`  
Estimate: `2`  
Labels: `review`, `Should Have`  
Sprint: Current iteration  

As the owner, I want a manual PageSpeed score so that performance claims are evidence-based.

Acceptance criteria:

- `pagespeed.web.dev` is run on the live homepage.
- Mobile and desktop scores are recorded.
- Any failing Core Web Vital becomes a backlog issue.

### 21. Live Stripe payment confirmation test

Status: `In review`  
Estimate: `3`  
Labels: `review`, `Must Have`  
Sprint: Current iteration  

As the owner, I want the payment flow checked live so that paid users can subscribe safely.

Acceptance criteria:

- Plus checkout works.
- Success page displays receipt.
- Subscription is active after payment.
- Heroku logs show no payment 500 error.

### 22. ATS scoring quality review

Status: `In review`  
Estimate: `5`  
Labels: `review`, `Should Have`  
Sprint: Current iteration  

As a user, I want ATS scoring to distinguish unrelated roles so that the report feels credible.

Acceptance criteria:

- Same-industry CV/job gives sensible score.
- Unrelated CV/job does not score unrealistically high.
- Must-have requirements have stronger weighting.

### 23. Report page readability and CV wording review

Status: `In review`  
Estimate: `5`  
Labels: `review`, `ux`  
Sprint: Current iteration  

As a user, I want the report and suggested wording to be compact, readable and useful.

Acceptance criteria:

- Recruiter risk is visible.
- Suggested CV wording uses real evidence.
- Cover letter summary is stronger and role-specific.

## Ready

### 24. Final project presentation

Status: `Ready`  
Estimate: `5`  
Labels: `presentation`, `Must Have`  
Sprint: Next iteration  

As the project owner, I want a final presentation so that I can demonstrate MyValidCV professionally.

Acceptance criteria:

- Product story is clear.
- Architecture summary is included.
- Demo journey is included.
- Agile/Kanban evidence is included.

### 25. Demo script and screenshots

Status: `Ready`  
Estimate: `3`  
Labels: `presentation`, `Should Have`  
Sprint: Next iteration  

As the presenter, I want a demo script and screenshots so that the presentation runs smoothly.

Acceptance criteria:

- Screenshots cover landing, dashboard, validation, report, pricing and owner.
- Demo script follows the core journey.

### 26. README final polish

Status: `Ready`  
Estimate: `2`  
Labels: `Could Have`  
Sprint: Next iteration  

As a reviewer, I want a polished README so that setup, product scope and deployment are easy to understand.

Acceptance criteria:

- README links are current.
- Heroku instructions are clear.
- Agile docs are referenced.

### 27. Terms, privacy and refund content pages

Status: `Ready`  
Estimate: `3`  
Labels: `Should Have`  
Sprint: Next iteration  

As a user, I want clear terms, privacy and refund information so that I can trust the service.

Acceptance criteria:

- Footer links lead to content pages or clear sections.
- Refund terms explain payment expectations.
- Data use is explained in plain language.

### 28. Owner promo code workflow guide

Status: `Ready`  
Estimate: `3`  
Labels: `Should Have`  
Sprint: Next iteration  

As the owner, I want a clear promo-code workflow so that discounts can be managed safely.

Acceptance criteria:

- Owner can find discount-code admin.
- Active dates, percentage and usage limits are explained.
- Promo codes do not bypass payment records.

## Backlog

### 29. User feedback after ATS report

Status: `Backlog`  
Estimate: `3`  
Labels: `Could Have`  
Sprint: Backlog  

As the owner, I want report feedback so that I can learn whether users find the report useful.

Acceptance criteria:

- User can rate report usefulness.
- Feedback belongs to user/report.
- Owner can review feedback.

### 30. Improve ATS taxonomy coverage

Status: `Backlog`  
Estimate: `8`  
Labels: `Should Have`  
Sprint: Backlog  

As the owner, I want broader role taxonomy so that analysis works across more industries.

Acceptance criteria:

- More role families are seeded.
- Skills and qualifications are structured.
- Matching logic uses taxonomy without overfitting to one job.

