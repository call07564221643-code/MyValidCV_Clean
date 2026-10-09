# Validation, Scaling, Retention and Owner Alerting

Status: pre-implementation specification  
Audience: product owner, engineering and operations  
Decision: approved in principle; provider credentials and owner contact details remain required before live delivery.

## 1. Outcomes and non-negotiable guardrails

The changes must:

1. Keep CV upload and validation available during traffic spikes.
2. Improve validation quality without allowing an LLM to make the final hiring, rejection or ranking decision.
3. Notify the owner before storage, database, web capacity or optional LLM capacity becomes critical.
4. Minimise personal-data retention and storage cost while preserving reports users are entitled to keep.
5. Never delete active data merely because a single monitoring reading is high.
6. Make every deletion and automated recommendation auditable.

## 2. Current-state findings

- ATS scoring is deterministic and does not require Ollama.
- Maya uses the optional Ollama-compatible endpoint, with an eight-second timeout and deterministic fallback.
- Production is configured for one Basic web dyno with two workers and two threads.
- CV processing currently happens synchronously in the web request.
- A daily/monthly-capable `purge_expired_cvs` command exists, but scheduling is external.
- The purge command deletes complete CV records. Because `ATSResult.cv` currently cascades, deleting a CV also deletes its reports.
- Enterprise candidate files and their result rows are currently deleted together.
- Without private object storage, uploaded bytes can be duplicated into PostgreSQL as a durability fallback.
- The owner health page is pull-based. Sentry is optional; no complete email/SMS/WhatsApp capacity-alert pipeline exists.
- The health page's storage warning compares every account with a hard-coded 10 MB value, although plan limits differ.

## 3. Target architecture

### Request path

1. Authenticate and check entitlement/rate limit.
2. Stream the upload to private object storage; do not load an unbounded file into memory.
3. Validate extension, MIME signature, maximum bytes, page count and malware-scan status.
4. Create a queued analysis record and return a job identifier quickly.
5. A background worker extracts and validates the document, runs deterministic scoring and persists a compact report.
6. The UI polls or receives completion status and presents the report.
7. Ollama is invoked only by an approved policy trigger and never blocks the deterministic result.

### Availability controls

- Add a background queue and separate worker process for CV processing.
- Set per-plan upload, batch and concurrency limits.
- Apply backpressure: return a clear queued/busy response instead of allowing request timeouts.
- Add retry with exponential backoff only for transient operations; never retry malformed documents.
- Use idempotency keys so retries do not create duplicate CVs, reports or charges.
- Add a circuit breaker around Ollama, messaging providers, malware scanning and object storage.
- Keep deterministic validation available when Ollama is disabled or unhealthy.

## 4. Data-lifecycle policy

### Separate raw documents from reports

Change the schema so a source CV file can be purged without automatically deleting its ATS report:

- Make the report-to-CV relationship nullable with `SET_NULL`, or introduce a separate immutable report snapshot.
- Store only the minimum display fields needed by the report after source deletion.
- Apply the same separation to enterprise candidate source files and enterprise assessment records.
- Treat extracted CV text as personal data; do not retain it as a hidden substitute for the deleted file.

### Default lifecycle proposal

These are starting defaults and must be reflected in the privacy notice and customer terms:

| Data class | Proposed default | Action |
|---|---:|---|
| Rejected/invalid upload | Immediately after response, maximum 24 hours for diagnostics | Hard-delete file and extracted text |
| Enterprise pilot source CV | 24 hours | Hard-delete source; delete or anonymise trial result as disclosed |
| Enterprise production source CV | 7 days after completed batch | Delete source; retain compact report according to organisation policy |
| Free individual source CV | 7 days after last use | Delete source; retain compact report while account is active |
| Paid individual source CV | 30 days after last use | Delete source unless the user explicitly chooses to retain it |
| Deleted account data | Short recovery window, then purge | Cascade through an audited account-erasure workflow |
| Operational metrics | 90 days detailed, 12 months aggregated | Remove user identifiers from aggregates |
| Alert and deletion audit | 12 months | Store metadata only, never CV content |

### Storage-pressure policy

Use graduated actions rather than emergency deletion:

- At 70%: warn owner, forecast days remaining and accelerate already-expired cleanup.
- At 80%: notify by email and WhatsApp/SMS; prevent optional duplicate storage and pause nonessential generated artifacts.
- At 90%: critical alert; shorten only temporary-data grace periods within the published policy and stop new pilot uploads if required.
- At 95%: enter controlled admission mode, accepting only entitled production traffic that can be safely stored.

