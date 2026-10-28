# Corporate Network Intelligence: on-premises installation

The whole solution runs inside your own network. **The dashboard needs no internet access.** It is one self-contained HTML file: the chart libraries (Cytoscape.js and Plotly.js), the Open Sans font, the bank logos, the icons and the data are all inside it. Checked by opening it in a browser with networking switched off: no outside requests and no errors.

The only steps that use the internet are one-off installs (Python packages and the Neo4j software). Section 5 shows how to do those on a connected machine and carry the files in.

## 1. What is in this package

| Folder / file | What it is |
|---|---|
| `docs/index.html` | **The dashboard.** Open it in Chrome or Edge, or put it on any internal web server. |
| `01_data/synthetic/` | The synthetic transaction file (CSV, 46 fields). Replace it with real data later. |
| `01_data/processed/` | The JSON files the dashboard is built from, plus a ready-made Neo4j 5.26 database dump. |
| `03_code/scripts/` | Synthetic data generator (`gen.py`, `write.py`). Not needed for real data. |
| `03_code/src/graph/` | Pipeline: load the CSV into Neo4j, compute network metrics, export the dashboard data. |
| `03_code/src/app/` | Optional Python (Plotly Dash) web app. It is an earlier version: the HTML dashboard has the latest tabs and design. |
| `03_code/config/neo4j/docker-compose.yml` | Neo4j Community 5.26 in Docker. No plugins needed. |
| `05_visualizations/explorer_src/` | Dashboard source: `template.html`, `build.py`, bank logos, type icons and `vendor/` (offline chart libraries and font). |
| `08_documentation/` | Data dictionary and methodology. |

## 2. Fastest start: the dashboard only (5 minutes, nothing to install)

1. Unzip the package.
2. Double-click `docs/index.html`. It opens in the browser and works offline.
3. To share it inside the office, copy `docs/index.html` to any internal web server (IIS, Apache, nginx or a SharePoint document library that serves HTML) and share that internal URL.

   Quick test server on any machine with Python: `cd docs` and then `python -m http.server 8080`, then open `http://<machine-name>:8080`.

## 3. Full pipeline: real data → Neo4j → dashboard

Requirements: Python 3.10 or newer, and Neo4j 5.x Community (Docker, Neo4j Desktop or the Windows/Linux server install).

```
# 1. Python packages (offline install: see section 5)
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r 03_code/requirements.txt

# 2. Start Neo4j (Docker example; choose your own password)
set NEO4J_PASSWORD=YourStrongPassword          # macOS/Linux: export NEO4J_PASSWORD=...
docker compose -f 03_code/config/neo4j/docker-compose.yml up -d

# 3. Load the transactions (same 46-field layout as 01_data/synthetic/qib_synthetic_transactions.csv)
cd 03_code/src/graph
python load_to_neo4j.py --csv ../../../01_data/synthetic/qib_synthetic_transactions.csv --password %NEO4J_PASSWORD%

# 4. Network metrics (PageRank, betweenness, communities), written back to Neo4j
python analytics_and_export.py --password %NEO4J_PASSWORD% --out ../../../01_data/processed/dashboard_data.json

# 5. Export the dashboard data from Neo4j
python export_explorer_data.py --password %NEO4J_PASSWORD%

# 6. Rebuild the dashboard file (standard library only, no packages needed)
cd ../../../05_visualizations/explorer_src
python build.py                      # writes docs/index.html
```

Repeat steps 3 to 6 whenever new data arrives (for example as a nightly scheduled task).

**Skip steps 3 and 4 for a quick look at the graph:** load the ready-made database instead. Rename `01_data/processed/qatar_payment_graph.neo4j.dump` to `neo4j.dump` and run `neo4j-admin database load --from-path=01_data/processed --overwrite-destination=true neo4j` with Neo4j stopped.

Neo4j Browser: `http://localhost:7474`. Example business queries are in `03_code/src/graph/cypher/business_queries.cypher`.

## 4. Optional: the Python web app

```
pip install -r 03_code/src/app/requirements.txt
cd 03_code/src/app
python app.py                                   # http://127.0.0.1:8050
gunicorn app:server -b 0.0.0.0:8050             # Linux server, for colleagues
```

It reads Neo4j when `NEO4J_URI`, `NEO4J_USER` and `NEO4J_PASSWORD` are set, otherwise the JSON files in `01_data/processed`. Fonts are served from `assets/`, so it also runs offline.

## 5. Installing on a machine with no internet

**Python packages:** on a connected machine with the same operating system and Python version, run:
```
pip download -r 03_code/requirements.txt -r 03_code/src/app/requirements.txt -d wheels
```
Copy the `wheels` folder across, then on the offline machine run:
```
pip install --no-index --find-links wheels -r 03_code/requirements.txt -r 03_code/src/app/requirements.txt
```

**Neo4j with Docker:** on a connected machine run `docker pull neo4j:5.26-community` and `docker save neo4j:5.26-community -o neo4j-5.26.tar`. Copy the tar file across and run `docker load -i neo4j-5.26.tar` on the offline machine.

**Neo4j without Docker:** download the Neo4j 5.26 Community server zip (Windows) or tar (Linux) from neo4j.com on a connected machine and copy it across. It needs Java 17 or 21.

## 6. Moving to real data: points to check

- **Data:** the pipeline expects the 46-field layout in `08_documentation/data_dictionary/`. The dashboard shows a "Synthetic data" badge in the header; remove it in `05_visualizations/explorer_src/build.py` (`plain_bar`) once real data is used.
- **Security:** the dashboard file contains the data it shows, so treat `docs/index.html` with the same classification as the source data. Host it only on internal servers with access control, and do not email it outside the bank. Keep the Neo4j password out of scripts: use environment variables.
- **Size:** the page holds every flow for the period. For very large volumes (many thousands of companies), build one file per segment or region, or use the Dash app against Neo4j so the data stays on the server.
- **Licences:** Cytoscape.js (MIT), Plotly.js (MIT), Open Sans (SIL OFL 1.1), Neo4j Community (GPLv3) and the Flaticon icons (free licence with attribution). Bank logos belong to their owners and are used only to identify each bank.
