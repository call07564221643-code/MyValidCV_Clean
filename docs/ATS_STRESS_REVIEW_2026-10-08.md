# ATS stress test — 8 October 2026

Completed 450 scoring calls plus a separate profiling call using the actual ATS engine and project-seeded taxonomy (48 skills, 14 qualifications, 17 roles). No scoring exceptions occurred. Application code and application data were unchanged; the benchmark created a separate SQLite database. No AI API calls were made.

## Concurrent workload

Each level ran 96 mixed recruitment-match, software-match, and dental-versus-software requests through a thread pool. These are local pipeline calls, not HTTP requests. Latency starts when a worker begins processing, so it excludes time waiting in the executor queue. Connection cleanup is included in wall-clock throughput but excluded from scoring latency. Single-process threading does not model multiple production worker processes.

| Workers | Calls | Errors | Median latency | p95 latency | Throughput |
|---|---:|---:|---:|---:|---:|
| 1 | 96 | 0 | 73 ms | 152 ms | 11.12/s |
| 4 | 96 | 0 | 283 ms | 388 ms | 13.36/s |
| 8 | 96 | 0 | 618 ms | 926 ms | 11.72/s |
| 16 | 96 | 0 | 1,207 ms | 1,728 ms | 11.50/s |

More threads did not provide sustained throughput improvement beyond four workers. Test process scheduling, Python execution, and local SQLite reads all contribute; this test does not isolate their individual effects. Treat the observed throughput as a development-machine result rather than production capacity.

## Larger documents

Both documents were expanded using repeated synthetic content. Three uninstrumented calls per size measured latency, followed by a separate call with Python memory tracing.

| Characters per CV and job description | Median | Maximum of 3 calls | Peak traced Python allocations |
|---|---:|---:|---:|
| 2,000 | 234 ms | 273 ms | 0.05 MiB |
| 10,000 | 1.19 s | 1.19 s | 0.15 MiB |
| 50,000 | 6.06 s | 9.02 s | 0.63 MiB |
| 100,000 | 11.56 s | 16.12 s | 1.24 MiB |

Separately, a 100,000-character CV against a normal advert had a median of 969 ms; a normal CV against a long advert had a median of 11.21 seconds. Long job descriptions are the stronger slowdown in these fixtures. The separate profiler briefly overlapped the size-test phase; the 50,000-character maximum may include that contention. Small sample sizes make size-case p95 equivalent to the maximum; they are not robust tail-latency estimates.

Memory numbers cover allocations observed by `tracemalloc`, not total process RAM, native-library allocations, or production worker memory. The figures do not establish a leak-free service under prolonged operation.

## Matching behavior and invalid input

Each of ten scenarios repeated five times with identical scores on every repetition:

| Scenario | Score | Validation |
|---|---:|---|
| Recruitment CV / recruitment advert | 81 | Accepted |
| Software CV / software advert | 70 | Accepted |
| Dental-oriented CV / software advert | 25 | Accepted as documents; low match |
| Repeated keyword list / software advert | 40 | CV rejected |
| Empty CV / recruitment advert | 12 | CV rejected |
| Recruitment CV / empty advert | 83 | Advert rejected |
| Recruitment CV with Unicode suffix | 81 | Accepted |
| CV with long token appended | 81 | Accepted |
| Repeated long CV | 81 | Accepted |
| Repeated long advert | 81 | Accepted |

The matching examples show plausible ordering and repeatability, not independently measured hiring accuracy. The dental and software fixtures are synthetic variations of the recruitment fixture, not a representative professionally labeled dataset. Repeated text retains the same score in these specific cases.

**Important boundary:** direct scoring returns 83 for an empty advert when the supplied role title still identifies the recruitment role. `validate_job_description` rejects that advert and the reviewed normal analysis view validates before scoring. Any future caller must preserve this validation; direct scorer output alone is insufficient to establish valid input.

TXT and generated DOCX extraction passed CV validation. A corrupt PDF was rejected with `CVExtractionError`. Valid PDF extraction, OCR/scanned PDFs, and multilingual matching accuracy were not benchmarked.

## Profile and recommended improvements

The separate profile used a normal CV and an advert repeated 16 times (roughly 10,000 characters). Under profiling, one call took 2.265 seconds and made 368,791 function calls. The recorded cumulative times overlap and must not be added together:

- `_term_in_text`: 13,803 calls, 1.142 seconds cumulative.
- `load_taxonomy`: 0.933 seconds cumulative, including term matching.
- `_classify_requirements`: two calls, 0.873 seconds cumulative.
- `_detect_mandatory_qualifications`: 0.654 seconds cumulative.
- `_sentences`: 44 calls, 0.572 seconds cumulative.

Prioritize a shared maximum extracted/pasted text length, then parse sentences once per document and reuse them across requirement classification and evidence extraction. Cache term patterns and evaluate taxonomy caching with deliberate invalidation. Measure again before choosing deployment worker counts or bulk concurrency. Preserve scores and evidence maps with regression comparisons when optimizing.

## Reproduction and limits

Run `.venv/Scripts/python.exe scripts/stress_ats_scoring.py`; use `--profile` for profiling after the first run creates and seeds the isolated benchmark database. The script uses minimal Django settings to avoid the missing local Sentry dependency. It does not load production settings, secrets, or telemetry integrations.

Environment: Windows 11, Python 3.12.10, Django 6.0.1, SQLite. Fixture generation, schema migration, seeding, and model import are outside the reported scoring timings. No HTTP authentication, storage, malware scan, persistence of analysis results, AI assistance, emails, network job fetching, or deployed-server load was tested. Database taxonomy lookup errors can fall back inside the production scorer; the initial taxonomy counts verified tables and seed availability, but the benchmark does not instrument every query for hidden fallback.

Artifacts: `scripts/stress_ats_scoring.py`, `docs/ATS_STRESS_RESULTS_2026-10-08.json`, `docs/ATS_STRESS_PROFILE_2026-10-08.txt`, and `docs/ats_stress_benchmark.sqlite3`.