Never delete unexpired customer data outside the published policy merely to recover capacity. A legal hold, active dispute or explicit retention requirement must override automated deletion.

### Purge implementation controls

- Run dry-run reporting before activation and after every policy change.
- Delete in small, configurable batches to avoid long locks and memory spikes.
- Make the job idempotent and safe to resume.
- Record policy, cutoff, object key, record identifier, byte count, outcome and timestamp in a deletion audit; never record CV content.
- Reconcile database records, object-store objects and `CVStorage.used_storage` after every run.
- Alert on purge failures, mismatched objects, unusually high deletion counts and jobs that have not run on schedule.
- Use object-store lifecycle rules as a second safety net, not the only deletion mechanism.
- Provide user-initiated delete and export controls and show the applicable retention period in the UI.

## 5. Owner alerting and admin settings

### Models/admin configuration

Add an admin-managed singleton `PlatformOperationsSettings` containing:

- owner display name and timezone
- alert email address
- mobile number in international E.164 format
- enable email, SMS and WhatsApp independently
- severity allowed per channel
- quiet hours for warnings (critical alerts bypass quiet hours)
- acknowledgement/escalation interval
- storage thresholds and cost-budget thresholds
- daily digest time
- test-notification buttons and last verified timestamps

Provider secrets must remain encrypted environment variables, not editable database fields. Admin settings should select the provider and destination only.

Add `AlertRule`, `OperationalAlert` and `NotificationAttempt` records for thresholds, deduplication, acknowledgements, delivery status and audit history. Never include CV content, candidate names or other sensitive personal data in an alert.

### Initial alert catalogue

| Severity | Trigger | Default delivery |
|---|---|---|
| Critical | Site unavailable or sustained 5xx errors | Email + SMS + WhatsApp |
| Critical | Database unavailable, storage >=95%, or upload pipeline stopped | Email + SMS + WhatsApp |
| Critical | p95 analysis time approaching 30-second request timeout | Email + SMS + WhatsApp |
| Warning | Storage >=70%/80% or forecast below 14/7 days | Email + WhatsApp |
| Warning | Upload failure rate >5% over a meaningful sample | Email + WhatsApp |
| Warning | Queue age >60 seconds or queue depth exceeds safe worker capacity | Email + WhatsApp |
| Warning | Ollama fallback/error rate >5% for 15 minutes | Email |
| Warning | LLM or messaging spend reaches 70%/85% of monthly budget | Email + WhatsApp |
| Information | Daily health, volume, cost and capacity digest | Email |

Every alert requires a recovery notification, deduplication window and link to the owner health page/runbook. Thresholds remain provisional until seven to fourteen days of production baselines exist.

## 6. Validation enhancements

### Deterministic validation remains authoritative

- Improve file signature and extraction-quality checks.
- Detect image-only/scanned files and route them to bounded OCR when enabled.
- Version extraction, taxonomy, scoring and policy independently.
- Cache taxonomy data rather than querying all taxonomy rows for every CV.
- Measure requirement extraction, mandatory-rule accuracy, score stability and failure reasons.
- Expand the reviewed evaluation set across job families, career levels, formats and protected-group proxies where legally appropriate.
- Require human review for enterprise shortlisting and preserve overrides with reasons.

### Selective Ollama backend services

Introduce one provider-neutral `AIService` interface with typed tasks and strict JSON schemas. Approved tasks:

1. Resolve ambiguous job requirements when deterministic confidence is low.
2. Map unknown terminology to taxonomy candidates for later human/admin approval.
3. Produce plain-language explanations from already-calculated deterministic evidence.
4. Suggest truthful CV improvements grounded only in supplied text.
5. Summarise operational incidents and likely causes for owner alerts.
6. Classify support questions before using the existing safe response path.

Prohibited tasks:

- final candidate rejection, hiring decision or autonomous rank override
- inventing CV evidence, qualifications, dates or achievements
- sending raw CVs to an unapproved external endpoint
- silently changing a deterministic score
- using protected characteristics or proxies in employment recommendations

Each AI call must have a task name, prompt/model version, redacted/minimised input, timeout, output schema validation, confidence gate, cost/token record and deterministic fallback. Cache only non-personal or safely scoped results. Log metadata, not prompt bodies containing CV data.

