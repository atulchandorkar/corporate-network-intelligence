// Business queries for the Qatar payment network. Paste into Neo4j Browser (http://localhost:7474) or Bloom.

// 1. The whole network, largest 200 relationships (Browser draws it as a graph)
MATCH (p:Entity)-[r:PAID]->(q:Entity)
RETURN p, r, q ORDER BY r.total_qar DESC LIMIT 200;

// 2. Hubs: who receives the most money, with influence (PageRank) and brokerage (betweenness)
MATCH (e:Entity)
RETURN e.name, e.entity_type, e.is_qib_customer, round(e.inflow_qar) AS inflow_qar, round(e.outflow_qar) AS outflow_qar,
       round(e.pagerank, 4) AS influence, round(e.betweenness, 3) AS brokerage, e.degree_in AS payers, e.degree_out AS payees
ORDER BY e.pagerank DESC LIMIT 25;

// 3. One company's ego network (change the name)
MATCH (c:Entity {name: 'Qatar Airways Group'})-[r:PAID]-(other)
RETURN c, r, other;

// 4. Bank corridors: QIB versus each other Qatar bank, by direction
MATCH (t:Transaction) WHERE t.route <> 'ON_US'
MATCH (pb:Bank {code: t.payer_bank_cd}), (qb:Bank {code: t.payee_bank_cd})
RETURN pb.name AS from_bank, qb.name AS to_bank, count(t) AS payments, round(sum(t.amount_qar)) AS value_qar
ORDER BY value_qar DESC;

// 5. On-us (both at QIB) vs off-us by month
MATCH (t:Transaction)-[:IN_MONTH]->(m:Month)
RETURN m.label AS month, t.route AS route, count(t) AS payments, round(sum(t.amount_qar)) AS value_qar
ORDER BY month, route;

// 6. QIB cross-sell leads: non-customers that QIB customers pay or receive from the most
MATCH (c:Entity {is_qib_customer: true})-[r:PAID]-(x:Entity {is_qib_customer: false})
WHERE x.entity_type <> 'Individual'
WITH x, count(DISTINCT c) AS qib_counterparties, sum(r.total_qar) AS value
MATCH (x)-[:BANKS_WITH]->(b:Bank)
RETURN x.name, x.entity_type, b.name AS current_bank, qib_counterparties, round(value) AS value_qar
ORDER BY value DESC LIMIT 20;

// 7. Government flows: which ministries pay which companies
MATCH (g:Entity {entity_type: 'Government'})-[r:PAID]->(c:Entity)
RETURN g.name AS ministry, c.name AS company, r.txn_count AS payments, round(r.total_qar) AS value_qar
ORDER BY value_qar DESC LIMIT 30;

// 8. Clusters (Louvain community) and their members
MATCH (e:Entity)
RETURN e.community AS cluster, count(*) AS members, collect(e.name)[0..8] AS sample_members
ORDER BY cluster;

// 9. Two-hop supply chains: A pays B, B pays C, within 30 days
MATCH (a:Entity)-[:SENT]->(t1:Transaction)-[:RECEIVED_BY]->(b:Entity)-[:SENT]->(t2:Transaction)-[:RECEIVED_BY]->(c:Entity)
WHERE a <> c AND t2.date >= t1.date AND t2.date <= t1.date + duration('P30D') AND t1.amount_qar > 1000000
RETURN a.name, b.name, c.name, t1.date, round(t1.amount_qar) AS first_leg, t2.date, round(t2.amount_qar) AS second_leg
ORDER BY first_leg DESC LIMIT 25;

// 10. Concentration risk: customers whose top counterparty is over 40% of their inflow
MATCH (c:Entity {is_qib_customer: true})<-[r:PAID]-(p)
WITH c, p, r.total_qar AS v, c.inflow_qar AS total WHERE total > 0
WITH c, max(v) AS top, total
WHERE top / total > 0.4
RETURN c.name, round(100.0 * top / total, 1) AS top_payer_share_pct, round(total) AS inflow_qar
ORDER BY top_payer_share_pct DESC;

// 11. Self transfers: companies moving money between their QIB account and their own account at another bank
MATCH (e:Entity)-[:SENT]->(t:Transaction {is_self: true})-[:RECEIVED_BY]->(e)
MATCH (b:Bank {code: t.cp_bank_cd})
RETURN e.name AS company, b.name AS other_bank,
       sum(CASE WHEN t.route = 'QIB_TO_OTHER' THEN t.amount_qar ELSE 0 END) AS out_of_qib,
       sum(CASE WHEN t.route = 'OTHER_TO_QIB' THEN t.amount_qar ELSE 0 END) AS into_qib,
       count(t) AS transfers
ORDER BY out_of_qib - into_qib DESC;

// 12. Where QIB customers hold their other accounts
MATCH (e:Entity)-[o:OWN_ACCOUNT_AT]->(b:Bank)
RETURN e, o, b;

// 13. Bank analytics: QIB pays, receives and keeps on-us, per counterparty bank
MATCH (t:Transaction)
MATCH (b:Bank {code: t.cp_bank_cd})
RETURN b.name AS bank,
       sum(CASE WHEN t.route = 'QIB_TO_OTHER' THEN t.amount_qar ELSE 0 END) AS qib_pays,
       sum(CASE WHEN t.route = 'OTHER_TO_QIB' THEN t.amount_qar ELSE 0 END) AS qib_receives,
       sum(CASE WHEN t.route = 'ON_US' THEN t.amount_qar ELSE 0 END) AS within_qib,
       count(t) AS payments
ORDER BY qib_pays + qib_receives + within_qib DESC;

// 14. Industry to industry flows (self transfers excluded; government is an industry)
MATCH (a:Entity)-[:SENT]->(t:Transaction {is_self: false})-[:RECEIVED_BY]->(b:Entity)
WITH CASE WHEN a.is_gre AND a.entity_type <> 'Government' THEN 'Government-related (GRE)' ELSE a.industry END AS from_industry,
     CASE WHEN b.is_gre AND b.entity_type <> 'Government' THEN 'Government-related (GRE)' ELSE b.industry END AS to_industry, t
RETURN from_industry, to_industry, round(sum(t.amount_qar)) AS qar, count(t) AS payments
ORDER BY qar DESC LIMIT 30;
