# MyValidCV GitHub Project User Stories

Use this register to create GitHub Issues for Project 7.

For each item:

1. Go to `Issues`.
2. Click `New issue`.
3. Choose `User Story`.
4. Copy the title.
5. Copy the full issue body.
6. Add the issue to Project 7.
7. Set Status, Estimate, Sprint, Labels and Milestone.

Milestone for MVP items:

```text
MVP v1.0
```

## Board Counts

| Status | Count |
| --- | ---: |
| Done | 18 |
| In review | 5 |
| Ready | 5 |
| Backlog | 2 |
| Total | 30 |

---

## 1. User Story: Landing Page And Emotional Carousel

Status: `Done`
Labels: `Must Have`, `ux`
Story points: `3`
Sprint: `Sprint 1`

## User Story

As a **cold visitor**
I want **the landing page to explain my CV uncertainty and show a simple path to validation**
So that **I feel relief and decide to create an account**

## User Experience Reason

This removes the fear of applying blindly and the confusion of not knowing why a CV is ignored. It turns the visitor's emotional pain into a clear action: start a validation.

## Acceptance Criteria

- [ ] The visitor can understand MyValidCV in a few seconds.
- [ ] The primary CTA leads to signup or dashboard.
- [ ] The emotional carousel explains pain, recruiter view and relief.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Must Have

## Story Points

3

## Sprint

Sprint 1

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 2. User Story: Register Login Logout And Account Page

Status: `Done`
Labels: `Must Have`
Story points: `5`
Sprint: `Sprint 1`

## User Story

As a **job seeker**
I want **to register, log in, log out and manage my account**
So that **my CVs, reports and plan information are saved securely**

## User Experience Reason

This removes the anxiety of losing reports or having to repeat the same work. It also gives the user confidence that the platform has a real account area.

## Acceptance Criteria

- [ ] Users can register.
- [ ] Users can log in and log out.
- [ ] Account page is labelled clearly as Account.
- [ ] UserProfile is created automatically.
- [ ] The wrong user/account type cannot access restricted data.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Must Have

## Story Points

5

## Sprint

Sprint 1

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 3. User Story: Google And LinkedIn Social Login Setup

Status: `Done`
Labels: `Should Have`
Story points: `3`
Sprint: `Sprint 1`

## User Story

As a **new user**
I want **to register with Google or LinkedIn**
So that **I can start faster without creating another password**

## User Experience Reason

This reduces signup friction and helps cold visitors move faster from interest to first validation.

## Acceptance Criteria

- [ ] Google login button appears on auth pages.
- [ ] LinkedIn login button appears on auth pages.
- [ ] OAuth settings use environment variables.
- [ ] Manual email registration still works.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Should Have

## Story Points

3

## Sprint

Sprint 1

## Test Notes

- [x] Local check completed.
- [ ] Heroku OAuth provider test completed.
- [ ] Browser/UX smoke test completed.

---

## 4. User Story: Dashboard For Normal Users

Status: `Done`
Labels: `Must Have`
Story points: `5`
Sprint: `Sprint 1`

## User Story

As a **normal user**
I want **a dashboard showing my CVs, reports, usage and next action**
So that **I can continue my job search without confusion**

## User Experience Reason

This removes the frustration of searching across pages after login. The dashboard becomes the user's calm workspace.

## Acceptance Criteria

- [ ] Normal users can open `/dashboard/`.
- [ ] Saved CVs are visible.
- [ ] Recent reports are visible.
- [ ] Usage and renewal information is readable.
- [ ] The wrong user/account type cannot access restricted data.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Must Have

## Story Points

5

## Sprint

Sprint 1

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 5. User Story: Enterprise Dashboard And Bulk CV Reports

Status: `Done`
Labels: `Must Have`
Story points: `8`
Sprint: `Sprint 2`

## User Story

As an **enterprise recruiter**
I want **to upload multiple CVs against one job role and receive ranked reports**
So that **I can shortlist candidates faster**

## User Experience Reason

This removes manual screening pressure and helps recruiters compare candidates with consistent criteria.

## Acceptance Criteria

- [ ] Enterprise users can access bulk analysis.
- [ ] Bulk results are ranked.
- [ ] CSV export works.
- [ ] Enterprise users cannot see owner financial data.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Must Have

## Story Points

8

## Sprint

Sprint 2

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 6. User Story: Owner Control Centre Separated At /owner/

Status: `Done`
Labels: `Must Have`
Story points: `3`
Sprint: `Sprint 2`

## User Story

As the **website owner**
I want **a separate owner control centre at `/owner/`**
So that **business, payment and user-management controls are not mixed with customer dashboards**

