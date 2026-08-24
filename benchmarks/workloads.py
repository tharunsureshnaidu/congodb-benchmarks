"""Query definitions (per query language) and latency-stat helpers.

Same logical queries everywhere: only the syntax differs between Cypher
(bolt platforms) and AQL (Arango). Percentiles use stdlib `statistics`
(no numpy/pandas dependency needed for a handful of quantiles).
"""
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

QUERIES = {
    "bolt": {
        "point_lookup": "MATCH (p:Person {id: $id}) RETURN p",
        "filtered_lookup": "MATCH (p:Person {department: $department}) RETURN p LIMIT 100",
        "hop_1": "MATCH (p:Person {id: $id})-[:EMAILED]->(x) RETURN count(x) AS c",
        "hop_2": "MATCH (p:Person {id: $id})-[:EMAILED*2]->(x) RETURN count(x) AS c",
        "hop_3": "MATCH (p:Person {id: $id})-[:EMAILED*3]->(x) RETURN count(x) AS c",
        "aggregation": (
            "MATCH (p:Person)-[r:EMAILED]->() "
            "RETURN p.department AS department, count(r) AS sent "
            "ORDER BY sent DESC"
        ),
        "write": "MATCH (p:Person {id: $id}) SET p.last_seen = $ts",
    },
    "arango": {
        "point_lookup": "FOR p IN Person FILTER p.node_id == @id RETURN p",
        "filtered_lookup": "FOR p IN Person FILTER p.department == @department LIMIT 100 RETURN p",
        "hop_1": (
            "FOR v IN 1..1 OUTBOUND CONCAT('Person/', @id) EMAILED "
            "COLLECT WITH COUNT INTO c RETURN c"
        ),
        "hop_2": (
            "FOR v IN 2..2 OUTBOUND CONCAT('Person/', @id) EMAILED "
            "COLLECT WITH COUNT INTO c RETURN c"
        ),
        "hop_3": (
            "FOR v IN 3..3 OUTBOUND CONCAT('Person/', @id) EMAILED "
            "COLLECT WITH COUNT INTO c RETURN c"
        ),
        "aggregation": (
            "FOR e IN EMAILED "
            "LET p = DOCUMENT(e._from) "
            "COLLECT department = p.department WITH COUNT INTO sent "
            "SORT sent DESC RETURN {department, sent}"
        ),
        "write": "FOR p IN Person FILTER p.node_id == @id UPDATE p WITH {last_seen: @ts} IN Person",
    },
}

# FalkorDB speaks openCypher, so the query text above is identical -- no
# separate dialect to maintain.
QUERIES["falkordb"] = QUERIES["bolt"]


def percentiles(samples_ms: list[float]) -> dict:
    if not samples_ms:
        return {"p50": None, "p95": None}
    sorted_samples = sorted(samples_ms)
    quantiles = statistics.quantiles(sorted_samples, n=100, method="inclusive")
    return {
        "p50": quantiles[49],
        "p95": quantiles[94],
        "min": sorted_samples[0],
        "max": sorted_samples[-1],
        "n": len(sorted_samples),
    }


def timed_run(platform, query: str, params: dict) -> float:
    start = time.perf_counter()
    platform.run(query, params)
    return (time.perf_counter() - start) * 1000


def run_latency_workload(platform, kind: str, query_key: str, node_ids: list[int],
                          iterations: int = 100, warmup: int = 10, param_key: str = "id") -> dict:
    """Run `iterations` samples of one query against random start nodes, after warm-up."""
    query = QUERIES[kind][query_key]
    for _ in range(warmup):
        node_id = random.choice(node_ids)
        timed_run(platform, query, {param_key: node_id})

    samples = []
    for _ in range(iterations):
        node_id = random.choice(node_ids)
        samples.append(timed_run(platform, query, {param_key: node_id}))
    return percentiles(samples)


def run_filtered_lookup(platform, kind: str, departments: list[str], iterations: int = 100, warmup: int = 10) -> dict:
    query = QUERIES[kind]["filtered_lookup"]
    for _ in range(warmup):
        timed_run(platform, query, {"department": random.choice(departments)})
    samples = [
        timed_run(platform, query, {"department": random.choice(departments)})
        for _ in range(iterations)
    ]
    return percentiles(samples)


def run_aggregation(platform, kind: str, iterations: int = 20, warmup: int = 3) -> dict:
    query = QUERIES[kind]["aggregation"]
    for _ in range(warmup):
        timed_run(platform, query, {})
    samples = [timed_run(platform, query, {}) for _ in range(iterations)]
    return percentiles(samples)


def _mixed_worker(make_platform, kind: str, node_ids: list[int], write_ratio: float,
                   duration_s: float) -> int:
    """One simulated client: opens its own connection and hammers point-lookup
    reads with an occasional write, for `duration_s` seconds. Returns op count."""
    platform = make_platform()
    read_q = QUERIES[kind]["point_lookup"]
    write_q = QUERIES[kind]["write"]
    ops = 0
    deadline = time.perf_counter() + duration_s
    try:
        while time.perf_counter() < deadline:
            node_id = random.choice(node_ids)
            if random.random() < write_ratio:
                platform.run(write_q, {"id": node_id, "ts": ops})
            else:
                platform.run(read_q, {"id": node_id})
            ops += 1
    finally:
        platform.close()
    return ops


def run_mixed_workload(make_platform, kind: str, node_ids: list[int], concurrency: int,
                        write_ratio: float = 0.1, duration_s: float = 10.0) -> dict:
    """Sustained concurrent read/write throughput at a given client concurrency.
    `make_platform` is a zero-arg factory so each thread gets its own connection."""
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(_mixed_worker, make_platform, kind, node_ids, write_ratio, duration_s)
            for _ in range(concurrency)
        ]
        total_ops = sum(f.result() for f in futures)
    return {
        "concurrency": concurrency,
        "write_ratio": write_ratio,
        "duration_s": duration_s,
        "total_ops": total_ops,
        "throughput_qps": total_ops / duration_s,
    }
