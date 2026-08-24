# Graph Database Cloud Benchmarks

A reproducible benchmark suite comparing **CognoDB Cloud** against four other
managed graph database platforms, on identical data, identical queries, and
identical resource limits.

**→ [Read the write-up](./ARTICLE.md)** for the readable version of this
story — what broke getting five "free tier" accounts online, and the
finding that free tiers aren't actually the same size. This README below is
the full technical reference: methodology, every metric, every table, every
caveat.

> **Status of the numbers in this repo:** all 5 platforms have **real
> measured results** from a single run on 2026-08-24
> (`results/summary.json`, also what the dashboard renders). Getting all
> five connected required working around two platform-specific quirks —
> Memgraph Cloud's self-signed cert and AuraDB's non-default username — plus
> discovering FalkorDB Cloud's public endpoint doesn't do TLS at all. Full
> details, plus what this run does and doesn't prove, are in
> [Honest caveats](#honest-caveats).

## Platforms compared

| Platform | Tier | vCPU | RAM / memory | Storage | Query language | Spec source |
|---|---|---|---|---|---|---|
| CognoDB Cloud | free (c0) | 0.5 (burstable) | 256 MB | 1 GB | Cypher over Bolt | assignment brief (authoritative for this instance) |
| Neo4j AuraDB | Free | shared/burstable, unspecified | ~250 MB | 200k nodes / 400k rels cap | Cypher over Bolt | [Neo4j AuraDB FAQ](https://neo4j.com/cloud/platform/aura-graph-database/faq/) — not independently confirmed via query API (see Footprint) |
| Memgraph Cloud | entry | not disclosed by platform | **1.54 GiB** (`memory_limit`, measured) | not disclosed | Cypher over Bolt | measured live via `SHOW STORAGE INFO` |
| FalkorDB Cloud | free | not disclosed by platform | **100 MB** (`maxmemory`, measured) | not disclosed | openCypher (FalkorDB client) | measured live via Redis `INFO memory` |
| ArangoDB Oasis | 14-day free trial | **user-selected at deployment** | **user-selected at deployment** | user-selected | AQL | [ArangoDB Oasis is a self-sized trial, not a fixed free tier](https://arangodb.com/2019/11/arangodb-oasis-a-fully-managed-multi-model-database-service/) — exact size picked for this run not recorded |

**Why these five:** CognoDB speaks Bolt/Cypher, so three of the four
comparison platforms (AuraDB, Memgraph Cloud, and FalkorDB Cloud for its
query text, if not its wire protocol) share *the same Cypher* — the fairest
possible comparison, since the query text itself is byte-identical across
those. AuraDB and Memgraph Cloud additionally share one client implementation
(`benchmarks/platforms/bolt_platform.py`) since both speak Bolt. FalkorDB
Cloud is a genuinely different engine underneath (a graph layer over Redis,
via its own client rather than a Bolt driver) while still using openCypher
syntax, which makes it a useful "same query language, different storage
engine" data point. ArangoDB is included because it's a credible,
widely-used *multi-model* graph database with a fully different query
language too (AQL, document+edge collections) — a contrast point rather than
"another Cypher clone."

**Resource parity — fairness analysis, not an assumption.** The original
plan was "pin everything to CognoDB's advertised 0.5 vCPU / 256 MB / 1 GB."
Actually measuring each platform's real footprint (see
[Footprint](#footprint) below) shows that didn't hold in practice:
**FalkorDB Cloud's real memory cap (100 MB) is smaller than CognoDB's, and
Memgraph Cloud's (1.54 GiB) is over 6x larger** — a genuine ~15x spread in
actual allocated memory across platforms marketed as comparable
free/entry tiers, not a hardware advantage anyone chose. Neither AuraDB's
nor CognoDB's own free-tier memory ceiling was independently confirmable
via their query APIs (both lack the admin procedures to report it — see
Footprint), so those two rows rely on published specs, not live
measurement. **ArangoDB Oasis is the least comparable of the five**: it
isn't a fixed free tier at all, it's a 14-day trial where the deployer
picks the instance size — this run's actual selected size wasn't recorded,
which is itself the honest caveat, not something to paper over. The
dataset (100,000 edges) was sized to fit comfortably even inside the
smallest *confirmed* real limit (FalkorDB's 100 MB) — it did — but the
resource-parity goal from section 3 of the brief was only partially met in
practice, and this table says so rather than presenting the original
uniform assumption as fact.

## Dataset

Source used for this run: [SNAP `soc-Pokec`](https://snap.stanford.edu/data/soc-Pokec.html)
relationships file (`soc-pokec-relationships.txt.gz`, 30,622,564 directed
friendship edges total), sampled down to **100,000 relationships / 169,924
nodes** with a fixed random seed (`benchmarks/dataset.py`, `SAMPLE_SEED=42`)
so every platform loads the identical sampled subgraph. Fetched via:
```bash
curl -o data/soc-pokec-relationships.txt.gz https://snap.stanford.edu/data/soc-pokec-relationships.txt.gz
python -m benchmarks.dataset --source data/soc-pokec-relationships.txt.gz --target-edges 100000
```
`benchmarks/dataset.py`'s no-argument default instead auto-downloads
[SNAP `email-Enron`](https://snap.stanford.edu/data/email-Enron.html) — any
gzip'd `src dst` edge list works via `--source`, the sampling/CSV-writing
logic doesn't care where the edges came from. Note: `soc-pokec-profiles.txt.gz`
(the *node attribute* file — completion %, gender, region, etc., 60 columns
per line) is **not** an edge list and is not used here; only the separate
`soc-pokec-relationships.txt.gz` friendship graph feeds this benchmark.
Capping at 100k rather than the assignment's full 100k–500k range is a
deliberate margin against the smallest platform tier (see the FalkorDB
Cloud caveat below).

Schema loaded into every platform:

```
(:Person {id: int, department: string})-[:EMAILED]->(:Person)
```

`department` is one of 8 synthetic buckets (`engineering`, `sales`, `legal`,
`trading`, `hr`, `finance`, `ops`, `exec`), assigned deterministically from
`node_id % 8` (see `benchmarks/dataset.py:department_for`) — real-world graphs
rarely ship a ready-made categorical column, and every platform must see
*exactly* the same values for the filtered-lookup and aggregation workloads to
be comparable, so deriving it from the id beats sourcing a second dataset.

Indexed properties on every platform: `Person.id` (unique-ish lookup key) and
`Person.department` (filtered lookup / group-by).

## Repository layout

```
ARTICLE.md               # readable write-up for a general technical audience
README.md                # this file -- full methodology + results reference
benchmarks/
  dataset.py           # downloads/reads a .txt.gz edge list, samples to 100k edges, writes data/nodes.csv + data/edges.csv
  config.py             # reads platform credentials from environment variables
  workloads.py          # Cypher + AQL query text, percentile stats, mixed-workload runner
  run_benchmark.py       # CLI: load + benchmark one platform, write results/<platform>.json
  merge_results.py      # combine per-platform JSON into results/summary.json
  footprint.py           # pull real storage/memory footprint per platform, write results/footprint.json
  platforms/
    bolt_platform.py    # shared client for CognoDB, AuraDB, Memgraph Cloud (all Bolt/Cypher)
    falkordb_platform.py # FalkorDB Cloud client (openCypher, FalkorDB's own client)
    arango_platform.py  # ArangoDB client (AQL)
scripts/run_all.sh       # one command: prepare data -> benchmark every platform -> merge results
dashboard/                # Next.js results viewer (reads results/summary.json)
results/
  summary.example.json    # placeholder data, clearly flagged, used only if summary.json is absent
  summary.json             # this run's real merged results (committed -- no secrets, just numbers)
  footprint.json           # this run's real per-platform footprint (committed)
  <platform>.json          # this run's raw per-platform result, pre-merge
```

## Reproducing this benchmark

Prerequisites: Python 3.10+, Node 18+, and free-tier accounts on CognoDB
Cloud, Neo4j AuraDB, Memgraph Cloud, FalkorDB Cloud, and ArangoDB Oasis.

1. **Provision the five managed instances.**
   - CognoDB: sign up at `console.cognodb.com/signup`, create a free `c0`
     instance, save the `bolt+s://` URI and the one-time `cognodb` password.
   - AuraDB: create a Free instance at `console.neo4j.io`, save the
     `neo4j+s://` URI and generated password.
   - Memgraph Cloud: create an entry-tier instance, save its `bolt+s://` URI
     and credentials.
   - FalkorDB Cloud: create a free-tier instance, save its host/port and
     password.
   - ArangoDB Oasis: start a free trial deployment, save its HTTPS endpoint
     and root password.

2. **Configure credentials** (never commit this file):
   ```bash
   cp .env.example .env
   # fill in COGNODB_*, AURA_*, MEMGRAPH_*, FALKORDB_*, ARANGO_*
   ```

3. **Install dependencies:**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run everything with one command:**
   ```bash
   scripts/run_all.sh
   # or target specific platforms: scripts/run_all.sh cognodb aura
   ```
   This downloads/prepares the dataset once, then for each platform: clears
   any existing data, creates indexes, bulk-loads nodes and edges (timing the
   load), runs a warm-up pass, then 100 iterations of each traversal/lookup
   query, 20 iterations of the aggregation query, and a 1/10/40-client mixed
   read/write sweep (10% writes) for 10 seconds per concurrency level. Each
   platform's results land in `results/<platform>.json`; `merge_results.py`
   combines them into `results/summary.json`.

5. **Pull footprint numbers** (separate step — each platform needs a
   different introspection method, so this doesn't fit the per-platform
   loop above):
   ```bash
   python -m benchmarks.footprint
   ```
   Writes `results/footprint.json`; prints "not observable" per-platform
   rather than failing when a platform's query API doesn't expose this.

6. **View the results:**
   ```bash
   cd dashboard && npm install && npm run dev
   ```
   Open `http://localhost:3000` — it reads `results/summary.json` directly
   (falling back to the placeholder file with a visible banner if that
   doesn't exist yet).

## Metrics measured (per platform)

| Category | Metric | Method |
|---|---|---|
| Data loading | Nodes/sec, relationships/sec, wall-clock load time | Batched `UNWIND` (Bolt platforms) / `import_bulk` (ArangoDB), 2000-row batches |
| Traversals | 1-hop, 2-hop, 3-hop latency (p50/p95) | 100 iterations from random start nodes, 10-iteration warm-up |
| Lookups | Point lookup (indexed `id`), filtered lookup (indexed `department`) | 100 iterations, 10-iteration warm-up |
| Aggregation | `COUNT` grouped by `department` over all `EMAILED` edges | 20 iterations, 3-iteration warm-up |
| Mixed workload | Sustained queries/sec at 1 / 10 / 40 concurrent clients, 90% read / 10% write | 10-second run per concurrency level, thread-per-client, own connection per client |
| Footprint | Stored data size / memory, where the platform exposes it | `python -m benchmarks.footprint` — platform-specific introspection (Memgraph's `SHOW STORAGE INFO`, Redis `INFO memory` for FalkorDB, `collection.statistics()` for ArangoDB); "not observable" where confirmed unavailable |

Percentiles are computed with Python's stdlib `statistics.quantiles` — no
extra dependency needed for a handful of percentile numbers.

## Results

**Live results for all 5 platforms**, measured on 2026-08-24 from this
repo's own dev environment against each platform's real free/entry-tier
instance, using the sampled soc-Pokec dataset described above (169,924
nodes / 100,000 edges). Raw numbers live in `results/summary.json`; the
dashboard renders the same data. See [Honest caveats](#honest-caveats) for
what this single run does and doesn't prove.

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
| Memgraph Cloud | 203.9 / 220.4 | 204.4 / 214.6 | 204.5 / 209.7 |
| FalkorDB Cloud | 101.4 / 105.4 | 101.8 / 120.0 | 99.8 / 125.9 |
| ArangoDB Oasis | 307.4 / 355.2 | 307.3 / 341.9 | 307.2 / 331.2 |

### Lookups (ms, p50 / p95)

| Platform | Point lookup | Filtered lookup |
|---|---|---|
| CognoDB | 306.9 / 333.0 | 307.4 / 331.1 |
| AuraDB | 204.0 / 227.5 | 204.4 / 259.6 |
| Memgraph Cloud | 204.4 / 207.9 | 203.9 / 210.9 |
| FalkorDB Cloud | 101.2 / 119.7 | 100.9 / 116.6 |
| ArangoDB Oasis | 307.3 / 351.3 | 307.5 / 349.2 |

### Aggregation (ms, p50 / p95)

| Platform | GROUP BY department |
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

Measured live via `python -m benchmarks.footprint` (`results/footprint.json`)
— each platform needed a genuinely different introspection method, since
there's no common Cypher/AQL surface for this:

| Platform | Stored data size | Memory usage | How it was measured |
|---|---|---|---|
| CognoDB | not observable | not observable | attempted `SHOW STORAGE INFO`, `SHOW DATABASES`, and `apoc.monitor.store()` — all three fail; this instance's Cypher surface implements neither Memgraph's storage-info extension nor APOC |
| AuraDB | not observable via query API (console UI shows a storage % gauge, not pulled this run) | not observable | `SHOW DATABASES` returns topology/status only, no size field; `dbms.listConfig` is `Forbidden` on Free tier; no APOC installed |
| Memgraph Cloud | 32.82 MiB on disk | 162.26 MiB resident (172.55 MiB peak), against a 1.54 GiB limit | `SHOW STORAGE INFO` (Memgraph-specific Cypher extension) |
| FalkorDB Cloud | — (Redis reports memory, not disk) | 46.17 MB used (52.57 MB peak), against a 100 MB `maxmemory` cap | Redis `INFO memory` over the same connection |
| ArangoDB Oasis | 13.77 MB document data + 16.88 MB across 3 indexes | not observable via this API | `collection.statistics()` (python-arango) |

Two real findings here: FalkorDB Cloud is running this dataset at **~46-52%
of its entire memory ceiling** — the tightest margin of any platform in
this benchmark, worth knowing before scaling the dataset up on that
platform specifically. And ArangoDB's index size (16.88 MB) is *larger*
than its document data (13.77 MB) for this dataset — the 3 indexes
(`_key` primary index plus the two created in `create_indexes()`) cost
more space than the 269,924 documents they index.

## Analysis

- **Traversal and lookup latency is flat across query complexity within
  each platform, and that's the tell.** On every platform, 1-hop, 2-hop,
  3-hop, point lookup, and filtered lookup all land within a few ms of each
  other — a traversal one hop deeper should cost *more*, not the same. That
  flatness means network round-trip time to the client dominates actual
  query execution time for a dataset this small, not the query itself. Each
  platform sits at its own flat floor: ~307ms (CognoDB, ArangoDB), ~204ms
  (AuraDB, Memgraph Cloud), ~101ms (FalkorDB Cloud) — three clusters, not
  five random numbers. **This is almost certainly "network path from this
  run's client to each platform's region," not "query engine speed."**
  FalkorDB Cloud's cluster is a partial exception (see below): its
  connection also skips TLS, which removes a real per-query cost the other
  four all pay, so its floor isn't purely a region effect. A genuinely fair
  per-engine latency comparison would need a client colocated in the same
  region as every instance, which this run did not control for.
- **ArangoDB's aggregation query is the one place engine/query behavior,
  not network RTT, clearly dominates.** At 11.7s p50 — 10x CognoDB's 1.1s,
  38x AuraDB's 277ms, 49x Memgraph's 238ms, 38x FalkorDB's 309ms — the
  `FOR e IN EMAILED LET p = DOCUMENT(e._from) COLLECT department...` AQL
  query does a `DOCUMENT()` lookup per edge rather than a joined/indexed
  traversal: a per-edge document fetch for 100,000 edges is a real O(n)
  cost that every Cypher/openCypher platform's `MATCH
  ()-[r:EMAILED]->() RETURN p.department, count(r)` avoids by keeping the
  property inline on the traversal path. This is the one number in this
  run that looks like a genuine query-planner/idiom difference rather than
  a network or protocol artifact.
- **FalkorDB Cloud was fastest on every single metric measured** — fastest
  load (21.8s vs. 35.8–127.7s elsewhere), lowest latency floor (~101ms),
  and by far the highest mixed-workload throughput (1,351.6 qps at 40
  clients vs. 104–223 qps for the Bolt platforms). Three plausible,
  non-exclusive reasons, none of which this single run can cleanly
  separate: (1) its Redis-derived engine is genuinely fast for this kind
  of small-graph workload; (2) its connection skips TLS entirely (see
  caveats) while every other platform pays a TLS handshake per new
  connection, which matters a lot for the mixed workload's 40
  simultaneously-opened client connections; (3) region proximity, same
  confound as above. The throughput gap (6–13x the other platforms) is
  large enough that TLS overhead alone is a plausible major contributor,
  not just engine speed — this would need a same-TLS-posture rerun to
  untangle.
- **Throughput scaled up at every concurrency level tested (1 → 10 → 40)
  for all five platforms**, with no sign of a ceiling being hit yet on any
  of them (e.g. CognoDB: 2.9 → 28.6 → 104.4 qps; ArangoDB: 3.2 → 32.9 →
  120.3 qps — each roughly linear in client count, and FalkorDB's jump from
  117 → 1,352 qps between 10 and 40 clients is *super*-linear). That's a
  mild surprise for 0.5 vCPU burstable instances; it suggests either the
  burst credit wasn't exhausted in a 10-second window, or the read-heavy
  (90%) point-lookup workload is cheap enough per-query that connection/
  queueing overhead, not compute, was the bottleneck at these
  concurrencies. A longer sustained run (60s+ per level) would be needed to
  see whether throttling eventually bites, especially on the four TLS-paying
  platforms.

## Honest caveats

- **All 5 platforms ran, but three needed a platform-specific fix
  discovered live, not assumed in advance.**
  - **Memgraph Cloud** required `bolt+ssc://` instead of `bolt+s://`. Its
    instance presents a self-signed certificate; `bolt+s://` demands
    CA-verified TLS and failed immediately with
    `SSLCertVerificationError`. AuraDB's and CognoDB's own free-tier certs
    verified fine with `bolt+s://`/`neo4j+s://`.
  - **AuraDB Free's username is not `neo4j`.** This specific instance's
    generated credentials export used the instance ID (`f8ed57a5`) as the
    username, not the conventional `neo4j` — the first connection attempt
    with `neo4j` failed with `Neo.ClientError.Security.Unauthorized`
    despite the URI, host, and port all being correct and reachable.
    Anyone reproducing this should copy the exact username from their own
    instance's downloaded credentials file rather than assuming `neo4j`.
  - **FalkorDB Cloud's public endpoint doesn't complete a TLS handshake at
    all.** With `ssl=True`, the TCP connection succeeded but the TLS
    handshake itself hung/timed out on every attempt (confirmed via a raw
    `redis-py` connection, isolating it from the `falkordb` client
    library) — not a slow query, a connection that never establishes.
    Setting `ssl=False` connected and completed a `PING` in 0.38s. This
    matters beyond "it works now": FalkorDB Cloud's throughput numbers in
    this run are **not directly comparable** to the other four platforms
    for that reason — see Analysis.
- **This run's client-to-platform network path was not controlled for, and
  the results show it.** As detailed in Analysis above, every platform's
  query latency is flat across query complexity, clustering into three
  bands (~307ms CognoDB/ArangoDB, ~204ms AuraDB/Memgraph, ~101ms FalkorDB)
  — a signature of network RTT (and, for FalkorDB, no-TLS) dominating
  actual execution time, not a property of any database engine. None of
  the absolute latency numbers in this README should be read as "how fast
  is this database," only "how fast did this database answer from this
  specific client, in this specific run, over this specific network path
  and TLS posture." A methodologically tighter version of this benchmark
  would run the client in the same cloud region as each instance, and hold
  TLS posture constant across all five.
- **The same password was reused across AuraDB (initially), Memgraph
  Cloud, and FalkorDB Cloud's `.env` entries during this benchmark's
  setup** — a real-world credential-hygiene issue independent of the
  benchmark's actual results. Rotate each platform's password to something
  unique before treating this `.env` as a template for anything beyond
  this one-off benchmark run.
- **ArangoDB's data load took 2–6x longer than every other platform**
  (127.7s vs. 21.8–62.6s elsewhere) for the identical 169,924 nodes /
  100,000 edges, and its aggregation query took 38–49x longer than the
  four Cypher/openCypher platforms (11.7s vs. 238–1,117ms p50) — see
  Analysis above for why (a per-edge `DOCUMENT()` lookup in the
  aggregation AQL, likely combined with `import_bulk`'s HTTP-per-batch
  overhead during load). Flagged as a real, reproducible difference, not a
  fluke — rerun it yourself before trusting it further, since it was only
  measured once here.
- **Query-language differences (Cypher vs. AQL) are not fully eliminable.**
  The ArangoDB traversal queries use `FOR v IN n..n OUTBOUND` while the
  Cypher/openCypher platforms use `-[:EMAILED*n]->`; these are the
  idiomatic way to express the same logical query in each language, but
  query planners are free to optimize them differently, so ArangoDB
  numbers reflect "AQL's traversal planner," not a strictly identical
  execution path.
- **Each mixed-workload concurrency level ran for only 10 seconds and only
  once, on all five platforms.** Long enough to see relative ordering, not
  long enough to confidently rule out burst-credit throttling kicking in
  later, or to report variance across repeated runs. Every number in the
  Mixed read/write throughput table is a single-run point estimate.
- **Footprint metrics were pulled live for 3 of 5 platforms** (Memgraph,
  FalkorDB, ArangoDB) via `benchmarks/footprint.py` — see the Footprint
  results section. **CognoDB and AuraDB are genuinely not observable**, not
  unmeasured: this was confirmed by direct attempt (`SHOW STORAGE INFO`,
  `SHOW DATABASES`, `dbms.listConfig`, `apoc.monitor.store()` all fail on
  one or both), not assumed. This also surfaced that the original "every
  platform is pinned to the same 256 MB" plan didn't hold in practice —
  see the corrected Platforms-compared table and its fairness-analysis
  note above.
- **The dataset is a random 100,000-edge sample of SNAP soc-Pokec's real
  30,622,564-edge friendship graph** (see Dataset section), not the full
  graph — chosen deliberately to fit every platform's free-tier storage, at
  the cost of losing whatever structural properties (e.g. degree
  distribution, community structure) only show up at full scale. `1-hop`
  neighbor counts, in particular, will be systematically lower on the
  sampled graph than they would be on the full soc-Pokec graph.
- **This entire benchmark ran once, end to end, from one client machine, on
  one day.** No repeated-run variance, no cold-start-vs-warm split beyond
  the per-workload warm-up already built into each run, and no retry of a
  failed/flaky measurement. Every number above is a single sample, not a
  distribution — treat this as a first pass to build on, not a final verdict.

## License

No license file included — add one if you intend to publish this beyond the
assignment submission.
