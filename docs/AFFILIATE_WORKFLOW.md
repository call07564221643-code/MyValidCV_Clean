# Affiliate operations

Open `/partners/owner/affiliates/` using an account with the affiliate review permission. Record a completed meeting or give a waiver reason, then approve. Approval creates a partner organisation, owner membership, 20% commission profile and a random referral code with a one-calendar-year expiry. Repeating approval does not create duplicates or extend expiry.

The affiliate receives a code email and sees it at `/partners/`. They supply bank payout details and accept `affiliate-20-v2`. A code is inactive until these steps are complete. Customers receive 20% off eligible paid plan checkouts (including Enterprise); discounts do not stack. The affiliate receives 20% of the discounted payment for eligible verified checkout purchases. Automatic subscription renewals are excluded from affiliate commission. Recurring checkout prices remain the price agreed at purchase; expiry prevents new code redemptions. The agreement displays these terms, hold period, minimum payout, refund reversals and warning/cancellation rights.

For cancellation, publish a warning to the affiliate dashboard first. The cancellation button then becomes available. Cancelled and expired codes fail checkout validation. Existing valid earned commission is preserved subject to refund and payout review. Warning publication does not send an external email or require acknowledgement by the affiliate.

Bank details are encrypted with a separate Fernet key in `AFFILIATE_PAYOUT_ENCRYPTION_KEY`. Keep that key backed up in your secret manager; do not rotate/remove it without re-encrypting existing records. Account data is never emailed. Only superusers or holders of `growth.approve_commission` can open the audited, non-cached payout details screen. Payouts are external/manual; this feature does not send money or verify bank ownership.

Set `PUBLIC_SITE_URL` to the public origin and configure a delivering email backend. Email failures appear on the owner page; use Resend code to retry. A successful SMTP send means the backend accepted the message, not that the recipient opened it.

Migrate both growth and payments. To provision previously approved applications and give the owner limited dashboard/payout access:

```text
python manage.py provision_approved_affiliates --reviewer-email OWNER_EMAIL --grant-reviewer
```

This grants affiliate review and commission permissions without staff or superuser status. Declined and withdrawn applications are excluded.

Validation: run `TEST_USE_SQLITE=true python manage.py test growth payments subscriptions accounts --noinput` (use PowerShell environment syntax on Windows). Regression coverage includes permission checks, idempotent approval, real agreement acceptance, encrypted payout storage, Enterprise price preview, commission amounts, refund reversal, expiry, warning-first cancellation and email retry.
