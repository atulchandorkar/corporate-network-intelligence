# QIB payment network explorer (Plotly Dash)

Pick a company. It sits in the centre, its direct counterparties form the first ring, and their counterparties form the second ring (placed behind the first-level entity they trade with most).

The company picked in the top bar is the primary filter: every tab follows it. The "This company / All QIB customers" switch decides whether the Self transfers, Banks and Industry flows tabs show that company only or the whole portfolio. Filters on the left apply to every tab: months, bank route (both at QIB / QIB to other bank / other bank to QIB), counterparty bank (QIB, QNB, Doha Bank, CBQ and the rest), counterparty type and purpose. The Company network tab adds network depth, money direction, number of second-level entities and ring or force layout. Click any dot to re-centre on it.

Tabs:
- **RM brief:** a headline, KPIs, written insights, ranked recommendations for the relationship manager, top customers and suppliers, monthly receipts and payments, banks and industries on the other side, and new and lapsed relationships (logic in `rm_brief.py`).
- **Company network:** the first- and second-level network of one company (self transfers excluded).
- **Self transfers:** companies moving money between their QIB account and their own account at another bank (or a second QIB account): a company-to-bank network, out of QIB vs back in by company and by bank, net leakage by month, and a detail table.
- **Banks:** QIB in the centre with every Qatar bank around it, a table per bank, and a drill-down for one bank (monthly flows, purposes, QIB customers using it, counterparties banking there).
- **Industry flows:** a Sankey of payer industry to payee industry, an industry matrix and net position. Government is an industry; GREs can be grouped or shown by sector.
- **QIB overview:** the largest relationships, bank corridors and the most influential entities.

## Run locally
```
cd 03_code/src/app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export NEO4J_PASSWORD=...      # optional; without it the app reads 01_data/processed/*.json
python app.py                  # open http://127.0.0.1:8050
```

## Host it for colleagues
`gunicorn app:server -b 0.0.0.0:8050` on any internal server, or deploy to Dash Enterprise, Render or Azure App Service. Set NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD as environment variables.

## Files
- `app.py`: layout and callbacks
- `network.py`: first- and second-level network logic and the ring layout
- `data_access.py`: Neo4j queries, with a fallback to the exported JSON files
- `analytics.py`: self-transfer, bank and industry calculations
- `rm_brief.py`: the RM brief (insight sentences and recommendation rules)
- `assets/qib_logo.png`: logo taken from the qib.com.qa header at screen resolution; replace it with the official SVG from the brand team for print quality
