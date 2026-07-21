# Testing

## Testing approach

MyValidCV uses automated Django tests, framework checks, migration checks and
manual journey testing. The highest-risk areas are authentication, ownership of
CV data, destructive actions, plan entitlements, payments and external-service
failures.

The automated suite was last run on 21 July 2026 with Python 3.12, Django 6.0.1
and the test SQLite database. Production uses PostgreSQL, so the live deployment
must also receive a short smoke test after every release.

## Automated verification

Run the project checks from the repository root:

```powershell
$env:TEST_USE_SQLITE='True'
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py check --deploy
```

`check --deploy` is a production-configuration audit. Local development may
legitimately report HTTPS or cookie warnings; the deployed environment must use
`DEBUG=False`, HTTPS and secure cookies.

### Automated test coverage

| Area | Behaviour covered |
| --- | --- |
| Accounts | Registration without a username field, unique generated usernames, case-insensitive email login, username login, logout navigation, password-reset email, unknown-email privacy and duplicate-email validation |
| Authorization | Login protection, owner-only report explorer, customer denial, CV ownership checks and prevention of cross-user update/delete |
| CV management | Upload validation, list/read, title update, confirmation before deletion, POST deletion and cascading deletion of analysis results |
| ATS analysis | File limits, executable rejection, private/non-HTTP URL rejection and scoring across relevant and irrelevant job roles |
| Plans | Active-subscription entitlements, Enterprise bulk access and protection against stale profile labels granting paid access |
| Payments | Checkout controls, webhook processing, invoice/receipt behaviour and mock-mode safeguards |
| Core UI | Landing-page calls to action, authenticated navigation, dashboards and Maya's safe fallback when the local Ollama service is unavailable |

The complete suite contains 47 tests. Test output may include an expected logged
Ollama connection error: the associated test deliberately verifies that Maya
returns a safe fallback response when that optional service is unavailable.

## CRUD requirement traceability

The original `CV` model supplies a complete authenticated front-end CRUD flow;
users do not need Django Admin.

| Operation | Form/view | User-visible result |
| --- | --- | --- |
| Create | `CVUploadForm` / `upload_cv` | A validated CV is saved against the signed-in user |
| Read | `upload_cv` and dashboard queries | The user sees only their saved CVs and analysis history |
| Update | `CVUpdateForm` / `update_cv` | The owner can rename a saved CV |
| Delete | `delete_cv` confirmation and POST | The owner can delete a CV and its related results |

Delete is intentionally a two-step action. A GET request only displays the
confirmation page; the CSRF-protected POST performs deletion. Each update and
delete lookup includes both the public UUID and `request.user`, returning 404
for records owned by another account.

## Manual journey test script

Complete this matrix in the deployed application before submission and record
the actual result and browser used. “Automated pass” means the server-side rule
is covered, but it does not replace the final browser check.

| Journey | Steps and expected result | Current evidence |
| --- | --- | --- |
| Register | Submit a valid name, email and matching passwords; account is created without asking for username | Automated pass; deployment check required |
| Login | Sign in once with email and once with username; both open the dashboard | Automated pass; deployment check required |
| Invalid login | Submit incorrect credentials; a generic error appears without revealing account existence | Deployment check required |
| Password reset | Select “Forgot password?”, submit a registered email, follow the one-time link and choose a new password | Automated pass; production SMTP check required |
| Logout | Sign out and confirm protected pages redirect to login | Deployment check required |
| Create CV | Upload a supported CV; it appears in Saved CVs and can be selected for analysis | Automated validation; browser check required |
| Read CV | Open Manage CVs; only the signed-in user's CVs are listed | Automated pass; browser check required |
| Update CV | Choose Edit, change the title and save; updated title appears in both management and dashboard views | Automated pass; browser check required |
| Delete CV | Choose Delete; cancel/back preserves it, confirmation POST removes it and related results | Automated pass; browser check required |
| Ownership | As a second user, request another user's edit/delete UUID; response is 404 and data remains | Automated pass |
| Individual analysis | Add CV and job details; report shows score, strengths, gaps and recommendations | Browser check required |
| Enterprise | With active Enterprise subscription, run bulk analysis and inspect saved reports | Entitlement automated; live journey required |
| Owner reports | A superuser opens the separate report explorer; a normal customer is denied | Automated pass; browser check required |
| Stripe | Complete a test-mode checkout and send signed webhook; entitlement updates once | Automated pass; Stripe test deployment required |
| Retention/reminders | Run scheduled management commands against test data and confirm expired data/reminders are handled | Deployment scheduler check required |

## Compatibility and accessibility checks

Check the current Chrome, Firefox and Edge desktop releases plus a narrow mobile
viewport. Verify keyboard-only navigation, visible focus, meaningful labels,
form errors, zoom at 200%, colour contrast, responsive layouts and confirmation
dialog content. Recheck with Lighthouse after each material template or asset
change.

The mobile Lighthouse evidence supplied on 19 July 2026 recorded FCP 2.0 s, LCP
2.0 s, TBT 0 ms, CLS 0 and Speed Index 2.1 s under Slow 4G emulation. The audit
identified render-blocking CSS and an oversized CV-steps image; these remain
performance regression targets. Evidence screenshots are stored in
`static/images/`.

## Security and data-integrity checks

- Forms use Django CSRF protection and server-side validation.
- Protected views require authentication; privileged reports additionally
  require superuser status.
- CV mutations scope database lookups to the authenticated owner.
- Destructive CV behaviour is POST-only after a non-destructive confirmation.
- Password reset does not disclose whether an email exists.
- Plan access comes from an active subscription, not an editable display label.
- Secrets come from environment variables and `DEBUG` defaults to false outside
  explicitly configured development/test environments.
- Stripe webhooks require signature verification and production cannot use mock
  checkout mode.

## Defects found during regression testing

| Defect | Resolution | Regression evidence |
| --- | --- | --- |
| Email login still triggered username-required validation | Added email-or-username authentication and removed the public username registration requirement | Account login and registration tests |
| Customers had no password-recovery path | Added Django's token-based password-reset views, templates and login link | Reset email and privacy tests |
| Users could not update or delete their own CVs outside Admin | Added owner-scoped update and confirmation/delete views | CV management tests |
| CV tests were redirected by production HTTPS settings | Isolated request tests with the intended test security override | CV management suite passes |
| Dashboard tests asserted obsolete interface wording | Updated assertions to match the current dashboard contract | Full regression suite |

## Release gate

A release is ready only when framework and migration checks pass, all automated
tests pass, `DEBUG=False` is confirmed in deployment, and the authentication,
CV CRUD, payment and role-based smoke tests above have been completed. Any item
marked “deployment check required” must be recorded as passed or as a documented
known issue before final submission.
