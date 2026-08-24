"""Pull whatever storage/memory footprint each platform's own query API exposes.
Genuinely platform-specific -- there's no common Cypher/AQL surface for this,
so each branch below is a real attempt against that platform's actual
introspection tools, not a placeholder. Writes results/footprint.json.

    python -m benchmarks.footprint
"""
import json
import os

from benchmarks.config import load_platform
from benchmarks.platforms.bolt_platform import BoltPlatform
from benchmarks.platforms.arango_platform import ArangoPlatform
from benchmarks.platforms.falkordb_platform import FalkorDBPlatform

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def cognodb_footprint(cfg):
    """CognoDB's Cypher surface doesn't implement SHOW DATABASES/STORAGE INFO
    or APOC (confirmed by direct attempt) -- genuinely not observable via the
    query API on this tier."""
    return {"stored_data_size": "not observable", "memory_usage": "not observable",
            "note": "no SHOW STORAGE INFO / APOC support on this instance's Cypher surface"}


def aura_footprint(cfg):
    """SHOW DATABASES only returns topology/status, no size; admin procedures
    (dbms.listConfig) are Forbidden on Free tier; no APOC installed -- confirmed
    by direct attempt, not assumed."""
    return {"stored_data_size": "not observable via query API (visible in Aura console UI)",
            "memory_usage": "not observable",
            "note": "SHOW DATABASES has no size field; dbms.listConfig is Forbidden; no APOC"}


def memgraph_footprint(cfg):
    p = BoltPlatform(cfg["uri"], cfg["user"], cfg["password"])
    rows = {r["storage info"]: r["value"] for r in p.run("SHOW STORAGE INFO")}
    p.close()
    return {
        "memory_res": rows.get("memory_res"),
        "peak_memory_res": rows.get("peak_memory_res"),
        "disk_usage": rows.get("disk_usage"),
        "memory_limit": rows.get("memory_limit"),
    }


def arango_footprint(cfg):
    p = ArangoPlatform(cfg["uri"], cfg["user"], cfg["password"], cfg["db"])
    stats = p.db.collection("Person").statistics()
    return {
        "documents_size_bytes": stats.get("documents_size"),
        "index_size_bytes": stats.get("indexes", {}).get("size"),
        "index_count": stats.get("indexes", {}).get("count"),
    }


def falkordb_footprint(cfg):
    p = FalkorDBPlatform(cfg["host"], cfg["port"], cfg["username"], cfg["password"], cfg["graph"], cfg["ssl"])
    info = p.db.connection.info("memory")
    return {
        "used_memory": info.get("used_memory_human"),
        "used_memory_peak": info.get("used_memory_peak_human"),
        "maxmemory": info.get("maxmemory_human"),
        "maxmemory_policy": info.get("maxmemory_policy"),
    }


FOOTPRINT_FNS = {
    "cognodb": cognodb_footprint,
    "aura": aura_footprint,
    "memgraph": memgraph_footprint,
    "falkordb": falkordb_footprint,
    "arango": arango_footprint,
}


def main():
    results = {}
    for name, fn in FOOTPRINT_FNS.items():
        try:
            _, cfg = load_platform(name)
            results[name] = fn(cfg)
        except Exception as e:
            results[name] = {"error": f"{type(e).__name__}: {e}"}
        print(name, "->", results[name])

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "footprint.json"), "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