## User Experience Reason

This removes confusion between enterprise users and the website owner. It also protects sensitive management data.

## Acceptance Criteria

- [ ] Superusers can access `/owner/`.
- [ ] Normal users cannot access `/owner/`.
- [ ] `/dashboard/owner/` redirects to `/owner/`.
- [ ] The owner page links to users, payments, refunds, plans and reports.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Must Have

## Story Points

3

## Sprint

Sprint 2

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 7. User Story: CV Upload And CV Quality Validation

Status: `Done`
Labels: `Must Have`
Story points: `5`
Sprint: `Sprint 2`

## User Story

As a **job seeker**
I want **to upload my CV and know if the document is strong enough for analysis**
So that **I do not receive a misleading ATS report from a weak or wrong document**

## User Experience Reason

This removes the disappointment of uploading the wrong document and receiving useless results.

## Acceptance Criteria

- [ ] User can upload PDF or DOCX CV.
- [ ] Uploaded CV belongs to the logged-in user.
- [ ] Weak or non-CV documents produce a clear warning.
- [ ] The wrong user/account type cannot access restricted data.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Must Have

## Story Points

5

## Sprint

Sprint 2

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 8. User Story: ATS Analysis And Result Page

Status: `Done`
Labels: `Must Have`
Story points: `8`
Sprint: `Sprint 2`

## User Story

As a **job seeker**
I want **to compare my CV with a job description, URL or advert**
So that **I can understand match quality before applying**

## User Experience Reason

This removes guesswork and helps users understand what recruiters and ATS systems may notice.

## Acceptance Criteria

- [ ] User can add job text, URL or advert.
- [ ] ATSResult is saved to the logged-in user.
- [ ] Result page opens after validation.
- [ ] Matched and missing skills are visible.
- [ ] The wrong user/account type cannot access restricted data.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Must Have

## Story Points

8

## Sprint

Sprint 2

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 9. User Story: Suggested CV Draft And Cover Letter Output

Status: `Done`
Labels: `Should Have`
Story points: `8`
Sprint: `Sprint 3`

## User Story

As a **Plus user**
I want **suggested CV wording and a cover letter draft based on matched evidence**
So that **I can apply with clearer role-specific wording**

## User Experience Reason

This removes the stress of rewriting from scratch, while keeping the user honest about what evidence is real.

## Acceptance Criteria

- [ ] Suggested CV wording appears on the report page.
- [ ] Cover letter uses matched CV and job evidence.
- [ ] Red/yellow/green guidance is explained.
- [ ] The output avoids invented experience.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Should Have

## Story Points

8

## Sprint

Sprint 3

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 10. User Story: Pricing Page With Free Plus And Enterprise Plans

Status: `Done`
Labels: `Must Have`
Story points: `5`
Sprint: `Sprint 3`

## User Story

As a **visitor**
I want **clear Free, Plus and Enterprise pricing**
So that **I can choose a plan without confusion**

## User Experience Reason

This removes hesitation caused by unclear pricing, provider names or repeated feature copy.

## Acceptance Criteria

- [ ] Free, Plus and Enterprise are shown.
- [ ] Plan limits are clear.
- [ ] Pay button is provider-neutral.
- [ ] Enterprise is positioned for teams.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Must Have

## Story Points

5

## Sprint

Sprint 3

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 11. User Story: Stripe Checkout And Receipt Flow

Status: `Done`
Labels: `Must Have`
Story points: `8`
Sprint: `Sprint 3`

## User Story

As a **paid user**
I want **secure checkout and a receipt confirmation**
So that **I trust my subscription is active**

## User Experience Reason

This removes payment anxiety and reassures users that card details are handled securely.

## Acceptance Criteria

- [ ] Plus checkout opens through Stripe.
- [ ] Success page confirms payment.
- [ ] Subscription status is updated.
- [ ] Receipt and transaction records exist.
- [ ] The wrong user/account type cannot access restricted data.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Must Have

## Story Points

8

## Sprint

Sprint 3

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Final live payment smoke test pending.

---

## 12. User Story: PostgreSQL And Heroku Deployment

Status: `Done`
Labels: `Must Have`
Story points: `8`
Sprint: `Sprint 3`

## User Story

As the **website owner**
I want **the SaaS deployed on Heroku with PostgreSQL**
So that **the project is live and data persists**

## User Experience Reason

This removes the risk of local-only work and allows real users, payment testing and owner review.

## Acceptance Criteria

- [ ] Heroku app is live.
- [ ] PostgreSQL is connected.
- [ ] Release command runs migrations.
- [ ] Plan and taxonomy seed commands run.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Must Have

