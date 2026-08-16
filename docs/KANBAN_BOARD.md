# MyValidCV Delivery Kanban Board

Delivery date: **21 July 2026**

Sprint: **Delivery Sprint (20-21 July 2026)**

Milestone: **MVP v1.0**

This board is ordered by release dependency. Keep no more than three cards in
progress and attach evidence before moving a card to Done.

## Board Finalisation Status

Board structure: **Finalised on 20 July 2026**

MVP release: **Not yet closed** - the open evidence and release gates below must
be completed or recorded as approved delivery exceptions on 21 July.

## In Progress - Release Gates

- [ ] **#19 Final UX smoke test** - Critical, 3 points
  - Test home, registration, username/email login, dashboard, validation,
    result, pricing, owner console and owner report explorer.
  - Check mobile and desktop; turn every 500 error into a hotfix.
  - Local username/email login and email-only registration tests pass.

- [ ] **#21 Live Stripe payment confirmation** - Critical, 3 points
  - Confirm checkout, test payment, receipt, entitlement update and clean logs.

- [ ] **#22 ATS scoring quality review** - Critical, 5 points
  - Compare related and unrelated CV/job pairs and record the expected result.

## In Review

- [ ] **#20 Complete PageSpeed evidence** - High, 2 points
  - Mobile Lighthouse baseline captured on 19 July.
  - Desktop run, overall Performance score and post-deployment rerun remain.

## Ready - Complete In This Order

- [ ] **#23 Report readability and CV wording review** - High, 5 points
- [ ] **#27 Terms, privacy and refund content** - Critical, 3 points
- [ ] **#28 Owner promo-code workflow guide** - Medium, 3 points
- [ ] **#25 Demo script and screenshots** - Critical, 3 points
- [ ] **#26 README final polish** - High, 2 points
- [ ] **#24 Final project presentation** - Critical, 5 points

## Done - Released Increments

- [x] **Sprint 1, #1-#4:** landing, authentication and customer dashboard.
- [x] **Sprint 2, #5-#8:** Enterprise reports, owner separation, CV upload and ATS results.
- [x] **Sprint 3, #9-#12:** generated application content, pricing, Stripe and Heroku/PostgreSQL.
- [x] **Sprint 4, #13-#18:** production readiness, themes, access rules, seed data and Agile/GitHub documentation.
- [x] Owner Console remains at `/owner/` and Owner Reports at `/owner/reports/`.
- [x] Local login accepts username or email.
- [x] Email-only registration generates a unique internal username when omitted.
- [x] Authentication and owner-route regression tests pass locally.

## Post-Delivery Backlog

- [ ] **#29 Structured feedback after ATS report** - Medium, 3 points
- [ ] **#30 Improve ATS taxonomy coverage** - Medium, 8 points
- [ ] Richer first-time onboarding empty state - Medium
- [ ] Owner-editable FAQ and policy content - Medium

## Blocked / Delivery Exceptions

Move an item here only with the blocker, owner, attempted check and next action.
The manual PageSpeed check may be recorded as an external evidence exception if
the service is unavailable; this does not permit other release gates to be skipped.

## Evidence Required On 21 July

- Live application URL and Heroku release identifier.
- Local/system check and relevant automated-test result.
- Mobile and desktop UX smoke-test note.
- Stripe test transaction/receipt reference with secrets removed.
- PageSpeed mobile and desktop scores, or a documented external blocker.
- Final screenshots, demo script, README and presentation link.
