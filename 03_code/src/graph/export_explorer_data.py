"""Export the three JSON files the dashboard is built from, straight from Neo4j.

    python export_explorer_data.py --password <pw> [--uri bolt://localhost:7687] [--out ../../../01_data/processed]

Writes neo4j_entities.json, neo4j_flows.json and neo4j_bank_flows.json. Run analytics_and_export.py first so every
entity has its PageRank, betweenness and community. Then rebuild the page with 05_visualizations/explorer_src/build.py.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from data_access import Neo4jSource  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", default="bolt://localhost:7687")
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", required=True)
    ap.add_argument("--out", default=str(ROOT / "01_data" / "processed"))
    a = ap.parse_args()
    src, out = Neo4jSource(a.uri, a.user, a.password), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, df in (("neo4j_entities", src.entities()), ("neo4j_flows", src.all_flows()), ("neo4j_bank_flows", src.bank_flows())):
        rows = json.loads(df.to_json(orient="records"))
        (out / f"{name}.json").write_text(json.dumps(rows, separators=(",", ":")))
        print(f"wrote {name}.json ({len(rows)} rows)")


if __name__ == "__main__":
    main()
