# Logic review — 8 October 2026

Static review of affiliate applications, approval, referral capture, commissions, checkout activation, subscription entitlements, usage limits, vouchers, and related code overlap. No application code changed. This is a targeted review of the main business flows, not an exhaustive audit of every function or a security certification.

## Findings, in priority order

1. **High — repeated payment activation changes access again.** `payments/views.py:586–622`: `was_paid` prevents duplicate commission creation and discount counting, but subscription plan, status, expiry, and invoice dates are still rewritten. A delayed duplicate checkout callback extends access from the callback date; replaying an older purchase after a newer purchase can restore the older plan. Refunded transactions also pass through this function and become paid again. Make already processed transactions return without regranting access, and define permitted payment state transitions.

2. **High — application approval does not provision affiliate access.** `growth/admin.py:38–41` approves only the application row. There is no application-to-organisation/partner linkage or approval service that creates an organisation membership, partner profile, or referral code. `growth/models.py:136` requires a manually supplied code; no referral code generator was found in application code. Approved applicants therefore need separate manual onboarding before they can accept terms or earn commissions. If manual provisioning is intended, expose and document that remaining step; otherwise implement an atomic, repeatable approval/provisioning service.

3. **High — approval rules can be bypassed in the admin form.** `AffiliateApplicationAdmin` leaves `status`, `meeting_status`, `reviewed_by`, and meeting details editable. Setting status to approved directly bypasses the completed-meeting filter in the approval action and does not set decision metadata. Actions use ordinary model change permissions rather than explicitly requiring `growth.review_affiliate_application`. Centralize transitions and enforce the same rules for individual edits and bulk actions. Commission actions similarly do not explicitly enforce the declared `approve_commission` permission.

4. **High — affiliate revenue and commission totals multiply.** `growth/views.py:78–85` joins both attributions and commissions in one aggregate query. Distinct counts protect counts, but sums repeat each commission once per attribution. Two attributions and one £10 commission display £20 commission. Use independent subqueries or separate aggregates; `Sum(distinct=True)` is insufficient when legitimate amounts are equal. The template also labels every currency GBP and totals include reversed commissions.

5. **Medium — expired referrals prevent a new valid code from working.** `growth/services.py:34–36` returns any unconverted attribution without checking expiry or partner eligibility. `growth/middleware.py:43–50` uses the same broad lookup. An expired attribution is retained while conversion correctly excludes it, so a newly entered valid code earns no commission. Share a lookup for current eligible attributions and retire expired ones before accepting a new referral.

6. **Medium — referral capture/conversion has concurrency gaps.** Capture has no uniqueness constraint for an open customer attribution. Concurrent captures can create multiple rows; middleware `get_or_create` can subsequently raise `MultipleObjectsReturned`. Conversion does not lock the attribution, so distinct payment transactions for one customer can consume the same attribution simultaneously. The existing constraint prevents duplicate commissions only for the same partner/transaction. Serialize attribution selection and consumption according to the intended first-conversion policy.

7. **Medium — commission recording failures are not retried.** `payments/views.py:633–640` logs referral errors while allowing activation to succeed. Future callbacks skip recording because `was_paid` is true, permanently losing the commission until manual repair. Add durable retry/reconciliation separate from access activation.

8. **Medium — usage and discount limits are vulnerable to concurrent requests.** `accounts/models.py:64–72` and `ats/views.py:1239–1345` check and increment usage separately using a Python increment. Parallel analyses can both pass the final available slot and overwrite the counter. Enterprise upload similarly checks aggregate usage before creating candidates. Checkout validates discount capacity before payment; activation increments a separately loaded discount row without locking, allowing lost counts and oversubscription. Reserve capacity atomically with an explicit policy for abandoned checkouts.

9. **Medium — accepted affiliate channels differ from application channels.** `growth/forms.py:6–14` permits podcast, community, direct recommendations, and other; `growth/views.py:14–16` omits these from agreement acceptance. Applicants using only those channels cannot accept an agreement for their proposed channel. Keep one channel definition shared by both forms.

10. **Medium — referral codes are ambiguous by case.** `ReferralPartner.referral_code` is unique as stored, but lookups use `iexact(...).first()`. On case-sensitive database configurations, `Creator` and `creator` can coexist and resolve to an arbitrary partner. Normalize codes and enforce matching case-insensitive uniqueness in the database. Automatic generation should handle collisions with a database-backed retry rather than an existence check alone.

## Code overlap and consolidation

- Stripe and SumUp checkout repeat plan/discount/referral validation, transaction creation, invoice creation, and zero-price activation (`payments/views.py:64` and `:238`). Extract a common preparation service; keep provider requests separate.
- Middleware and explicit-code capture implement different open-attribution selection and metadata rules. Share eligibility and current-attribution selection while preserving their separate consent paths.
- User creation runs two profile signals (`accounts/signals.py`): the second fetches and saves the profile immediately after the first creates it. Consolidate into one idempotent signal.
- Application and agreement channels are duplicated and already inconsistent.
- `extract_cv_evidence_lines` and `find_evidence_citations` overlap in source-line extraction but have different matching/fallback behavior. Establish the intended evidence rules before consolidation; they are not interchangeable duplicates.
- Entitlement wrappers correctly delegate to `subscriptions.services`; scoring and extraction are already separated. These are useful boundaries to preserve.

## Existing protections and verification

Referral eligibility requires an active organisation and partner profile, approval timestamp, agreement date validity, and acceptance of the current terms. Explicit code entry rejects active organisation members' self-referrals. Voucher redemption uses an atomic transaction, row locks, and a per-user uniqueness constraint. Payment activation locks the payment row, and commissions have a partner/payment uniqueness constraint.

Existing tests cover application submission, dashboard permission, agreement acceptance, separate referral consent, sequential payment commission deduplication, and full-refund reversal. These do not demonstrate protection against the concurrency and state-transition cases above.

Attempted: `.venv/Scripts/python.exe manage.py test growth payments subscriptions accounts --noinput`. Tests could not start: `ModuleNotFoundError: No module named 'sentry_sdk'`. No dependencies installed or test results claimed. Findings are based on source inspection; concurrent scenarios and database-specific code uniqueness need runtime verification.

Recommended order: payment state/idempotency; affiliate approval/provisioning; dashboard aggregates; attribution expiry/concurrency/retry; quota reservations; shared definitions and checkout consolidation. Add regression tests for each behavioral correction rather than broad cosmetic refactoring.
