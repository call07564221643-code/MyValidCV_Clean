# Lean data model

The retained business data is limited to users, CVs, subscriptions/payments, and
the minimum audit/usage records needed to enforce product limits. Job adverts and
generated analysis content should be processed transiently unless the user
explicitly saves an application.

```text
User
 |-- 1:1 UserProfile
 |-- 1:M CV
 |-- 1:1 CustomerSubscription
 |-- 1:M PaymentTransaction
 `-- 1:M UsageRecord

UserProfile
 `-- account_type: individual | enterprise

CV
 |-- owner -> User
 |-- encrypted/private file reference (or encrypted database bytes)
 |-- original filename, MIME type, size, checksum
 `-- uploaded_at (deleted automatically after 30 days)

SubscriptionPlan
 `-- 1:M CustomerSubscription

CustomerSubscription
 |-- user -> User
 |-- plan -> SubscriptionPlan
 |-- Stripe customer/subscription identifiers
 `-- status and billing-period boundaries

PaymentTransaction
 |-- user -> User
 |-- subscription -> CustomerSubscription
 |-- Stripe Checkout Session/PaymentIntent identifiers
 `-- amount, currency, status, timestamps

UsageRecord
 |-- user/subscription
 |-- event_type: individual_validation | enterprise_cv_scan
 |-- quantity
 `-- occurred_at
```

## Data deliberately not retained by default

- pasted job descriptions and fetched job-advert HTML;
- permanent ATS result text;
- generated CV rewrites or cover letters;
- enterprise candidate CVs after the configured retention period;
- raw Stripe webhook payloads beyond the short audit/retry window.

Results can be returned to the browser in the validation response. Monthly limits
should be calculated from `UsageRecord` inside a database transaction. Payment
entitlements should come from `CustomerSubscription`, not a duplicated plan value
on `UserProfile`.

## Privacy controls

- Private, authenticated CV access only.
- Encryption in transit and at rest.
- User-controlled deletion and a documented retention period.
- A daily cleanup job enforcing a rolling 30-day maximum retention period.
- Store a checksum to detect duplicate uploads without logging CV contents.
- Keep only Stripe identifiers and payment metadata; never store card details.
