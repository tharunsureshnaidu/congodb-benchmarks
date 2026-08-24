# Five "free tier" graph databases walk into a benchmark

I went into this expecting the hard part to be writing Cypher. Sample a
real dataset, load it into five databases, run the same queries against
each one, report the medians. A weekend project, tops.

The queries were the easy part. What actually took the time was getting
five different companies' "free, no credit card, ready in a minute"
signup flows to all answer a query from the same script — and once they
did, discovering that "free tier" doesn't mean anywhere near the same
thing from one vendor to the next.

This is the story of comparing **CognoDB Cloud** against **Neo4j AuraDB**,
**Memgraph Cloud**, **FalkorDB Cloud**, and **ArangoDB Oasis**. The full
numbers, the code, and a much longer list of caveats live in the repo's
README — this is the version I'd actually tell a friend.

## The setup

The idea was straightforward: take a real dataset, not something
generated for the occasion, and load the identical data into all five
platforms. I used a 100,000-edge sample of [SNAP's `soc-Pokec`
dataset](https://snap.stanford.edu/data/soc-Pokec.html) — a real Slovak
social network, 30.6 million friendship edges in the original, trimmed
down to a size that wouldn't blow past anyone's free-tier storage.

Four of the five platforms speak Cypher, which is a nice accident of the
graph database world — CognoDB, AuraDB, and Memgraph Cloud all talk Bolt,
so one client class could hit all three without any per-platform code.
FalkorDB also understands Cypher, just through its own Redis-flavored
client instead of Bolt. ArangoDB is the odd one out on purpose — a
completely different query language (AQL) and storage model, because a
benchmark that only compares near-identical Cypher engines to each other
isn't really benchmarking anything.

## Getting five accounts talking was its own project

Every signup page says the same thing: no credit card, instance ready in
under a minute. Two of the five connected the moment I pointed a driver at
them. The other three each needed a small, undocumented fix before they'd
answer anything.

Memgraph Cloud rejected every connection attempt with a TLS certificate
error. It turns out its free instance ships a self-signed certificate, and
the standard `bolt+s://` connection scheme insists on a certificate signed
by a real certificate authority. Swap it for `bolt+ssc://` — same
encryption, no certificate check — and it connects instantly. One-word
fix, but nothing in the getting-started flow mentions it.

AuraDB was stranger. Right URI, right password, and it just kept saying
Unauthorized. After staring at it for a while I realized the username
wasn't `neo4j` — it was the instance ID. Every example on the internet
uses `neo4j` as the username, because for most Aura instances that's
correct. Not this one. The password had been right the entire time; I was
just logging in as the wrong person.

FalkorDB was the one that actually had me worried something was broken on
their end. The port was open. The connection just sat there — not an
error, just silence, for a full minute, every single attempt. Stripping
away every layer of abstraction down to a bare Redis client (no graph
library, just "say hello to this server") finally showed what was
happening: the TLS handshake itself never completed. Turn TLS off
entirely, and it connects and answers a ping in under half a second. The
endpoint just doesn't do TLS, despite every setup guide assuming it does.

None of this is a knock on any single company. Five different products
built five different versions of "it just works," and three of them
needed a small correction before they actually did.

## The actual surprise: nobody's free tier is the same size

Going in, the plan was to treat every platform as roughly equivalent — a
half a CPU, a couple hundred megabytes of RAM, call it a fair fight. Then
I tried to actually measure what each platform was giving me instead of
assuming it, and that assumption didn't survive contact with reality.

FalkorDB's real memory ceiling, read straight off Redis's own `INFO
memory` command, is 100 MB. My 100,000-edge dataset was sitting at roughly
half of that the entire time it ran. Memgraph's console shows a 2 GB, 2
vCPU box, and asking the database itself for its storage info reports a
1.54 gigabyte usable limit inside that — either way, comfortably more than
FalkorDB's, on two platforms marketed with the same "free" and "entry"
language. Neither ArangoDB Oasis nor FalkorDB Cloud actually hands you a
fixed free tier at all — both are "pick your own size" deployments. The
smallest ArangoDB would let me choose came out to 0.25 vCPU, 1 GB of RAM,
and 40 GB of disk: less CPU than CognoDB's tier, several times more RAM
and a lot more disk. And CognoDB and AuraDB, for their part, simply don't
expose a memory or storage figure through any API a client can reach. I
tried every trick I knew — storage-info queries, admin procedures, APOC —
and came up empty on both.

So the honest summary isn't "everyone got the same resources." It's: of
the three platforms where I could actually pin down a real number, those
numbers spanned more than an order of magnitude, and two more platforms
won't tell you their number no matter how you ask. If you're choosing a
graph database off a vendor's free-tier comparison page, that's
worth remembering — the word "free" tells you what it costs, not what
you're actually getting.

## The latency numbers were mostly measuring the internet

Here's the thing that should make anyone suspicious of headline latency
numbers in general: on CognoDB and ArangoDB, a query touching one
neighbor and a query walking three hops away came back in almost exactly
the same time — around 307 milliseconds, both of them, every time. AuraDB
and Memgraph sat at a flatter, faster ~204ms. FalkorDB was flatter and
faster still, around 101ms.

A database that answers a cheap query and an expensive query at the same
speed isn't showing you its query engine. It's showing you the round trip
between my laptop and wherever that instance happens to live. Three flat
bands, three different network distances — plus, in FalkorDB's case, one
less TLS handshake to pay for than everyone else.

The one number that didn't fit that story was ArangoDB's aggregation
query, which took 11.7 seconds against roughly a quarter to a bit over a
second everywhere else. The AQL query looks up each edge's source
document individually instead of carrying the grouping field along the
traversal, which is a real cost that scales with the size of the graph —
not something network latency can explain away, since every other query
ArangoDB ran was just as network-bound as its competitors and didn't look
like this.

## So, what actually held up

Not "which database is fastest" — I don't think a hundred-thousand-edge
graph, run once, from one laptop, against a free instance, can honestly
answer that question, and I've tried not to pretend it does. What did
hold up: treat any vendor's free-tier claims as marketing copy until
you've measured them yourself, because the gap between two "free" tiers
can be larger than the gap between free and paid. Read latency numbers
with real suspicion unless you know where the client sat relative to the
database — a number with no network context is only half a number. And
the differences that survive once you account for the network — like
ArangoDB's per-edge lookup — are the ones actually worth trusting.

Everything above — every metric, every platform, the full list of caveats
this piece didn't have room for — is in the repo, along with the code to
run it yourself against your own free-tier accounts. If a number here
looks off, that's kind of the point of publishing the harness next to the
results: go check it.