## Story Points

8

## Sprint

Sprint 3

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [x] Browser/UX smoke test completed.

---

## 13. User Story: Static Files HTTPS And PageSpeed Readiness

Status: `Done`
Labels: `Should Have`
Story points: `3`
Sprint: `Sprint 4`

## User Story

As a **visitor**
I want **the website to load securely and quickly**
So that **I trust the platform before uploading my CV**

## User Experience Reason

This removes distrust caused by slow pages, insecure browser warnings or broken static assets.

## Acceptance Criteria

- [ ] HTTP redirects to HTTPS.
- [ ] HSTS is present.
- [ ] Static assets are hashed and compressed.
- [ ] Scripts are deferred.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Should Have

## Story Points

3

## Sprint

Sprint 4

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Official PageSpeed manual score pending.

---

## 14. User Story: Dark And Light Mode Across Website

Status: `Done`
Labels: `Could Have`, `ux`
Story points: `3`
Sprint: `Sprint 4`

## User Story

As a **user**
I want **light and dark mode to apply across the whole site**
So that **the website remains comfortable and readable**

## User Experience Reason

This removes visual discomfort and prevents unreadable buttons in dark mode.

## Acceptance Criteria

- [ ] Theme toggle is icon-only.
- [ ] Theme applies beyond the navbar.
- [ ] Buttons remain readable in dark mode.
- [ ] The page is readable on mobile and desktop.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Could Have

## Story Points

3

## Sprint

Sprint 4

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 15. User Story: Admin Branding And Owner Access Rules

Status: `Done`
Labels: `Should Have`
Story points: `3`
Sprint: `Sprint 4`

## User Story

As the **website owner**
I want **admin and owner areas branded and restricted correctly**
So that **management feels professional and protected**

## User Experience Reason

This removes the confusion of Django default branding and reduces risk of exposing sensitive controls.

## Acceptance Criteria

- [ ] Admin uses MyValidCV branding.
- [ ] Owner-only data is restricted.
- [ ] Superuser access works.
- [ ] Normal users cannot access owner controls.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Should Have

## Story Points

3

## Sprint

Sprint 4

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 16. User Story: Demo Data And Seeded Plans Taxonomy

Status: `Done`
Labels: `Should Have`
Story points: `5`
Sprint: `Sprint 4`

## User Story

As the **website owner**
I want **demo data, plans and taxonomy seeded**
So that **the product can demonstrate realistic usage and reports**

## User Experience Reason

This removes empty-dashboard anxiety during demos and makes the product easier to evaluate.

## Acceptance Criteria

- [ ] Plans are seeded.
- [ ] Taxonomy is seeded.
- [ ] Demo data command exists.
- [ ] Release command synchronizes key records.
- [ ] The happy path and one failure path are tested.

## MoSCoW Priority

Should Have

## Story Points

5

## Sprint

Sprint 4

## Test Notes

- [x] Local check completed.
- [x] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 17. User Story: Agile Documentation Backlog And Kanban Documents

Status: `Done`
Labels: `Must Have`
Story points: `2`
Sprint: `Sprint 4`

## User Story

As the **project owner**
I want **Agile documentation, backlog and Kanban files**
So that **the development process is visible and professional**

## User Experience Reason

This removes assessment uncertainty and shows that the SaaS was managed with a real product workflow.

## Acceptance Criteria

- [ ] Agile operating model exists.
- [ ] UX playbook exists.
- [ ] Product backlog exists.
- [ ] Kanban board exists.
- [ ] README links to the documents.

## MoSCoW Priority

Must Have

## Story Points

2

## Sprint

Sprint 4

## Test Notes

- [x] Local check completed.
- [x] Heroku check not required.
- [x] Browser/GitHub review completed.

---

## 18. User Story: GitHub Issue Template And Project Setup Guide

Status: `Done`
Labels: `Must Have`
Story points: `2`
Sprint: `Sprint 4`

## User Story

As the **project owner**
I want **GitHub issue templates and setup guidance**
So that **Project 7 can be populated as a real Agile board**

## User Experience Reason

This removes confusion about why markdown files do not automatically appear as GitHub Project cards.

## Acceptance Criteria

- [ ] User Story issue template exists.
- [ ] Project setup guide exists.
- [ ] Issue register exists.
- [ ] README links to setup documents.

## MoSCoW Priority

Must Have

## Story Points

2

## Sprint

Sprint 4

## Test Notes

- [x] Local check completed.
- [x] Heroku check not required.
- [x] Browser/GitHub review completed.

---

## 19. User Story: Final UX Smoke Test

Status: `In review`
Labels: `review`, `Must Have`
Story points: `3`
Sprint: `Current iteration`

