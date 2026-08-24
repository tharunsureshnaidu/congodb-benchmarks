"""Combine results/<platform>.json files into results/summary.json, the single
file the Next.js dashboard reads. Run after run_benchmark.py for each platform.
"""
import glob
import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def main():
    summary = {}
    for path in glob.glob(os.path.join(RESULTS_DIR, "*.json")):
        name = os.path.basename(path).removesuffix(".json")
        if name in ("summary", "summary.example"):
            continue
        with open(path) as f:
            summary[name] = json.load(f)

    out_path = os.path.join(RESULTS_DIR, "summary.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote {out_path} ({len(summary)} platforms)")


if __name__ == "__main__":
    main()