## 7. Metrics and operating targets

Primary KPIs:

1. **Successful validation rate:** completed valid analyses / accepted analysis jobs. Initial target >=99% excluding user-invalid documents.
2. **Validation latency:** p95 from accepted upload to result ready. Initial target <=10 seconds for normal individual CVs; queue age reported separately.
3. **Capacity safety:** forecast days until any capacity limit. Target >=14 days at warning level and no unplanned capacity exhaustion.

Driver metrics:

- queue depth, oldest-job age, worker utilisation and throughput
- extraction failures by format, average upload bytes and storage growth/day
- Ollama invocation rate, fallback rate, latency and estimated cost by task
- purge bytes/records, purge duration, overdue records and reconciliation mismatch

Guardrails:

- zero unlogged automated deletion and zero deletion outside the active policy
- zero LLM-only hiring/rejection decisions
- score consistency on the locked evaluation set within the approved version
- owner notification delivery success >=99% for critical alerts

## 8. Implementation sequence and release gates

### Phase 0 — baseline and safety

- Confirm data controller/processor obligations and approve retention wording.
- Capture 7–14 days of latency, queue-equivalent volume, upload sizes, failures and storage growth.
- Correct per-plan storage calculations on the health page.
- Configure Sentry and verify a test incident reaches the owner.
- Create backups and test restoration before schema or purge changes.

Gate: no automated deletion until restore and dry-run evidence are approved.

### Phase 1 — data separation and retention

- Add report snapshots/nullable source relationships and migrations.
- Move files to private object storage and disable PostgreSQL binary fallback after verification.
- Build the policy-based, batched purge service and deletion audit.
- Add dry-run report, reconciliation and owner-visible retention status.

Gate: reports remain readable after test source files are purged; legal holds and user deletion tests pass.

### Phase 2 — monitoring and notifications

- Add operations settings, alert rules/events and delivery attempts.
- Implement email first, then provider adapters for SMS and WhatsApp.
- Add health sampling, thresholds, deduplication, recovery and escalation.
- Add admin test buttons and delivery verification.

Gate: warning, critical, recovery, deduplication and provider-failure drills pass without sensitive data in messages.

### Phase 3 — asynchronous scaling

- Add queue/worker, job statuses, idempotency and UI progress.
- Add backpressure, concurrency caps, bounded retries and circuit breakers.
- Run end-to-end staging tests with TXT, PDF, DOCX, OCR, database writes and object storage at 10/25/50/100 concurrent arrivals.

Gate: no lost/duplicate jobs, p95 target met, recovery verified and capacity forecast visible.

### Phase 4 — enhanced validation

- Cache taxonomy and expand deterministic checks/evaluation data.
- Add human-review and override telemetry.
- Introduce `AIService` in shadow mode for one low-risk task first.
- Compare AI-assisted output with deterministic baseline and human review before exposure.

Gate: quality improves without score instability, privacy leakage, unacceptable latency or uncontrolled cost.

### Phase 5 — controlled production rollout

- Release to staff, then a small percentage of individual users, then selected enterprise tenants.
- Use feature flags and an immediate kill switch for AI and new processing paths.
- Review daily during rollout, then weekly after stability is demonstrated.

## 9. Tests required before implementation is considered complete

- Unit tests for every retention rule, threshold, channel and AI policy decision.
- Migration test proving historical reports survive raw-file deletion.
- Restore test from backup and object-store recovery exercise.
- Race/idempotency tests for duplicate uploads and retrying workers.
- Load tests covering full HTTP upload, persistence, queue, worker and download/report access.
- Notification tests with mocked providers plus one controlled live test per channel.
- Security tests for file spoofing, decompression bombs, malware, SSRF and unauthorised record access.
- Evaluation tests for scoring regressions, mandatory requirements, hallucination and unsupported AI claims.

## 10. Inputs required from the owner before live integrations

1. Owner alert mobile number including country code (enter it later through the new admin setting; do not place it in source code or chat history).
2. Preferred delivery provider: one provider for both SMS/WhatsApp where possible, or separate providers.
3. Verified WhatsApp Business sender and any required message templates.
4. Monthly alert/LLM spending cap and preferred billing currency.
5. Approval or adjustment of the proposed retention defaults.
6. Private object-storage provider and credentials, supplied through protected environment configuration.

Implementation can begin with provider-neutral models and test adapters before items 1–3 are supplied.
