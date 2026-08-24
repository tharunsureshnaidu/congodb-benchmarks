"""FalkorDB Cloud client. FalkorDB speaks openCypher (it's the RedisGraph
successor), so the CREATE/MATCH/UNWIND query text is identical to the Bolt
platforms (see workloads.QUERIES["falkordb"], aliased to QUERIES["bolt"]) --
only the wire protocol and index-creation syntax differ, so this mirrors
BoltPlatform's load()/run() shape but talks to FalkorDB's own client instead
of a Bolt driver.
"""
import time
from falkordb import FalkorDB


class FalkorDBPlatform:
    def __init__(self, host: str, port: int, username: str, password: str,
                 graph_name: str = "benchmark", ssl: bool = True):
        self.db = FalkorDB(
            host=host, port=port,
            username=username or None, password=password or None,
            ssl=ssl,
        )
        self.graph = self.db.select_graph(graph_name)

    def close(self):
        pass  # no persistent connection object to tear down

    def run(self, query: str, params: dict | None = None):
        return self.graph.query(query, params or {}).result_set

    def create_indexes(self):
        self.graph.query("CREATE INDEX FOR (p:Person) ON (p.id)")
        self.graph.query("CREATE INDEX FOR (p:Person) ON (p.department)")

    def clear(self):
        try:
            self.graph.delete()
        except Exception:
            pass  # graph doesn't exist yet on first run

    def load(self, nodes: list[dict], edges: list[tuple[int, int]], batch_size: int = 2000):
        """Batched UNWIND load, same shape as BoltPlatform.load().
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
