# MyValidCV User Experience Playbook

The product should sell relief first and logic second. Users subscribe because
they feel uncertainty, fear of rejection, urgency and lack of control. The UI
should help them feel: "I know what to fix before I apply."

## UX Promise

Upload CV -> Add Job -> Validate -> Improve -> Apply.

Every page should move the user closer to that promise or support their account.

## Emotional Jobs To Be Done

- "I am tired of applying and hearing nothing back."
- "I do not know if my CV is weak or if the job is too competitive."
- "I want to understand what recruiters will notice first."
- "I need a simple answer before the deadline."
- "I want confidence without inventing experience."

## Conversion Principles

- Lead with relief: "Know what to fix before you apply."
- Show one main action per page.
- Keep explanations short and practical.
- Do not overuse percentages; explain why the CV is weak.
- Never suggest fake experience.
- Use pricing copy that connects the plan to urgency and usage.
- Keep enterprise reporting separate from job-seeker workflows.

## Page Standards

### Landing Page

- Primary goal: get a visitor to start a free validation.
- Keep one dominant CTA: `Start free` or `Validate my CV`.
- Carousel content should express pain, relief and control.
- Feature cards should support the CTA, not compete with it.

### Registration And Login

- Explain that an account saves CVs, reports and usage.
- Let an existing user sign in with either username or email.
- Label the identity field `Username or email` and keep authentication errors generic.
- Social login buttons must reduce friction.
- Do not show unnecessary marketing images inside the form.

### Dashboard

- Show the user's status, renewal and remaining allowance simply.
- Prioritise next best action.
- Keep website-owner controls out of the customer dashboard.
- Enterprise users should see bulk reports and candidate screening tasks.

### Validation Workspace

- The main input should feel like an AI workspace.
- CV upload, saved CV selection and job input should happen in one flow.
- Show clear loading and success states.
- If a document is not a strong CV, explain what is missing.

### Result Page

- Replace generic scores with recruiter-facing interpretation.
- Explain matched evidence, missing evidence and highest-impact fixes.
- Suggested CV wording should use real CV evidence only.
- Cover letter should summarise the strongest matched evidence.

### Pricing

- Keep plans simple: Free, Plus, Enterprise.
- Use `Pay now`, not provider-specific wording.
- Explain what each plan removes: uncertainty, limits or manual screening.

### Owner Console

- Use `/owner/` only for superuser website control.
- Include users, payments, refunds, subscriptions, reports, promo codes and health.
- Use `/owner/reports/` as the owner's searchable report explorer.
- Keep the Owner Reports link distinct from customer and Enterprise report links.
- Do not expose owner metrics to enterprise users.

## 21 July Delivery Experience

The release demonstration must follow one uninterrupted journey:

1. Understand the promise from the landing page.
2. Register, or log in with username/email.
3. Upload a valid CV and see a useful invalid-document error when appropriate.
4. Add a job, validate and understand the recruiter-facing result.
5. Review honest suggested wording and cover-letter support.
6. Understand plan limits before checkout.
7. Confirm payment and account entitlement.
8. Show Enterprise bulk reporting separately from `/owner/` and `/owner/reports/`.

For delivery approval, check this journey on mobile and desktop. Record the
browser, viewport, live URL and outcome; do not treat code review alone as UX
acceptance.

## Accessibility And Trust

- Keep colour contrast readable in light and dark mode.
- Buttons need clear labels or accessible names.
- Forms need labels and useful errors.
- Paid features should explain what happens before checkout.
- Always show that results are guidance, not a hiring guarantee.

## UX Quality Checklist

- Can a cold visitor understand the product in five seconds?
- Can a new user validate a CV without visiting several pages?
- Does every CTA use plain language?
- Does the report explain what to do next?
- Does the UI feel calmer after the user clicks Validate?
- Does every account type see only relevant actions?
