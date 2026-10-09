"""Synthetic concurrency benchmark for MyValidCV's extraction/scoring pipeline.

This does not write CVs or results to the database. It exercises the same text
extraction, CV validation, job-ad validation, and deterministic ATS scoring used
by the application, with a shared start gate to model simultaneous requests.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

from ats.engine import ats_engine  # noqa: E402
from ats.scoring import calculate_score_details, validate_job_description  # noqa: E402


CV_TEXT = """Alex Morgan
alex.morgan@example.com | +44 7700 900123 | linkedin.com/in/alexmorgan

PROFILE
Experienced recruitment operations specialist with a record of delivering
high-volume hiring projects, improving processes, and supporting hiring teams.

SKILLS
Recruitment, onboarding, data analysis, Excel, SQL, project management,
communication, leadership, customer service, compliance and reporting.

EXPERIENCE
Senior Recruitment Coordinator, Example Ltd, 2021-present
Managed recruitment pipelines and coordinated interview schedules for several
departments. Implemented structured screening and reporting, reducing review
time by 30 percent. Led weekly stakeholder meetings and trained colleagues on
new systems. Analysed hiring data using Excel and SQL and delivered dashboards
to managers. Supported compliance checks and maintained accurate records.

Recruitment Assistant, Sample Group, 2018-2021
Supported candidate screening, onboarding and customer enquiries. Created
process documentation, improved data quality and coordinated multiple projects.
Worked with teams to resolve scheduling problems and report outcomes.

EDUCATION
BA Business Management, Example University, 2018
Certificate in Recruitment Practice, 2020

ACHIEVEMENTS
Delivered a high-volume campaign on time, improved candidate communications,
and reduced administrative errors through documented quality checks.
"""

JOB_TEXT = """Senior Recruitment Operations Specialist
About the role: We require an experienced recruitment professional to manage
high-volume hiring operations and support hiring managers. Responsibilities
include candidate screening, interview scheduling, onboarding, stakeholder
communication, compliance records, data analysis and process improvement.
Essential skills include recruitment, Excel, project management, communication
and reporting. Experience using SQL and producing hiring dashboards is preferred.
The successful candidate must demonstrate measurable process improvements and
the ability to coordinate several departments and meet deadlines.
"""


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def analyse_one(index: int, gate: threading.Barrier) -> dict:
    upload = SimpleUploadedFile(
        f"synthetic-{index}.txt",
        CV_TEXT.encode("utf-8"),
        content_type="text/plain",
    )
    gate.wait()
    started = time.perf_counter()
    extracted = ats_engine.extract_text_from_upload(upload)
    cv_ok, cv_message = ats_engine.validate_cv_text(extracted)
    job_ok, job_message = validate_job_description(JOB_TEXT)
    if not cv_ok or not job_ok:
        raise RuntimeError(cv_message if not cv_ok else job_message)
    score = calculate_score_details(extracted, JOB_TEXT, "Senior Recruitment Operations Specialist")
    return {
        "latency_ms": (time.perf_counter() - started) * 1000,
        "score": score["score"],
    }


def run_level(concurrency: int, repeats: int) -> dict:
    all_latencies: list[float] = []
    failures: list[str] = []
    run_durations: list[float] = []
    scores: list[int] = []

    for repeat in range(repeats):
        gate = threading.Barrier(concurrency + 1)
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(analyse_one, (repeat * concurrency) + i, gate) for i in range(concurrency)]
            started = time.perf_counter()
            gate.wait()
            for future in as_completed(futures):
                try:
                    result = future.result()
                    all_latencies.append(result["latency_ms"])
                    scores.append(result["score"])
                except Exception as exc:  # benchmark reports rather than hides failures
                    failures.append(f"{type(exc).__name__}: {exc}")
            run_durations.append(time.perf_counter() - started)

    successes = len(all_latencies)
    total = concurrency * repeats
    mean_duration = statistics.mean(run_durations)
    return {
        "concurrency": concurrency,
        "requests": total,
        "successes": successes,
        "failures": len(failures),
        "wall_time_mean_ms": round(mean_duration * 1000, 2),
        "throughput_per_second": round((concurrency / mean_duration) if mean_duration else 0, 2),
        "latency_p50_ms": round(statistics.median(all_latencies), 2) if all_latencies else None,
        "latency_p95_ms": round(percentile(all_latencies, 0.95), 2) if all_latencies else None,
        "latency_max_ms": round(max(all_latencies), 2) if all_latencies else None,
        "consistent_score": len(set(scores)) == 1 if scores else False,
        "score": scores[0] if scores else None,
        "sample_errors": failures[:3],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", default="1,4,10,25,50")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    levels = [int(value) for value in args.levels.split(",") if value.strip()]

    # Warm caches and database connections before recording measurements.
    warm_gate = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(analyse_one, -1, warm_gate)
        warm_gate.wait()
        future.result()

    results = [run_level(level, args.repeats) for level in levels]
    print(json.dumps({"repeats": args.repeats, "results": results}, indent=2))


if __name__ == "__main__":
    main()
