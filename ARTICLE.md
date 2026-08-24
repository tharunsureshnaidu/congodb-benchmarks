# I Benchmarked 5 "Free Tier" Graph Databases. The Free Tiers Weren't the Same Size.

You'd think benchmarking graph databases means writing Cypher, running it a
hundred times, and reporting a median. That part took an afternoon. What
actually ate the weekend was discovering that "free tier" is not a unit of
measurement — it's a marketing term, and five vendors don't agree on what
it means.

This is the story of benchmarking **CognoDB Cloud** against **Neo4j
AuraDB**, **Memgraph Cloud**, **FalkorDB Cloud**, and **ArangoDB Oasis** —
same dataset, same queries, same client, one weekend — and what broke along
the way turned out to be more interesting than the latency numbers
themselves.

*(Full methodology, raw results, and the code to reproduce every number
below live in [the repo](.) — this is the readable version of that story.)*

## The setup: five databases, one graph, zero shortcuts

The plan was simple on paper: take a real public dataset, sample it down to
100,000 relationships so it fits comfortably on a free-tier instance, load
it identically into all five platforms, and run the same five workloads —
traversals, lookups, an aggregation, and a concurrent read/write mix —
against each one.

The dataset is a random 100,000-edge sample of [SNAP's `soc-Pokec`
dataset](https://snap.stanford.edu/data/soc-Pokec.html), a real Slovak
social network with 30.6 million friendship edges in total. Not a toy graph
generated for the occasion — an actual social graph, just trimmed to a size
that won't blow past a free tier's storage limit.

Four of the five platforms speak Cypher over the Bolt protocol, which
meant one client class could talk to CognoDB, AuraDB, and Memgraph Cloud
without modification — genuinely the same code hitting three different
databases. FalkorDB speaks openCypher too, just over its own Redis-based
client instead of Bolt. ArangoDB is the outlier: a different query
language entirely (AQL), included on purpose, because a benchmark that
only compares Cypher clones to each other isn't really testing anything.

## Getting five "free" accounts online was the actual benchmark

Every platform's signup page promises the same thing: sign up, no credit
card, instance ready in under a minute. Four of the five delivered on
that. Getting all five to actually *answer a query* took some detective
work:

**Memgraph Cloud** refused every connection with a TLS certificate error.
Turned out its free instance uses a self-signed cert — the standard
`bolt+s://` scheme demands a certificate a public CA has signed, and
Memgraph's isn't one. The fix is a one-character difference in the
connection URI (`bolt+ssc://` instead of `bolt+s://`), but finding that out
cost a stack trace and a search.

**AuraDB** rejected the right password with the right URI, over and over,
with a flat "Unauthorized." The username wasn't `neo4j`. Every piece of
Neo4j driver documentation on the internet uses `neo4j` as the example
username, and for most Aura instances it *is* the username — except this
one, where the console's own downloaded credentials file listed the
instance ID as the username instead. The password was right the whole
time.

**FalkorDB Cloud** was the strangest one. The TCP port was open. The
connection just... hung. Not a fast failure — a full minute of nothing,
every single time. Isolating the problem down to a raw Redis client (no
FalkorDB wrapper, no graph library, just "can I say hello to this server")
revealed the actual issue: the TLS handshake itself was timing out. The
server accepts a plain, unencrypted connection just fine — it just doesn't
speak TLS on this endpoint at all, despite every setup guide assuming it
does.

None of these are exotic failures. They're the kind of thing that happens
constantly when five different companies each build their own "getting
started" experience, and none of them are lying — CognoDB and ArangoDB
connected on the first try with default settings, so it's not that these
docs are universally unreliable. It's that "should just work" is doing a
lot of unstated work in this industry, and a benchmark that skips past the
setup friction is skipping the part most engineers will actually hit.

## The finding nobody was looking for: "free tier" doesn't mean the same amount of anything

The original plan was to pin every platform to the same 0.5 vCPU / 256 MB
RAM / 1 GB storage — CognoDB's advertised free-tier ceiling — and call it a
fair fight. Then the benchmark tried to actually *measure* each platform's
real memory footprint instead of assuming it, and the assumption fell
apart:

- **FalkorDB Cloud's actual memory cap is 100 MB** — measured directly via
  Redis's own `INFO memory` command, not a guess. This benchmark's dataset
  was using **46–52% of FalkorDB's entire memory budget** just sitting
  there loaded.
- **Memgraph Cloud's actual memory limit is 1.54 GiB** — over **15 times**
  larger than FalkorDB's, for two platforms both marketed as a "free" or
  "entry" tier.
- **ArangoDB Oasis isn't a fixed free tier at all.** It's a 14-day trial
  where *you* pick the instance size when you deploy it. There is no
  universal "ArangoDB free tier" to compare against — there's whatever
  size someone happened to select.
- CognoDB's and AuraDB's own free tiers, meanwhile, turned out to be
  **genuinely unmeasurable** from the outside — neither platform's query
  API exposes a memory or storage figure, and neither has the admin
  procedures (or APOC) installed that would let a client ask.

So the honest version of "same resources everywhere" is: *for the three
platforms whose real limits could actually be measured, they weren't the
same, by more than an order of magnitude* — and two of the five platforms
won't tell you their real number no matter how you ask. That's not a
footnote. If you're picking a graph database based on a vendor's free-tier
comparison chart, this is the part worth remembering: "free tier" tells you
what you'll pay, not what you're getting.

## The latency numbers mostly measured the internet, not the database

Here's the part that should make anyone suspicious of a benchmark's
headline latency numbers: on CognoDB and ArangoDB, a query that touches one
neighbor and a query that walks three hops away answered in *the same
time* — around 307 milliseconds, every time, regardless of how much work
the query actually did. AuraDB and Memgraph clustered at ~204ms, flat the
same way. FalkorDB clustered lower still, around 101ms.

A database that takes exactly as long to answer a cheap query as an
expensive one isn't telling you about its query engine. It's telling you
about the round trip between this benchmark's client and that platform's
data center. Three flat clusters, three different network paths (plus, for
FalkorDB, no TLS handshake tax that the other four all pay) — not three
different levels of database speed.

The one place where the numbers *did* look like a real engine difference:
ArangoDB's aggregation query took **11.7 seconds**, against roughly a
quarter- to one-and-a-bit seconds for everything else. The AQL query does
a document lookup for every single edge instead of keeping the grouping
property inline on the traversal path — a real, structural cost that
network latency can't explain, because everything else ArangoDB did in
this benchmark was just as network-bound as its competitors.

## What this actually tells you

Not "which database is fastest" — that question, asked about a 100,000-edge
graph on a shared free instance from one client machine on one day, doesn't
have a trustworthy answer, and this piece has tried hard not to pretend it
does. What it does tell you:

1. **Read every "free tier" claim as marketing copy until you've measured
   it**, because the actual numbers behind it can differ by more than an
   order of magnitude between vendors using the same word.
2. **A latency number without a network topology is half a number.** If a
   benchmark doesn't say where the client sat relative to the database, be
   skeptical of any comparison across platforms in different regions.
3. **The genuine engine differences are the ones that survive removing the
   network** — like ArangoDB's per-edge lookup cost in this run's
   aggregation query. Those are worth trusting more than a raw millisecond
   figure.
4. **Setup friction is real signal, not noise.** A platform that connects
   on the first try with the officially documented settings is telling you
   something about its onboarding quality, independent of how fast its
   queries run once you're in.

The full results — every metric, every platform, every caveat this piece
didn't have room for — are in the repo's README, with the code to
reproduce every number above from scratch on your own free-tier accounts.
If a number here looks wrong, that's the point of publishing the harness
alongside the results: go check it.
