"""Fetch/prepare the benchmark dataset: a plain-text gzip'd edge list
("src dst" per line, "#" comments allowed -- the standard SNAP format) is
turned into nodes.csv (id,department) and edges.csv (src,dst), capped to
TARGET_EDGES relationships so the dataset stays well inside every platform's
free-tier storage (see README's FalkorDB Cloud caveat).

Default source: SNAP email-Enron (auto-downloaded). Pass --source to point
at a different local .txt.gz edge list instead (e.g. a SNAP soc-Pokec file
such as profile.txt.gz) -- the sampling/CSV-writing logic is identical
either way, so swapping datasets is a one-flag change, not a rewrite.
"""
import argparse
import csv
import gzip
import os
import random
import urllib.request

SNAP_URL = "https://snap.stanford.edu/data/email-Enron.txt.gz"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_RAW_PATH = os.path.join(DATA_DIR, "email-Enron.txt.gz")
NODES_CSV = os.path.join(DATA_DIR, "nodes.csv")
EDGES_CSV = os.path.join(DATA_DIR, "edges.csv")

TARGET_EDGES = 100_000  # "1 lakh" -- keeps every platform's free tier comfortably under load
SAMPLE_SEED = 42  # fixed, so re-running produces the identical sampled subgraph

DEPARTMENTS = ["engineering", "sales", "legal", "trading", "hr", "finance", "ops", "exec"]


def department_for(node_id: int) -> str:
    return DEPARTMENTS[node_id % len(DEPARTMENTS)]


def download_default():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DEFAULT_RAW_PATH):
        print(f"Downloading {SNAP_URL} ...")
        urllib.request.urlretrieve(SNAP_URL, DEFAULT_RAW_PATH)
    else:
        print("Raw dataset already downloaded.")
    return DEFAULT_RAW_PATH


def read_edges(raw_path: str):
    edges = []
    with gzip.open(raw_path, "rt") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            src, dst = line.split()[:2]
            edges.append((int(src), int(dst)))
    return edges


def prepare(source_path: str | None = None, target_edges: int = TARGET_EDGES):
    """Parse a gzip'd edge list, sample down to `target_edges` relationships,
    and write nodes.csv / edges.csv covering only the nodes touched by that sample."""
    raw_path = source_path or download_default()
    edges = read_edges(raw_path)
    print(f"Parsed {len(edges)} relationships from {raw_path}")

    if len(edges) > target_edges:
        random.seed(SAMPLE_SEED)
        edges = random.sample(edges, target_edges)
        print(f"Sampled down to {len(edges)} relationships (seed={SAMPLE_SEED})")

    node_ids = sorted({n for edge in edges for n in edge})

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(NODES_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "department"])
        for nid in node_ids:
            w.writerow([nid, department_for(nid)])

    with open(EDGES_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src", "dst"])
        w.writerows(edges)

    print(f"Wrote {len(node_ids)} nodes -> {NODES_CSV}")
    print(f"Wrote {len(edges)} edges -> {EDGES_CSV}")
    return len(node_ids), len(edges)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="path to a local .txt.gz edge list (default: auto-download email-Enron)")
    parser.add_argument("--target-edges", type=int, default=TARGET_EDGES)
    args = parser.parse_args()
    prepare(args.source, args.target_edges)
