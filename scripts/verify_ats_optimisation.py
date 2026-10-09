"""Compare scoring output and local concurrency against the committed scorer."""
import json
import statistics
import subprocess
import time
import types
from concurrent.futures import ThreadPoolExecutor

from scripts.stress_ats_scoring import CASES, CV_TEXT, JOB_TEXT, TITLE, ROOT, run_pair
from ats.scoring import calculate_score_details


def main():
    source = subprocess.check_output(["git", "show", "a78b494:ats/scoring.py"], cwd=ROOT, text=True)
    baseline = types.ModuleType("ats.baseline_scoring")
    baseline.__package__ = "ats"
    exec(compile(source, "baseline_scoring.py", "exec"), baseline.__dict__)
    pairs = list(CASES.items())[:4] + [("unicode", CASES["unicode"])]
    pairs.append(("large_valid", ((CV_TEXT * 30)[:40000], (JOB_TEXT * 30)[:15000], TITLE)))
    comparisons = []
    for name, pair in pairs:
        timings = {}
        outputs = []
        for label, scorer in (("before", baseline.calculate_score_details), ("after", calculate_score_details)):
            samples = []
            for _ in range(3):
                started = time.perf_counter()
                output = scorer(*pair)
                samples.append((time.perf_counter() - started) * 1000)
            outputs.append(output)
            timings[label + "_median_ms"] = round(statistics.median(samples), 2)
        assert outputs[0] == outputs[1], name + " changed scoring output"
        comparisons.append({"case": name, "score": outputs[1]["score"], "identical_output": True, **timings})
    rejected = {name: run_pair(CASES[name]) for name in ("empty_cv", "empty_job", "long_token", "long_cv", "long_job")}
    assert all("error" in row for row in rejected.values())
    concurrency = []
    for workers in (1, 4, 16):
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(run_pair, [CASES["recruitment_match"]] * 32))
        assert all(row.get("score") == comparisons[0]["score"] for row in rows)
        concurrency.append({"workers": workers, "requests": len(rows), "errors": 0,
                            "elapsed_seconds": round(time.perf_counter() - started, 3),
                            "max_ms": round(max(row["ms"] for row in rows), 2)})
    report = {"scope": "Local SQLite scorer comparison; no external AI or production capacity measurement.",
              "comparisons": comparisons, "rejected_inputs": rejected, "concurrency": concurrency}
    path = ROOT / "docs" / "ATS_OPTIMISATION_RESULTS_2026-10-09.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
