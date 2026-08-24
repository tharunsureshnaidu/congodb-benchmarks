"""ArangoDB client. Same GraphPlatform-shaped interface as BoltPlatform
(connect/close/create_indexes/clear/load/run) but speaks AQL instead of
Cypher -- Arango has no Bolt/Cypher compatibility layer, so it's the one
platform that needs its own query strings (see workloads.py QUERIES["arango"]).
"""
import time
from arango import ArangoClient


class ArangoPlatform:
    def __init__(self, uri: str, user: str, password: str, db: str):
        client = ArangoClient(hosts=uri)
        sys_db = client.db("_system", username=user, password=password)
        if not sys_db.has_database(db):
            sys_db.create_database(db)
        self.db = client.db(db, username=user, password=password)
        if not self.db.has_collection("Person"):
            self.db.create_collection("Person")
        if not self.db.has_collection("EMAILED"):
            self.db.create_collection("EMAILED", edge=True)

    def close(self):
        pass  # python-arango has no persistent connection to tear down

    def run(self, aql: str, params: dict | None = None):
        cursor = self.db.aql.execute(aql, bind_vars=params or {})
        return list(cursor)

    def create_indexes(self):
        people = self.db.collection("Person")
        people.add_persistent_index(fields=["node_id"], unique=True)
        people.add_persistent_index(fields=["department"])

    def clear(self):
        self.db.collection("Person").truncate()
        self.db.collection("EMAILED").truncate()

    def load(self, nodes: list[dict], edges: list[tuple[int, int]], batch_size: int = 2000):
        """Bulk import via python-arango's import_bulk (Arango's documented bulk-load path).
        Returns (node_count, edge_count, elapsed_seconds)."""
        start = time.perf_counter()
        people = self.db.collection("Person")
        docs = [{"_key": str(n["id"]), "node_id": n["id"], "department": n["department"]} for n in nodes]
        for i in range(0, len(docs), batch_size):
            people.import_bulk(docs[i : i + batch_size])

        emailed = self.db.collection("EMAILED")
        edge_docs = [
            {"_from": f"Person/{s}", "_to": f"Person/{d}"} for s, d in edges
        ]
        for i in range(0, len(edge_docs), batch_size):
            emailed.import_bulk(edge_docs[i : i + batch_size])

        elapsed = time.perf_counter() - start
        return len(nodes), len(edges), elapsed
