# MyValidCV Kanban Board

Use this board during each sprint. Move cards by editing the markdown. Keep the
`Doing` column small so work actually ships.

## Board Rules

- Maximum `Doing` items: 3.
- A card must have acceptance criteria before it enters `Doing`.
- Production bugs outrank feature work.
- Every completed card needs test notes and deployment status.

## Backlog

- [ ] Add richer first-time onboarding empty state.
  - Priority: Medium
  - Outcome: new users know the first action after signup.

- [ ] Add owner-editable FAQ, terms and privacy content.
  - Priority: Medium
  - Outcome: trust pages can be managed without code edits.

- [ ] Add structured feedback after ATS report.
  - Priority: Medium
  - Outcome: collect usefulness score and improvement ideas.

- [ ] Add GitHub Project board mirroring this markdown board.
  - Priority: Low
  - Outcome: drag-and-drop Kanban view for non-technical review.

## Ready

- [ ] Improve report page copy hierarchy.
  - Priority: High
  - Acceptance criteria:
    - Recruiter risk is visible near the top.
    - Matched evidence, missing evidence and suggested wording are scannable.
    - Cover letter uses real matched evidence only.

- [ ] Review pricing page conversion copy.
  - Priority: High
  - Acceptance criteria:
    - Plans are Free, Plus and Enterprise only.
    - Pay button wording is provider-neutral.
    - Each plan explains the user pain it removes.

- [ ] Add owner console promo-code workflow guidance.
  - Priority: High
  - Acceptance criteria:
    - Owner can find discount codes from `/owner/`.
    - Admin flow explains active dates, percentage and usage limit.

## Doing

- [ ] Run a full UX smoke test after each deployment.
  - Priority: Critical
  - Acceptance criteria:
    - Home, register, login, dashboard, validate, result, pricing and owner URLs checked.
    - Any 500 error becomes a hotfix card.

## Review

- [ ] PageSpeed readiness pass.
  - Priority: High
  - Test notes:
    - HTTPS redirect confirmed.
    - HSTS confirmed.
    - Static assets are hashed, gzip compressed and immutable.
    - Official PageSpeed API was blocked by quota; manual PageSpeed test still needed.

## Done

- [x] Separate owner control center from dashboard.
  - Released: Heroku v94.
  - Result: `/owner/` is superuser-only; `/dashboard/` stays customer-focused.

- [x] Rename user settings page to Account.
  - Released: Heroku v98.
  - Result: navbar says `Account`; `/settings/` remains account management.

- [x] Add emotional landing carousel.
  - Released: Heroku v100.
  - Result: landing page now addresses application anxiety, recruiter view and relief.

- [x] Improve PageSpeed readiness.
  - Released: Heroku v101.
  - Result: deferred scripts, CDN preconnect, theme prepaint and production HTTPS settings.

## Blocked

- [ ] Official Google PageSpeed score capture.
  - Blocker: PageSpeed API quota was unavailable from this environment.
  - Unblock: run manually at `https://pagespeed.web.dev/` and paste the results into this board.
