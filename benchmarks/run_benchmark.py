"""Single entry point: load data + run every required workload against one
platform, emit results/<platform>.json. Run once per platform (see
scripts/run_all.sh to run all of them back to back).

    python -m benchmarks.run_benchmark --platform cognodb
"""
import argparse
import csv
import json
import os
import time

from benchmarks.config import load_platform
from benchmarks.platforms.bolt_platform import BoltPlatform
from benchmarks.platforms.arango_platform import ArangoPlatform
from benchmarks.platforms.falkordb_platform import FalkorDBPlatform
from benchmarks.workloads import (
    run_latency_workload,
    run_filtered_lookup,
    run_aggregation,
    run_mixed_workload,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
DEPARTMENTS = ["engineering", "sales", "legal", "trading", "hr", "finance", "ops", "exec"]


def make_factory(kind: str, cfg: dict):
    if kind == "bolt":
        return lambda: BoltPlatform(cfg["uri"], cfg["user"], cfg["password"])
    if kind == "falkordb":
        return lambda: FalkorDBPlatform(
            cfg["host"], cfg["port"], cfg["username"], cfg["password"], cfg["graph"], cfg["ssl"]
        )
    return lambda: ArangoPlatform(cfg["uri"], cfg["user"], cfg["password"], cfg["db"])


def read_csvs():
    with open(os.path.join(DATA_DIR, "nodes.csv")) as f:
        nodes = [{"id": int(r["id"]), "department": r["department"]} for r in csv.DictReader(f)]
    with open(os.path.join(DATA_DIR, "edges.csv")) as f:
        edges = [(int(r["src"]), int(r["dst"])) for r in csv.DictReader(f)]
    return nodes, edges


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=[
        "cognodb", "aura", "memgraph", "falkordb", "arango",
    ])
    parser.add_argument("--skip-load", action="store_true", help="reuse already-loaded data")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--concurrency-levels", type=int, nargs="+", default=[1, 10, 40])
    args = parser.parse_args()

    kind, cfg = load_platform(args.platform)
    factory = make_factory(kind, cfg)
    platform = factory()

    result = {"platform": args.platform, "kind": kind, "started_at": time.time()}

    if not args.skip_load:
        nodes, edges = read_csvs()
        platform.clear()
        platform.create_indexes()
        node_count, rel_count, elapsed = platform.load(nodes, edges)
        result["loading"] = {
            "node_count": node_count,
            "relationship_count": rel_count,
            "wall_clock_s": elapsed,
            "nodes_per_s": node_count / elapsed,
            "relationships_per_s": rel_count / elapsed,
        }
        print(f"Loaded {node_count} nodes / {rel_count} rels in {elapsed:.1f}s")
    else:
        nodes, _ = read_csvs()

    node_ids = [n["id"] for n in nodes]

    print("Running traversal workloads...")
    result["traversals"] = {
        f"hop_{h}": run_latency_workload(platform, kind, f"hop_{h}", node_ids, args.iterations)
        for h in (1, 2, 3)
    }

    print("Running lookup workloads...")
    result["lookups"] = {
        "point_lookup": run_latency_workload(platform, kind, "point_lookup", node_ids, args.iterations),
        "filtered_lookup": run_filtered_lookup(platform, kind, DEPARTMENTS, args.iterations),
    }

    print("Running aggregation workload...")
    result["aggregation"] = run_aggregation(platform, kind)

    platform.close()

    print("Running mixed read/write concurrency sweep...")
    result["mixed_workload"] = [
        run_mixed_workload(factory, kind, node_ids, concurrency=c)
        for c in args.concurrency_levels
    ]

    result["finished_at"] = time.time()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, f"{args.platform}.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
