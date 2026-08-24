# What Happens When You Benchmark Five Graph Databases?

Graph database benchmarks are easy to get wrong.

So for this experiment, I wanted to answer a simpler question:

**What actually happens when the same graph and the same workloads are sent to several managed graph databases?**

I benchmarked **CognoDB Cloud, Neo4j AuraDB, Memgraph Cloud, FalkorDB Cloud, and ArangoDB Oasis** using the same 100,000-edge subset of the SNAP `soc-Pokec` dataset.

The benchmark measured ingestion, 1/2/3-hop traversals, indexed lookups, aggregation, and concurrent read/write workloads.

## The first surprise: latency wasn't really about graph depth

The traversal results were unexpectedly flat.

For example, CognoDB measured roughly:

* 1-hop: **306.8 ms p50**
* 2-hop: **307.1 ms p50**
* 3-hop: **307.1 ms p50**

Other platforms showed a similar pattern.

A 3-hop traversal should normally involve more graph work than a 1-hop traversal. The fact that the numbers barely changed suggested something else was dominating the measurement:

**network round-trip latency.**

This is an important lesson from the benchmark. A cloud database benchmark isn't necessarily measuring just the database engine. It measures the entire path between the client and the database.

## FalkorDB was the fastest — but there is a catch

FalkorDB produced the lowest traversal latency and the highest mixed-workload throughput.

At 40 concurrent clients:

| Platform     |         QPS |
| ------------ | ----------: |
| CognoDB      |       104.4 |
| Neo4j AuraDB |       223.2 |
| Memgraph     |       183.1 |
| FalkorDB     | **1,351.6** |
| ArangoDB     |       120.3 |

That looks like a decisive result.

But it isn't.

The FalkorDB connection used a different protocol configuration and did not have the same TLS overhead as the other platforms. That means the benchmark cannot cleanly separate database performance from connection overhead.

So the honest conclusion isn't:

> "FalkorDB is 6x faster."

It is:

> "FalkorDB achieved 1,351 QPS in this particular configuration, but protocol and connection differences are important confounding factors."

That's exactly why benchmark methodology matters.

## The biggest outlier was ArangoDB aggregation

The aggregation workload produced another interesting result.

Most databases completed the workload in hundreds of milliseconds, while ArangoDB took approximately **11.7 seconds at p50**.

This wasn't simply a random slow run. The AQL query shape required additional document lookups while traversing the graph, making the workload fundamentally more expensive.

This demonstrates another benchmark lesson:

**Logical workloads need to be equivalent, not necessarily syntactically identical.**

Cypher and AQL express the same operation differently, and those differences can have a significant impact on the resulting execution plan.

## What about CognoDB?

CognoDB didn't win every category, and that wasn't the purpose of the experiment.

It achieved:

* **2,715 nodes/s** during ingestion
* **1,598 relationships/s**
* **104.4 QPS** at 40 concurrent clients

Its measured traversal latency was higher than Neo4j, Memgraph, and FalkorDB in this environment.

But the results also show why a single benchmark number isn't enough to evaluate a database.

## The biggest limitation: resource parity

The original goal was to give every platform equivalent resources.

In practice, managed free tiers don't expose identical configurations.

CognoDB provides **0.5 burstable vCPU, 256 MB RAM, and 1 GB disk**, while other platforms expose different resource allocations.

Rather than hiding that problem, I recorded the differences and treated them as a limitation of the experiment.

That is ultimately what I wanted this benchmark to demonstrate:

**A benchmark is only as useful as the methodology behind the number.**

The complete benchmark harness, dataset preparation, raw results, and reproduction instructions are available in this repository.