## User Story

As the **project owner**
I want **a final UX smoke test across the full platform**
So that **I can find any final issue before presentation**

## User Experience Reason

This removes the risk of discovering broken pages during demo or assessment.

## Acceptance Criteria

- [ ] Home page tested.
- [ ] Register/login/logout tested.
- [ ] Dashboard tested.
- [ ] Validate CV and result page tested.
- [ ] Pricing and payment tested.
- [ ] Owner console tested.
- [ ] Mobile and desktop reviewed.

## MoSCoW Priority

Must Have

## Story Points

3

## Sprint

Current iteration

## Test Notes

- [ ] Local check completed.
- [ ] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 20. User Story: Manual Google PageSpeed Test

Status: `In review`
Labels: `review`, `Should Have`
Story points: `2`
Sprint: `Current iteration`

## User Story

As the **project owner**
I want **a manual Google PageSpeed test**
So that **performance claims are supported by evidence**

## User Experience Reason

This removes uncertainty about whether the site feels fast enough for first-time visitors.

## Acceptance Criteria

- [ ] `pagespeed.web.dev` is run on the live homepage.
- [ ] Mobile score is recorded.
- [ ] Desktop score is recorded.
- [ ] Any failing Core Web Vital becomes a backlog issue.

## MoSCoW Priority

Should Have

## Story Points

2

## Sprint

Current iteration

## Test Notes

- [ ] Local check not required.
- [ ] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 21. User Story: Live Stripe Payment Confirmation Test

Status: `In review`
Labels: `review`, `Must Have`
Story points: `3`
Sprint: `Current iteration`

## User Story

As the **website owner**
I want **the live Stripe payment flow tested end to end**
So that **paid users can subscribe without errors**

## User Experience Reason

This removes payment anxiety and prevents users from losing trust at checkout.

## Acceptance Criteria

- [ ] Plus checkout opens.
- [ ] Test payment succeeds.
- [ ] Success page shows receipt.
- [ ] User plan updates.
- [ ] Heroku logs show no payment 500 error.

## MoSCoW Priority

Must Have

## Story Points

3

## Sprint

Current iteration

## Test Notes

- [ ] Local check completed.
- [ ] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 22. User Story: ATS Scoring Quality Review

Status: `In review`
Labels: `review`, `Should Have`
Story points: `5`
Sprint: `Current iteration`

## User Story

As a **job seeker**
I want **ATS scoring to distinguish relevant and unrelated roles**
So that **I can trust the report**

## User Experience Reason

This removes distrust caused by unrealistic scores, such as a weak match receiving a high score.

## Acceptance Criteria

- [ ] Related CV/job pair produces sensible score.
- [ ] Unrelated CV/job pair does not score unrealistically high.
- [ ] Must-have requirements have strong weighting.
- [ ] Recruiter risk is explained.

## MoSCoW Priority

Should Have

## Story Points

5

## Sprint

Current iteration

## Test Notes

- [ ] Local check completed.
- [ ] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 23. User Story: Report Page Readability And CV Wording Review

Status: `In review`
Labels: `review`, `ux`
Story points: `5`
Sprint: `Current iteration`

## User Story

As a **job seeker**
I want **the report, suggested CV wording and cover letter to be clear and realistic**
So that **I know exactly what to improve before applying**

## User Experience Reason

This removes confusion caused by long analysis text or generic output that does not sound like a real CV.

## Acceptance Criteria

- [ ] Recruiter risk is visible.
- [ ] Suggested CV wording is based on real evidence.
- [ ] Cover letter summary uses matched keywords.
- [ ] Colour keys are clear.
- [ ] The page is readable on mobile and desktop.

## MoSCoW Priority

Should Have

## Story Points

5

## Sprint

Current iteration

## Test Notes

- [ ] Local check completed.
- [ ] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 24. User Story: Final Project Presentation

Status: `Ready`
Labels: `presentation`, `Must Have`
Story points: `5`
Sprint: `Next iteration`

## User Story

As the **project owner**
I want **a final presentation of MyValidCV**
So that **I can demonstrate the product, architecture, Agile workflow and business value**

## User Experience Reason

This removes presentation anxiety and creates a clear story for reviewers or stakeholders.

## Acceptance Criteria

- [ ] Product problem and solution are explained.
- [ ] Core journey is demonstrated.
- [ ] Architecture summary is included.
- [ ] Agile/Kanban evidence is included.
- [ ] Deployment link is included.

## MoSCoW Priority

Must Have

## Story Points

5

## Sprint

Next iteration

## Test Notes

