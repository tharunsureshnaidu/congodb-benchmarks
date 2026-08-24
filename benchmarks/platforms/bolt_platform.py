"""Shared client for every platform that speaks Cypher over the Bolt protocol:
CognoDB Cloud, Neo4j AuraDB Free, and Memgraph Cloud. They're wire-compatible,
so one implementation covers all three -- no per-platform subclassing needed
(this is the whole reason the assignment's "connect with the official Neo4j
driver" note works unmodified for CognoDB).
"""
import time
from neo4j import GraphDatabase


class BoltPlatform:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run(self, query: str, params: dict | None = None):
        with self.driver.session() as session:
            return list(session.run(query, params or {}))

    def create_indexes(self):
        self.run("CREATE INDEX person_id IF NOT EXISTS FOR (p:Person) ON (p.id)")
        self.run("CREATE INDEX person_department IF NOT EXISTS FOR (p:Person) ON (p.department)")

    def clear(self):
        self.run("MATCH (n) DETACH DELETE n")

    def load(self, nodes: list[dict], edges: list[tuple[int, int]], batch_size: int = 2000):
        """Batched UNWIND load (driver batching, per the assignment's suggested method).
        Returns (node_count, edge_count, elapsed_seconds)."""
        start = time.perf_counter()
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i : i + batch_size]
            self.run(
                "UNWIND $rows AS row CREATE (p:Person {id: row.id, department: row.department})",
                {"rows": batch},
            )
        for i in range(0, len(edges), batch_size):
            batch = [{"src": s, "dst": d} for s, d in edges[i : i + batch_size]]
            self.run(
                """
                UNWIND $rows AS row
                MATCH (a:Person {id: row.src}), (b:Person {id: row.dst})
                CREATE (a)-[:EMAILED]->(b)
                """,
                {"rows": batch},
            )
        elapsed = time.perf_counter() - start
        return len(nodes), len(edges), elapsed
