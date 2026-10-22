# Qatar payment network: Neo4j graph model and dashboards

## Graph model

```
(:Entity)-[:BANKS_WITH]->(:Bank)
(:Entity)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(:Entity)
(:Transaction)-[:IN_MONTH]->(:Month)
(:Entity)-[:PAID {txn_count, total_qar, first_date, last_date, routes, classifications, active_months}]->(:Entity)
(:Entity)-[:OWN_ACCOUNT_AT {txn_count, moved_out_of_qib, moved_into_qib, total_qar}]->(:Bank)
```

| Node | Count | Key properties |
|---|---|---|
| Entity | 138 | name, entity_type (Company (GRE), Company, Government, Charity, Individual), is_qib_customer, industry, is_gre, pagerank, betweenness, community, inflow_qar, outflow_qar |
| Transaction | 4,920 | ref (OUR_REFERENCE), date, amount_qar, amount_fcy, currency, classification, channel, route, payer_bank_cd, payee_bank_cd, cp_bank_cd, is_self |
| Bank | 10 | code, iban_id, name |
| Month | 12 | key (YYYYMM), label |

`PAID` is the aggregated payer-to-payee link (773 of them) that the network map draws. It leaves out self transfers, which `OWN_ACCOUNT_AT` records instead.

### How rows become the graph
- Every transaction is turned into money flow from payer to payee. A debit (D) means the QIB customer paid the counterparty; a credit (C) means the counterparty paid the customer.
- **Route** says where the money went:
  - `ON_US` means both accounts are at QIB.
  - `QIB_TO_OTHER` means money leaves QIB for another Qatar bank.
  - `OTHER_TO_QIB` means money arrives at QIB from another bank.
- When one QIB customer pays another, the CSV can hold the payment twice, once on each side's statement. Both rows share `OUR_REFERENCE`, so they become one Transaction node. That is why the 5,453 CSV rows become 4,920 transactions.

### Network metrics (computed by `analytics_and_export.py`, stored on Entity)
- **Influence (PageRank):** weighted by QAR. It is high when large payers send money to the entity.
- **Brokerage (betweenness):** high when the entity is the bridge between groups that otherwise don't trade.
- **Cluster (Louvain community):** groups of entities that mostly pay each other.

These are computed with NetworkX, so they run on Neo4j Community. With the Graph Data Science plugin installed, `gds.pageRank` and `gds.louvain` give the same kind of result.

## How to run it on your Mac
1. Start Neo4j. Install Docker Desktop, set `NEO4J_PASSWORD`, then run `docker compose -f 03_code/config/neo4j/docker-compose.yml up -d`.
2. Load the data. Either:
   - load the ready-made database: `neo4j-admin database load neo4j --from-path=01_data/processed` (the file is `qatar_payment_graph.neo4j.dump`, renamed to `neo4j.dump`), or
   - rebuild it from the CSV:
     ```
     pip install neo4j networkx scipy pandas openpyxl
     python 03_code/src/graph/load_to_neo4j.py --csv 01_data/synthetic/qib_synthetic_transactions.csv \
         --entities-xlsx 01_data/synthetic/qib_synthetic_transactions.xlsx --password $NEO4J_PASSWORD
     python 03_code/src/graph/analytics_and_export.py --password $NEO4J_PASSWORD --out 01_data/processed/dashboard_data.json
     ```
3. Explore. Open http://localhost:7474 and run the queries in `03_code/src/graph/cypher/business_queries.cypher`:
   - the whole network
   - hubs
   - one company's ego network
   - bank corridors
   - on-us vs off-us by month
   - cross-sell leads
   - government flows
   - clusters
   - two-hop supply chains
   - concentration risk
   - self transfers by company and bank
   - where customers hold their other accounts
   - bank analytics
   - industry-to-industry flows

## Dashboard pages
1. **Overview:** five headline figures, a monthly value chart by bank route, and written insights that update with the filters.
2. **Network map:** a force-directed map of who pays whom.
   - Dots are sized by flow and coloured by entity type. QIB customers have a dark ring.
   - Lines are coloured by bank route.
   - Click a dot to see that entity's profile, top payers and top payees.
3. **Hubs and clusters:** a sortable, searchable table of influence, brokerage, money in and out, and counterparties, plus a card for each Louvain cluster.
4. **Bank corridors:** QIB outflow and inflow with each Qatar bank, and the route mix for each purpose.
5. **Who pays whom:** a matrix of payer type against payee type, and value by purpose.

All pages share the same filters: month range, bank route, counterparty type and purpose.

All data is synthetic.

## Network explorer (company-centred view)
- Plotly Dash app: `03_code/src/app/` (see its README). Reads Neo4j live, or the JSON exports when no database is running.
- Shareable web version with the same views: `05_visualizations/interactive/qatar_network_explorer.html` (rebuild with `explorer_src/build.py` after reloading Neo4j).
- First level = entities that paid or were paid by the centre company. Second level = their counterparties, excluding the centre, ranked by value and capped by the "second-level entities" control.
- Every transaction has a QIB account on one side: the QIB customer's own account (O_BANK_CD = 4). Counterparties that also bank with QIB carry a CIF (MATCH_CIF_ID) and show as QIB customers.

## Self transfers, banks and industries
- **Self transfer:** the same company is on both sides (`is_self = true`), for example QatarEnergy paying from its QIB account to its own account at Doha Bank. There are 320 of them across 29 companies (QAR 882M). They are left out of the company network, the PAID links and the industry flows, and analysed on their own tab: where each company keeps its other accounts, money moved out of and back into QIB, by company, by bank and by month. A company that keeps moving its own money out of QIB is a deposit-retention lead.
- **Banks:** `cp_bank_cd` is the bank on the other side of each payment. QIB itself is the counterparty bank when both accounts are at QIB. The bank filter, and the Banks tab, use it: value QIB pays to and receives from each bank, the customers using it, the counterparties banking there, purposes and months.
- **Industries:** every entity has an industry. Government bodies are the "Government" industry; charities are "Charity & Non-Profit"; individuals are "Individuals". Government-related companies (GREs) can be grouped as one industry, "Government-related (GRE)", or shown under their own sector. The Industry flows tab shows a Sankey (payer industry to payee industry), a matrix and each industry's net position.

## RM brief (company view for relationship managers)
Pick a company at the top; every tab follows it. The RM brief tab writes the analysis in plain sentences from the filtered transactions:
- **Headline:** receipts, payments, number of payers and suppliers, net flow. Non-QIB entities are flagged as prospects.
- **Insights:** recent trend (last three months against the three before), customer and supplier concentration, dependence on government payers, the share of payments going to suppliers at other banks, self transfers, peak month and cash-gap months, new and lapsed counterparties, and network rank.
- **Recommendations** (ranked by the QAR involved, each naming who to start with): bring a non-customer to QIB; onboard suppliers and offer supply-chain finance (15%+ of payments to other banks); capture receivables or finance government receivables (25%+ of receipts from other banks); keep liquidity at QIB (net self-transfer outflow); working-capital line (3+ cash-gap months); customer concentration (one payer 40%+); falling (−20%) or rising (+25%) receipts; lapsed counterparties; payroll mandate. Credit-style recommendations are skipped for government bodies.
- The same logic lives in `explorer_src/template.html` (web) and `03_code/src/app/rm_brief.py` (Dash).

Two web builds come from `explorer_src/build.py`: `qatar_network_explorer.html` (neutral styling) and `qib_network_explorer_branded.html` (QIB logo, blue #0075B0 and orange #DF7A00, Open Sans, taken from qib.com.qa).
