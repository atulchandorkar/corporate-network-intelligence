"""Compute network metrics on the Neo4j payment graph, write them back, and export dashboard data.

Metrics (stored on :Entity):
  pagerank      weighted PageRank on PAID edges (weight = total QAR); who money flows towards
  betweenness   how often an entity sits on the shortest path between others (broker / bridge)
  degree_in/out number of distinct payers / payees
  inflow_qar / outflow_qar / net_flow_qar
  community     Louvain community id (clusters of entities that trade mostly with each other)

Uses NetworkX for the algorithms so it runs on Neo4j Community without the GDS plugin.
With GDS installed, gds.pageRank / gds.louvain give equivalent results.

Usage: python analytics_and_export.py --password <pw> --out ../../../01_data/processed/dashboard_data.json
"""
import argparse, json, math
import networkx as nx
from neo4j import GraphDatabase


def run(driver, out):
    with driver.session() as s:
        edges = s.run("""MATCH (p:Entity)-[e:PAID]->(q:Entity)
                         RETURN p.uid AS src, q.uid AS dst, e.total_qar AS w, e.txn_count AS n""").data()
        G = nx.DiGraph()
        for e in edges:
            G.add_edge(e["src"], e["dst"], weight=e["w"], log_w=math.log10(e["w"] + 1), n=e["n"])
        pr = nx.pagerank(G, weight="weight")
        bt = nx.betweenness_centrality(G.to_undirected(), weight=None, normalized=True)
        U = nx.Graph()
        for u, v, d in G.edges(data=True):
            U.add_edge(u, v, weight=U.get_edge_data(u, v, {"weight": 0})["weight"] + d["log_w"])
        comms = nx.community.louvain_communities(U, weight="weight", seed=7, resolution=1.0)
        comm = {n: i for i, c in enumerate(sorted(comms, key=len, reverse=True)) for n in c}
        rows = [dict(uid=n, pagerank=pr[n], betweenness=bt.get(n, 0), community=comm[n],
                     degree_in=G.in_degree(n), degree_out=G.out_degree(n),
                     inflow=sum(d["weight"] for _, _, d in G.in_edges(n, data=True)),
                     outflow=sum(d["weight"] for _, _, d in G.out_edges(n, data=True))) for n in G.nodes]
        s.run("""UNWIND $rows AS r MATCH (e:Entity {uid: r.uid})
                 SET e.pagerank = r.pagerank, e.betweenness = r.betweenness, e.community = r.community,
                     e.degree_in = r.degree_in, e.degree_out = r.degree_out,
                     e.inflow_qar = r.inflow, e.outflow_qar = r.outflow, e.net_flow_qar = r.inflow - r.outflow""",
              rows=rows)

        data = {}
        data["entities"] = s.run("""MATCH (e:Entity)-[:BANKS_WITH]->(b:Bank)
            RETURN e.uid AS id, e.name AS name, e.entity_type AS type, coalesce(e.industry,'') AS industry, e.is_gre AS gre,
                   e.is_qib_customer AS qib, b.name AS bank, e.pagerank AS pr, e.betweenness AS bt,
                   e.community AS comm, e.degree_in AS din, e.degree_out AS dout,
                   e.inflow_qar AS inflow, e.outflow_qar AS outflow""").data()
        # flows at (payer, payee, month, route, classification) grain: the dashboards filter on these
        # b = bank on the counterparty side (QIB for on-us), x = 1 for a self transfer
        data["flows"] = s.run("""MATCH (p:Entity)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(q:Entity)
            MATCH (cb:Bank {code: t.cp_bank_cd})
            RETURN p.uid AS s, q.uid AS t, t.month AS m, t.route AS r, t.classification AS c, cb.name AS b,
                   CASE WHEN t.is_self THEN 1 ELSE 0 END AS x, count(t) AS n, round(sum(t.amount_qar), 2) AS v
            ORDER BY s, t, m""").data()
        data["bank_flows"] = s.run("""MATCH (t:Transaction) MATCH (pb:Bank {code: t.payer_bank_cd}), (qb:Bank {code: t.payee_bank_cd})
            RETURN pb.name AS from_bank, qb.name AS to_bank, t.month AS m, count(t) AS n, round(sum(t.amount_qar),2) AS v""").data()
        data["months"] = [r["key"] for r in s.run("MATCH (m:Month) RETURN m.key AS key ORDER BY key").data()]
        data["summary"] = s.run("""MATCH (t:Transaction)
            RETURN count(t) AS txns, sum(t.amount_qar) AS total_qar,
                   sum(CASE t.route WHEN 'ON_US' THEN t.amount_qar ELSE 0 END) AS on_us_qar""").single().data()
    json.dump(data, open(out, "w"), separators=(",", ":"))
    print("entities", len(data["entities"]), "flows", len(data["flows"]), "communities", len(comms))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default="bolt://localhost:7687")
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", required=True)
    ap.add_argument("--out", default="dashboard_data.json")
    a = ap.parse_args()
    with GraphDatabase.driver(a.uri, auth=(a.user, a.password)) as d:
        run(d, a.out)
