"""Isolated local ATS benchmark; no production data, stored uploads, or AI calls."""
import io
import json
import math
import platform
import statistics
import sys
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from django.conf import settings
settings.configure(
    SECRET_KEY="local-benchmark-only", USE_TZ=True,
    INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes", "accounts",
                    "subscriptions", "payments", "governance", "growth", "ats"],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3",
               "NAME": str(ROOT / "docs" / "ats_stress_benchmark.sqlite3")}},
)
import django
django.setup()
from django.db import connection, connections
from django.core.files.uploadedfile import SimpleUploadedFile
from docx import Document
from ats.engine import ats_engine
from ats.scoring import calculate_score_details, validate_job_description
from ats.models import Skill, Qualification, RoleTemplate
from scripts.benchmark_cv_pipeline import CV_TEXT, JOB_TEXT

TITLE = "Senior Recruitment Operations Specialist"
DEV_CV = CV_TEXT.replace("recruitment", "software engineering").replace("Recruitment", "Software Engineering").replace("Excel", "Python Django PostgreSQL API Git")
DEV_JOB = "Software Engineer. About the role: Responsibilities include developing Python Django API services and PostgreSQL SQL databases. Required skills are Python, Django, SQL, Git, communication and software engineering experience. Candidates must demonstrate implemented services and measurable improvements."
OTHER_CV = CV_TEXT.replace("recruitment", "patient care").replace("Recruitment", "Dental").replace("SQL", "radiography").replace("Excel", "dentistry")
CASES = {
    "recruitment_match": (CV_TEXT, JOB_TEXT, TITLE),
    "software_match": (DEV_CV, DEV_JOB, "Software Engineer"),
    "dental_vs_software": (OTHER_CV, DEV_JOB, "Software Engineer"),
    "keyword_stuffing": ("Python Django SQL Git communication " * 50, DEV_JOB, "Software Engineer"),
    "empty_cv": ("", JOB_TEXT, TITLE),
    "empty_job": (CV_TEXT, "", TITLE),
    "unicode": (CV_TEXT + "\nRésumé café 数据分析 🚀", JOB_TEXT, TITLE),
    "long_token": (CV_TEXT + "\n" + "x" * 100000, JOB_TEXT, TITLE),
    "long_cv": ((CV_TEXT * 80)[:100000], JOB_TEXT, TITLE),
    "long_job": (CV_TEXT, (JOB_TEXT * 160)[:100000], TITLE),
}

def run_pair(pair):
    started = time.perf_counter()
    try:
        cv, job, title = pair
        result = calculate_score_details(cv, job, title)
        return {"ms": (time.perf_counter() - started) * 1000, "score": result["score"],
                "cv_valid": ats_engine.validate_cv_text(cv)[0],
                "job_valid": validate_job_description(job)[0]}
    except Exception as exc:
        return {"ms": (time.perf_counter() - started) * 1000, "error": repr(exc)}
    finally:
        connections.close_all()

def summarize(rows, seconds):
    times = sorted(r["ms"] for r in rows)
    return {"requests": len(rows), "errors": [r["error"] for r in rows if "error" in r],
            "p50_ms": round(statistics.median(times), 2),
            "p95_ms": round(times[math.ceil(len(times) * .95) - 1], 2),
            "max_ms": round(max(times), 2), "throughput_per_second": round(len(rows) / seconds, 2)}

def main():
    from django.core.management import call_command
    call_command("migrate", verbosity=0, interactive=False)
    call_command("seed_taxonomy", verbosity=0)
    report = {"scope": "Local extraction, validation and scoring; project-seeded taxonomy in an isolated SQLite database. No production data, HTTP, external API, malware scan, or production capacity measurement.",
              "environment": {"python": platform.python_version(), "django": django.get_version(), "platform": platform.platform()},
              "taxonomy": {"skills": Skill.objects.count(), "qualifications": Qualification.objects.count(), "roles": RoleTemplate.objects.count()},
              "cases": {}, "concurrency": [], "scaling": [], "extraction": {}}
    for name, pair in CASES.items():
        rows = [run_pair(pair) for _ in range(5)]
        report["cases"][name] = {**summarize(rows, sum(r["ms"] for r in rows) / 1000),
                                  "scores": sorted(set(r["score"] for r in rows if "score" in r)),
                                  "cv_valid": rows[0].get("cv_valid"), "job_valid": rows[0].get("job_valid")}
        print(name, report["cases"][name]["p95_ms"], flush=True)
    normal = list(CASES.values())[:3]
    for workers in (1, 4, 8, 16):
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(run_pair, [normal[i % 3] for i in range(96)]))
        report["concurrency"].append({"workers": workers, **summarize(rows, time.perf_counter() - started)})
        print("workers", workers, report["concurrency"][-1], flush=True)
    for size in (2000, 10000, 50000, 100000):
        pair = ((CV_TEXT * (size // len(CV_TEXT) + 1))[:size],
                (JOB_TEXT * (size // len(JOB_TEXT) + 1))[:size], TITLE)
        rows = [run_pair(pair) for _ in range(3)]
        tracemalloc.start()
        memory_row = run_pair(pair)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        report["scaling"].append({"chars_per_document": size, **summarize(rows, sum(r["ms"] for r in rows) / 1000),
                                   "peak_traced_python_mib": round(peak / 1024**2, 2), "memory_run_error": memory_row.get("error")})
        print("size", size, report["scaling"][-1], flush=True)
    doc = Document()
    for line in CV_TEXT.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    for ext, content in (("txt", CV_TEXT.encode()), ("docx", buf.getvalue()), ("pdf", b"invalid pdf")):
        started = time.perf_counter()
        try:
            extracted = ats_engine.extract_text_from_upload(SimpleUploadedFile("synthetic." + ext, content))
            report["extraction"][ext] = {"valid": ats_engine.validate_cv_text(extracted)[0], "chars": len(extracted)}
        except Exception as exc:
            report["extraction"][ext] = {"rejected": type(exc).__name__}
        report["extraction"][ext]["ms"] = round((time.perf_counter() - started) * 1000, 2)
    report["total_scoring_calls"] = 50 + 384 + 16
    path = ROOT / "docs" / "ATS_STRESS_RESULTS_2026-10-08.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Saved", path, flush=True)

if __name__ == "__main__":
    if "--profile" in sys.argv:
        import cProfile
        import pstats
        profiler = cProfile.Profile()
        profiler.enable()
        run_pair((CV_TEXT, JOB_TEXT * 16, TITLE))
        profiler.disable()
        with (ROOT / "docs" / "ATS_STRESS_PROFILE_2026-10-08.txt").open("w") as output:
            pstats.Stats(profiler, stream=output).strip_dirs().sort_stats("cumulative").print_stats(18)
    else:
        main()