- [ ] Local check not required.
- [ ] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 25. User Story: Demo Script And Screenshots

Status: `Ready`
Labels: `presentation`, `Should Have`
Story points: `3`
Sprint: `Next iteration`

## User Story

As the **presenter**
I want **a demo script and screenshots**
So that **the final review runs smoothly**

## User Experience Reason

This removes the risk of forgetting key features or losing time during the demo.

## Acceptance Criteria

- [ ] Landing screenshot captured.
- [ ] Dashboard screenshot captured.
- [ ] Validation screenshot captured.
- [ ] Report screenshot captured.
- [ ] Pricing and owner screenshots captured.
- [ ] Demo script follows the core journey.

## MoSCoW Priority

Should Have

## Story Points

3

## Sprint

Next iteration

## Test Notes

- [ ] Local check not required.
- [ ] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 26. User Story: README Final Polish

Status: `Ready`
Labels: `Could Have`
Story points: `2`
Sprint: `Next iteration`

## User Story

As a **reviewer**
I want **a polished README**
So that **setup, scope, deployment and Agile evidence are easy to understand**

## User Experience Reason

This removes reviewer confusion and makes the project look complete and professional.

## Acceptance Criteria

- [ ] README links are current.
- [ ] Setup steps are clear.
- [ ] Heroku configuration is clear.
- [ ] Agile documentation is linked.

## MoSCoW Priority

Could Have

## Story Points

2

## Sprint

Next iteration

## Test Notes

- [ ] Local check not required.
- [ ] Heroku check not required.
- [ ] Browser/GitHub review completed.

---

## 27. User Story: Terms Privacy And Refund Content Pages

Status: `Ready`
Labels: `Should Have`
Story points: `3`
Sprint: `Next iteration`

## User Story

As a **user**
I want **clear terms, privacy and refund information**
So that **I understand how my data and payments are handled**

## User Experience Reason

This removes trust concerns before signup or payment.

## Acceptance Criteria

- [ ] Footer links lead to terms/privacy/refund content.
- [ ] Refund terms are written plainly.
- [ ] Data use is explained clearly.
- [ ] Pages are readable on mobile and desktop.

## MoSCoW Priority

Should Have

## Story Points

3

## Sprint

Next iteration

## Test Notes

- [ ] Local check completed.
- [ ] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 28. User Story: Owner Promo Code Workflow Guide

Status: `Ready`
Labels: `Should Have`
Story points: `3`
Sprint: `Next iteration`

## User Story

As the **website owner**
I want **a clear promo-code workflow**
So that **discounts can be managed safely**

## User Experience Reason

This removes operational confusion when offering discounts to users.

## Acceptance Criteria

- [ ] Owner can find discount-code admin.
- [ ] Active dates are explained.
- [ ] Percentage and usage limit are explained.
- [ ] Promo codes do not bypass payment records.

## MoSCoW Priority

Should Have

## Story Points

3

## Sprint

Next iteration

## Test Notes

- [ ] Local check completed.
- [ ] Heroku check not required.
- [ ] Browser/UX smoke test completed.

---

## 29. User Story: User Feedback After ATS Report

Status: `Backlog`
Labels: `Could Have`
Story points: `3`
Sprint: `Backlog`

## User Story

As the **website owner**
I want **users to rate report usefulness**
So that **I can improve the ATS report based on real feedback**

## User Experience Reason

This removes guesswork about whether users understand and value the report.

## Acceptance Criteria

- [ ] User can rate a report.
- [ ] Feedback belongs to a report and user.
- [ ] Owner can review feedback.
- [ ] Feedback does not interrupt the core journey.

## MoSCoW Priority

Could Have

## Story Points

3

## Sprint

Backlog

## Test Notes

- [ ] Local check completed.
- [ ] Heroku check completed.
- [ ] Browser/UX smoke test completed.

---

## 30. User Story: Improve ATS Taxonomy Coverage

Status: `Backlog`
Labels: `Should Have`
Story points: `8`
Sprint: `Backlog`

## User Story

As the **website owner**
I want **broader ATS taxonomy coverage across job families**
So that **MyValidCV can serve more industries accurately**

## User Experience Reason

This removes user distrust when the platform compares unrelated jobs or misses role-specific language.

## Acceptance Criteria

- [ ] More role families are seeded.
- [ ] Skills and qualifications are structured.
- [ ] Matching logic uses taxonomy without overfitting.
- [ ] Unrelated CV/job pairs score realistically.

## MoSCoW Priority

Should Have

## Story Points

8

## Sprint

Backlog

## Test Notes

- [ ] Local check completed.
- [ ] Heroku check completed.
- [ ] Browser/UX smoke test completed.

