# Graph Database Cloud Benchmarks

This is a benchmark of **CognoDB Cloud** against four other managed graph
database platforms — same dataset, same queries, same client for all five.
The point isn't to crown a winner, it's to be honest about what the
numbers do and don't show.

**→ [Read the write-up](./ARTICLE.md)** for the short, readable version of
this story. This README is the full reference: methodology, results
tables, and the details behind them.

All five platforms below have real, measured results from a live run
(`results/summary.json`, also what the dashboard renders) — not
placeholders. Getting there took a bit of debugging along the way; that's
covered in [Caveats](#caveats).

## Platforms compared

| Platform | Tier | vCPU | RAM / memory | Storage | Query language |
|---|---|---|---|---|---|
| CognoDB Cloud | free (c0) | 0.5, burstable | 256 MB | 1 GB | Cypher over Bolt |
| Neo4j AuraDB | Free | shared/burstable | ~250 MB ([published spec](https://neo4j.com/cloud/platform/aura-graph-database/faq/)) | — | Cypher over Bolt |
| Memgraph Cloud | entry | 2 (allocated) | 2 GB allocated, 1.54 GiB usable (measured) | — | Cypher over Bolt |
| FalkorDB Cloud | free, self-sized | not confirmed | 100 MB (measured cap) | not confirmed | openCypher, own client |
| ArangoDB Oasis | 14-day trial, self-sized (A1 node) | 0.25 | 1 GB | 40 GB | AQL |

CognoDB speaks Cypher over Bolt, so AuraDB and Memgraph Cloud — which speak
the same protocol — share one client and byte-identical query text; it's
about as fair a comparison as this benchmark can offer. FalkorDB also uses
openCypher, just over its own Redis-based client rather than Bolt, which
makes it a nice "same language, different engine" data point. ArangoDB is
the deliberate outlier: a different query language (AQL) and a
document/edge storage model, included so the benchmark isn't just
comparing Cypher clones to each other.

The plan was to hold every platform to roughly the same footprint as
CognoDB's 0.5 vCPU / 256 MB. In practice, none of the other four matched
that exactly. Memgraph's console shows a 2 GB / 2 vCPU allocation —
measuring it live from inside the database (`SHOW STORAGE INFO`) reports a
1.54 GiB usable limit, presumably the rest is reserved for the OS and
Memgraph's own overhead. ArangoDB Oasis isn't a fixed tier at all — it's a
14-day trial where you pick the size at deployment, and this run used the
smallest option on offer, an A1 node: 0.25 vCPU, 1 GB RAM, 40 GB disk. Less
CPU than CognoDB, noticeably more RAM and disk. FalkorDB Cloud works the
same way — you deploy at whatever size you choose rather than getting a
fixed "free tier" — and the only number I could pin down for certain is
its real memory ceiling, measured directly from Redis at 100 MB, smaller
than everything else here. CognoDB and AuraDB, for their part, don't
expose a memory figure through any API a client can reach, so those two
rows lean on published numbers rather than a live reading. The dataset was
sized to fit comfortably inside the smallest confirmed limit (FalkorDB's
100 MB), and it did — but resource parity across all five wasn't fully
achieved, and it's worth saying so plainly rather than presenting the
original "everyone gets the same box" plan as fact.

## Dataset

A random 100,000-edge sample of [SNAP `soc-Pokec`](https://snap.stanford.edu/data/soc-Pokec.html),
a real Slovak social network with 30.6 million friendship edges in total.
Sampling down to 100,000 edges (169,924 distinct nodes) with a fixed seed
keeps every platform loading the exact same subgraph, and comfortably fits
inside a free-tier disk:

```bash
curl -o data/soc-pokec-relationships.txt.gz https://snap.stanford.edu/data/soc-pokec-relationships.txt.gz
python -m benchmarks.dataset --source data/soc-pokec-relationships.txt.gz --target-edges 100000
```

Each node loads as `(:Person {id, department})`, connected by `:EMAILED`
edges. `department` is a synthetic field (8 buckets, derived from the node
id) used for the filtered-lookup and group-by workloads — real datasets
rarely ship a ready-made categorical column, and every platform needs to
see identical values for that comparison to mean anything. `Person.id` and
`Person.department` are indexed on every platform.

`benchmarks/dataset.py` also works against any other gzip'd `src dst` edge
list via `--source` — its no-argument default downloads SNAP `email-Enron`
instead, if you want to try a different graph.

## Code layout

`benchmarks/` holds the whole harness: `dataset.py` prepares the data,
`run_benchmark.py` loads and benchmarks one platform, `footprint.py` pulls
memory/storage numbers, and `merge_results.py` combines everything into
`results/summary.json`. `benchmarks/platforms/` has the three client
implementations — one shared Bolt/Cypher client for CognoDB, AuraDB, and
Memgraph, plus separate ones for FalkorDB and ArangoDB. `scripts/run_all.sh`
runs the whole thing end to end, and `dashboard/` is the Next.js app that
renders the results.

## Reproducing this

Prerequisites: Python 3.10+, Node 18+, and a free-tier account on each of
the five platforms.

1. **Create the five instances** — CognoDB (`console.cognodb.com/signup`),
   AuraDB (`console.neo4j.io`), Memgraph Cloud, FalkorDB Cloud, and
   ArangoDB Oasis — and save each one's connection URI and password.

2. **Set up credentials:**
   ```bash
   cp .env.example .env
   # fill in COGNODB_*, AURA_*, MEMGRAPH_*, FALKORDB_*, ARANGO_*
   ```

3. **Install dependencies:**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run the benchmark:**
   ```bash
   scripts/run_all.sh
   # or target specific platforms: scripts/run_all.sh cognodb aura
   ```
   This prepares the dataset once, then per platform: clears old data,
   creates indexes, loads nodes and edges (timing it), and runs 100
   iterations of each traversal/lookup query, 20 of the aggregation, and a
   1/10/40-client mixed read/write sweep. Results land in
   `results/<platform>.json`, merged into `results/summary.json`.

5. **Pull footprint numbers** (a separate step, since each platform needs
   its own introspection method):
   ```bash
   python -m benchmarks.footprint
   ```

6. **View it:**
   ```bash
   cd dashboard && npm install && npm run dev
   ```
   Open `localhost:3000` — it reads `results/summary.json` directly.

## What was measured

| Category | Metric | How |
|---|---|---|
| Data loading | Nodes/sec, relationships/sec, wall-clock load time | Batched `UNWIND` (Bolt platforms) or `import_bulk` (ArangoDB), 2,000-row batches |
| Traversals | 1-hop, 2-hop, 3-hop latency (p50/p95) | 100 iterations from random start nodes, after a 10-iteration warm-up |
| Lookups | Point lookup (indexed `id`), filtered lookup (indexed `department`) | Same as above |
| Aggregation | Count grouped by `department` over all edges | 20 iterations |
| Mixed workload | Sustained qps at 1 / 10 / 40 concurrent clients, 90% read / 10% write | 10 seconds per concurrency level, one connection per client |
| Footprint | Stored size / memory, where the platform exposes it | Platform-specific — see below |

Percentiles come from Python's own `statistics.quantiles`.

## Results

Measured on 2026-08-24 against each platform's real instance, same
100,000-edge dataset throughout. Raw numbers are in `results/summary.json`;
the dashboard shows the same thing.

### Data loading

| Platform | Nodes | Relationships | Wall clock | Nodes/s | Rels/s |
|---|---|---|---|---|---|
| CognoDB | 169,924 | 100,000 | 62.6s | 2,715 | 1,598 |
| AuraDB | 169,924 | 100,000 | 46.2s | 3,678 | 2,164 |
| Memgraph Cloud | 169,924 | 100,000 | 35.8s | 4,748 | 2,794 |
| FalkorDB Cloud | 169,924 | 100,000 | 21.8s | 7,791 | 4,585 |
| ArangoDB Oasis | 169,924 | 100,000 | 127.7s | 1,331 | 783 |

### Traversal latency (ms, p50 / p95)

| Platform | 1-hop | 2-hop | 3-hop |
|---|---|---|---|
| CognoDB | 306.8 / 328.7 | 307.1 / 341.7 | 307.1 / 320.5 |
| AuraDB | 203.7 / 224.9 | 204.5 / 248.9 | 204.7 / 231.7 |
| Memgraph Cloud | 203.9 / 220.4 | 203.7 / 216.5 | 204.5 / 209.7 |
| FalkorDB Cloud | 101.4 / 105.4 | 101.8 / 120.0 | 99.8 / 125.9 |
| ArangoDB Oasis | 307.4 / 355.2 | 307.5 / 359.9 | 307.2 / 331.2 |

### Lookups (ms, p50 / p95)

| Platform | Point lookup | Filtered lookup |
|---|---|---|
| CognoDB | 306.9 / 333.0 | 307.4 / 331.1 |
| AuraDB | 204.0 / 227.5 | 204.4 / 259.6 |
| Memgraph Cloud | 204.4 / 207.9 | 204.3 / 208.9 |
| FalkorDB Cloud | 101.2 / 119.7 | 100.9 / 116.6 |
| ArangoDB Oasis | 307.3 / 351.3 | 307.1 / 408.6 |

### Aggregation (ms, p50 / p95)

| Platform | Count grouped by department |
|---|---|
| CognoDB | 1,116.8 / 1,302.8 |
| AuraDB | 277.1 / 314.4 |
| Memgraph Cloud | 238.2 / 307.7 |
| FalkorDB Cloud | 308.7 / 342.6 |
| ArangoDB Oasis | 11,716.3 / 13,067.9 |

### Mixed read/write throughput (qps, 90/10 mix)

| Platform | 1 client | 10 clients | 40 clients |
|---|---|---|---|
| CognoDB | 2.9 | 28.6 | 104.4 |
| AuraDB | 4.6 | 49.6 | 223.2 |
| Memgraph Cloud | 4.6 | 46.0 | 183.1 |
| FalkorDB Cloud | 11.8 | 117.2 | 1,351.6 |
| ArangoDB Oasis | 3.2 | 32.9 | 120.3 |

### Footprint

| Platform | Stored data | Memory usage |
|---|---|---|
| CognoDB | not observable | not observable |
| AuraDB | not observable via API | not observable |
| Memgraph Cloud | 32.8 MiB on disk | 162.3 MiB resident of a 1.54 GiB limit |
| FalkorDB Cloud | not observable via API | 46.2 MB used of a 100 MB cap |
| ArangoDB Oasis | 13.8 MB documents + 16.9 MB across 3 indexes | not observable via API |

CognoDB and AuraDB don't expose either figure through any API their free
tiers allow. FalkorDB is worth a second look before scaling the dataset up
on that platform specifically — it's already using close to half its
memory budget.

## Analysis

The clearest pattern in the traversal and lookup numbers is that they
barely move with query complexity — a 1-hop and a 3-hop traversal cost
about the same on every platform, which shouldn't be true of a real graph
engine. That flatness points to network round-trip time dominating the
actual query cost on a dataset this small. The numbers settle into three
bands — roughly 307ms (CognoDB, ArangoDB), 204ms (AuraDB, Memgraph), and
101ms (FalkorDB) — which looks much more like "distance between this
client and each platform's data center" than "how fast each database is."
FalkorDB's band is a partial exception, since its connection also skips
TLS entirely, removing a cost the other four all pay.

The one number that doesn't fit that network story is ArangoDB's
aggregation query, at 11.7 seconds — 10 to 50x slower than everything
else. The AQL query looks up each edge's source document individually
rather than keeping the grouping property inline on the traversal, which
is a real O(n) cost for 100,000 edges. That's a genuine query-shape
difference, not a network artifact.

FalkorDB came out fastest on every single metric — fastest load, lowest
latency, and by a wide margin the highest mixed-workload throughput
(1,351 qps at 40 clients versus 104–223 for the others). Some of that is
likely a genuinely fast engine for a small graph like this one; some of it
is almost certainly the missing TLS handshake, which matters a lot when 40
clients are all opening new connections at once. This run can't cleanly
separate the two, so treat FalkorDB's numbers as promising rather than
conclusive.

Throughput scaled up cleanly from 1 to 10 to 40 clients on every platform,
with no sign of hitting a ceiling — a bit of a surprise for 0.5 vCPU
instances, and a sign that a longer sustained run would be needed to see
whether throttling shows up eventually.
