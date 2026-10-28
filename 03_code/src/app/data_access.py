"""Data access for the network explorer.

Two interchangeable sources return the same tables:
  Neo4jSource  queries the live graph (default when NEO4J_PASSWORD is set)
  FileSource   reads the JSON exports in 01_data/processed (works without a database)

flows_touching() returns one row per payer, payee, month, route, purpose and counterparty bank:
  s, t, m, r, c, b (counterparty-side bank), x (1 = self transfer), n (payments), v (QAR)
"""
import json
import os
from pathlib import Path

import pandas as pd

FLOW_COLS = ["s", "t", "m", "r", "c", "b", "x", "n", "v"]
ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "01_data" / "processed"

ENTITY_QUERY = """
MATCH (e:Entity)-[:BANKS_WITH]->(b:Bank)
RETURN e.uid AS id, e.name AS name, e.entity_type AS type, coalesce(e.industry, '') AS industry, coalesce(e.is_gre, false) AS gre,
       e.is_qib_customer AS qib, b.name AS bank, e.pagerank AS pr, e.betweenness AS bt, e.community AS comm
"""

# Every transaction touching any of $uids, after the filters. DISTINCT stops a payment
# between two listed entities being counted twice.
TOUCHING_QUERY = """
UNWIND $uids AS u
MATCH (x:Entity {uid: u})
CALL (x) {
  MATCH (x)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(y:Entity) RETURN x AS a, t, y AS b
  UNION
  MATCH (y:Entity)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(x) RETURN y AS a, t, x AS b
}
WITH DISTINCT a, b, t
WHERE t.month >= $m_from AND t.month <= $m_to
  AND (size($routes) = 0 OR t.route IN $routes)
  AND (size($purposes) = 0 OR t.classification IN $purposes)
MATCH (cb:Bank {code: t.cp_bank_cd})
WITH a, b, t, cb WHERE size($banks) = 0 OR cb.name IN $banks
RETURN a.uid AS s, b.uid AS t, t.month AS m, t.route AS r, t.classification AS c, cb.name AS b,
       CASE WHEN t.is_self THEN 1 ELSE 0 END AS x, count(t) AS n, sum(t.amount_qar) AS v
"""

ALL_FLOWS_QUERY = """
MATCH (a:Entity)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(b:Entity)
MATCH (cb:Bank {code: t.cp_bank_cd})
RETURN a.uid AS s, b.uid AS t, t.month AS m, t.route AS r, t.classification AS c, cb.name AS b,
       CASE WHEN t.is_self THEN 1 ELSE 0 END AS x, count(t) AS n, sum(t.amount_qar) AS v
"""

BANK_FLOWS_QUERY = """
MATCH (t:Transaction)
MATCH (pb:Bank {code: t.payer_bank_cd}), (qb:Bank {code: t.payee_bank_cd})
RETURN pb.name AS from_bank, qb.name AS to_bank, t.month AS m, t.route AS r, count(t) AS n, sum(t.amount_qar) AS v
"""


def _filter(df, m_from, m_to, routes, purposes, banks=None):
    keep = (df.m >= m_from) & (df.m <= m_to)
    if banks:
        keep &= df.b.isin(banks)
    if routes:
        keep &= df.r.isin(routes)
    if purposes:
        keep &= df.c.isin(purposes)
    return df[keep]


class Neo4jSource:
    label = "Neo4j"

    def __init__(self, uri, user, password):
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.driver.verify_connectivity()

    def _df(self, query, **params):
        with self.driver.session() as s:
            return pd.DataFrame(s.run(query, **params).data())

    def entities(self):
        return self._df(ENTITY_QUERY)

    def all_flows(self):
        return self._df(ALL_FLOWS_QUERY)

    def bank_flows(self):
        return self._df(BANK_FLOWS_QUERY)

    def flows_touching(self, uids, m_from, m_to, routes, purposes, banks=None):
        df = self._df(TOUCHING_QUERY, uids=list(uids), m_from=m_from, m_to=m_to,
                      routes=list(routes or []), purposes=list(purposes or []), banks=list(banks or []))
        return df if len(df) else pd.DataFrame(columns=FLOW_COLS)


class FileSource:
    label = "exported files"

    def __init__(self, folder=PROCESSED):
        self._ents = pd.DataFrame(json.load(open(folder / "neo4j_entities.json", encoding="utf-8")))
        self._flows = pd.DataFrame(json.load(open(folder / "neo4j_flows.json", encoding="utf-8")))
        self._flows["m"] = self._flows.m.astype(str)
        self._banks = pd.DataFrame(json.load(open(folder / "neo4j_bank_flows.json", encoding="utf-8")))
        self._banks["m"] = self._banks.m.astype(str)

    def entities(self):
        return self._ents.copy()

    def all_flows(self):
        return self._flows.copy()

    def bank_flows(self):
        return self._banks.copy()

    def flows_touching(self, uids, m_from, m_to, routes, purposes, banks=None):
        uids = set(uids)
        df = self._flows[self._flows.s.isin(uids) | self._flows.t.isin(uids)]
        return _filter(df, m_from, m_to, routes, purposes, banks)


def open_source():
    """Neo4j when NEO4J_PASSWORD is set and reachable, otherwise the exported files."""
    pw = os.getenv("NEO4J_PASSWORD")
    if pw:
        try:
            return Neo4jSource(os.getenv("NEO4J_URI", "bolt://localhost:7687"), os.getenv("NEO4J_USER", "neo4j"), pw)
        except Exception as exc:  # fall back so the app still opens
            print(f"Neo4j not reachable ({exc}); using exported files")
    return FileSource()
