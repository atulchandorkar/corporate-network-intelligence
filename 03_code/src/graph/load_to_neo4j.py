"""Load the synthetic QIB transactions CSV into Neo4j as a payment network.

Graph model
  (:Entity {uid, name, entity_type, industry, is_qib_customer, cif_id, home_bank_cd})
  (:Bank {code, iban_id, name})
  (:Month {key, label})
  (:Entity)-[:BANKS_WITH]->(:Bank)
  (:Entity)-[:SENT]->(:Transaction)-[:RECEIVED_BY]->(:Entity)
  (:Transaction)-[:IN_MONTH]->(:Month)
  (:Entity)-[:PAID {txn_count, total_qar, first_date, last_date, routes, classifications}]->(:Entity)   <- aggregated edge, excludes self transfers
  (:Entity)-[:OWN_ACCOUNT_AT {txn_count, moved_out_of_qib, moved_into_qib, total_qar}]->(:Bank)          <- self transfers

Every transaction is oriented as money flow: payer -> payee.
  DEBIT_CREDIT_IND = D : QIB customer pays the counterparty
  DEBIT_CREDIT_IND = C : counterparty pays the QIB customer
Mirror legs of QIB-to-QIB transfers share OUR_REFERENCE and become one Transaction node.
Self transfer (is_self = true): the same company on both sides, moving money between its own QIB account and
its own account at another bank (or a second QIB account).

Route on each transaction:
  ON_US         both accounts at QIB
  QIB_TO_OTHER  money leaves QIB to another Qatar bank
  OTHER_TO_QIB  money arrives at QIB from another Qatar bank

Usage:
  python load_to_neo4j.py --csv ../../../01_data/synthetic/qib_synthetic_transactions.csv \
      --uri bolt://localhost:7687 --user neo4j --password <password>
"""
import argparse
import pandas as pd
from neo4j import GraphDatabase

BANKS = [(4, "QISB", "Qatar Islamic Bank"), (1, "QNBA", "Qatar National Bank"), (2, "CBQA", "Commercial Bank of Qatar"),
         (3, "DOHB", "Doha Bank"), (5, "ABQQ", "Ahli Bank"), (6, "QIIB", "Qatar International Islamic Bank"),
         (7, "MAFR", "Masraf Al Rayan"), (8, "BRWA", "Dukhan Bank"), (9, "BBME", "HSBC Bank Middle East - Qatar"),
         (10, "SCBL", "Standard Chartered Bank - Qatar")]
QIB_CD = 4

GOV_WORDS = ("Ministry", "Authority", "Ashghal", "Supreme Committee", "Qatar Tourism", "Hamad Medical",
             "Qatar Investment Authority")
CHARITY_WORDS = ("Charity", "Crescent", "Foundation for Humanitarian", "Education Above All", "Zakat Fund")


def entity_type(name, company_flag, sector_name=None):
    if company_flag != "Y":
        return "Individual"
    if any(w in name for w in CHARITY_WORDS):
        return "Charity"
    if any(w in name for w in GOV_WORDS):
        return "Government"
    return "Company"


def prepare(csv_path, entities_xlsx=None):
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, na_values=["NULL"])
    df["AMOUNT_LCY"] = df.AMOUNT_LCY.astype(float)
    df["AMOUNT_FCY"] = pd.to_numeric(df.AMOUNT_FCY, errors="coerce")

    # entity master: QIB customers (account holders) + counterparties
    types, industries = {}, {}
    if entities_xlsx:
        ent = pd.read_excel(entities_xlsx, sheet_name="Entities")
        types = dict(zip(ent.ENTITY_NAME, ent.ENTITY_TYPE.replace({"Corporate": "Company", "GRE": "Company (GRE)"})))
        industries = dict(zip(ent.ENTITY_NAME, ent.INDUSTRY))
    cust = df.groupby("CUSTOMER_NAME").first()
    ents = {}
    for name, r in cust.iterrows():
        ents[name] = dict(uid="CIF_" + r.CUSTOMER_ID, name=name, is_qib_customer=True, cif_id=r.CUSTOMER_ID,
                          industry=r.INDUSTRY_NAME, sector=r.SECTOR_NAME, home_bank_cd=QIB_CD,
                          entity_type=types.get(name) or entity_type(name, "Y"))
    for name, r in df.groupby("CP_CUSTOMER_NAME").first().iterrows():
        if name in ents:
            continue
        ents[name] = dict(uid=r.UNIQUE_ID, name=name, is_qib_customer=(int(r.CP_BANK_CD) == QIB_CD), cif_id=r.MATCH_CIF_ID or None, industry=None, sector=None,
                          home_bank_cd=int(r.CP_BANK_CD),
                          entity_type=types.get(name) or entity_type(name, r.COMPANY_FLAG))
    if not types:  # without the Entities sheet, mark GREs by sector
        for e in ents.values():
            if e["entity_type"] == "Company" and (e["sector"] or "").startswith("Corp 1"):
                e["entity_type"] = "Company (GRE)"
    # industry for every entity; government bodies, charities and individuals are industries of their own
    for e in ents.values():
        t = e["entity_type"]
        e["industry"] = ("Government" if t == "Government" else "Charity & Non-Profit" if t == "Charity"
                         else "Individuals" if t == "Individual" else industries.get(e["name"]) or e["industry"] or "Other")
        e["is_gre"] = t == "Company (GRE)"

    # transactions oriented payer -> payee, mirror legs merged on OUR_REFERENCE
    txns = {}
    for r in df.itertuples(index=False):
        cust_uid, cp_uid = ents[r.CUSTOMER_NAME]["uid"], ents[r.CP_CUSTOMER_NAME]["uid"]
        payer, payee = (cust_uid, cp_uid) if r.DEBIT_CREDIT_IND == "D" else (cp_uid, cust_uid)
        cp_bank = int(r.CP_BANK_CD)
        route = "ON_US" if cp_bank == QIB_CD else ("QIB_TO_OTHER" if r.DEBIT_CREDIT_IND == "D" else "OTHER_TO_QIB")
        is_self = r.CUSTOMER_NAME == r.CP_CUSTOMER_NAME  # own-account transfer: same company on both sides
        t = txns.get(r.OUR_REFERENCE)
        if t:
            t["stmt_entry_ids"].append(r.STMT_ENTRY_ID)
            continue
        txns[r.OUR_REFERENCE] = dict(
            ref=r.OUR_REFERENCE, stmt_entry_ids=[r.STMT_ENTRY_ID], date=r.BOOKING_DATE, month=r.BOOKING_MONTH_SK,
            amount_qar=r.AMOUNT_LCY, amount_fcy=None if pd.isna(r.AMOUNT_FCY) else float(r.AMOUNT_FCY),
            currency=r.CURRENCY, classification=r.TXN_CLASSIFICATION, sub_classification=r.TXN_SUB_CLASSIFICATION,
            channel=r.CHANNEL_TYPE, txn_channel=r.TRANSACTION_CHANNEL, txn_type=r.TRANSACTION_TYPE,
            payer=payer, payee=payee, route=route, is_self=is_self, cp_bank_cd=cp_bank,
            payer_bank_cd=QIB_CD if r.DEBIT_CREDIT_IND == "D" else cp_bank,
            payee_bank_cd=cp_bank if r.DEBIT_CREDIT_IND == "D" else QIB_CD)
    return list(ents.values()), list(txns.values())


SCHEMA = [
    "CREATE CONSTRAINT entity_uid IF NOT EXISTS FOR (e:Entity) REQUIRE e.uid IS UNIQUE",
    "CREATE CONSTRAINT bank_code IF NOT EXISTS FOR (b:Bank) REQUIRE b.code IS UNIQUE",
    "CREATE CONSTRAINT txn_ref IF NOT EXISTS FOR (t:Transaction) REQUIRE t.ref IS UNIQUE",
    "CREATE CONSTRAINT month_key IF NOT EXISTS FOR (m:Month) REQUIRE m.key IS UNIQUE",
    "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
    "CREATE INDEX txn_date IF NOT EXISTS FOR (t:Transaction) ON (t.date)",
]


def batches(rows, n=1000):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def load(driver, ents, txns):
    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
        for q in SCHEMA:
            s.run(q)
        s.run("UNWIND $rows AS r MERGE (b:Bank {code: r[0]}) SET b.iban_id = r[1], b.name = r[2], b.is_qib = (r[0] = 4)",
              rows=[list(b) for b in BANKS])
        s.run("""UNWIND $rows AS r
                 MERGE (e:Entity {uid: r.uid}) SET e += r
                 WITH e, r MATCH (b:Bank {code: r.home_bank_cd}) MERGE (e)-[:BANKS_WITH]->(b)""", rows=ents)
        for chunk in batches(txns):
            s.run("""UNWIND $rows AS r
                     MERGE (m:Month {key: r.month}) ON CREATE SET m.label = substring(r.month,0,4) + '-' + substring(r.month,4,2)
                     CREATE (t:Transaction {ref: r.ref, stmt_entry_ids: r.stmt_entry_ids, date: date(r.date),
                             month: r.month, amount_qar: r.amount_qar, amount_fcy: r.amount_fcy, currency: r.currency,
                             classification: r.classification, sub_classification: r.sub_classification,
                             channel: r.channel, txn_channel: r.txn_channel, txn_type: r.txn_type, route: r.route,
                             payer_bank_cd: r.payer_bank_cd, payee_bank_cd: r.payee_bank_cd,
                             is_self: r.is_self, cp_bank_cd: r.cp_bank_cd})
                     WITH t, r, m
                     MATCH (p:Entity {uid: r.payer}), (q:Entity {uid: r.payee})
                     CREATE (p)-[:SENT]->(t)-[:RECEIVED_BY]->(q), (t)-[:IN_MONTH]->(m)""", rows=chunk)
        # aggregated payer -> payee edge for visualisation
        s.run("""MATCH (p:Entity)-[:SENT]->(t:Transaction {is_self: false})-[:RECEIVED_BY]->(q:Entity)
                 WITH p, q, count(t) AS n, sum(t.amount_qar) AS total, min(t.date) AS first, max(t.date) AS last,
                      collect(DISTINCT t.route) AS routes, collect(DISTINCT t.classification) AS classes,
                      count(DISTINCT t.month) AS active_months
                 MERGE (p)-[e:PAID]->(q)
                 SET e.txn_count = n, e.total_qar = total, e.first_date = first, e.last_date = last,
                     e.routes = routes, e.classifications = classes, e.active_months = active_months""")
        # own-account transfers: company -> the bank where its other account sits
        s.run("""MATCH (e:Entity)-[:SENT]->(t:Transaction {is_self: true})
                 MATCH (b:Bank {code: t.cp_bank_cd})
                 WITH e, b, count(t) AS n,
                      sum(CASE WHEN t.payer_bank_cd = 4 AND t.payee_bank_cd <> 4 THEN t.amount_qar ELSE 0 END) AS out_qar,
                      sum(CASE WHEN t.payee_bank_cd = 4 AND t.payer_bank_cd <> 4 THEN t.amount_qar ELSE 0 END) AS in_qar,
                      sum(t.amount_qar) AS total
                 MERGE (e)-[r:OWN_ACCOUNT_AT]->(b)
                 SET r.txn_count = n, r.moved_out_of_qib = out_qar, r.moved_into_qib = in_qar, r.total_qar = total""")
        for label in ["Entity", "Transaction", "Bank", "Month"]:
            print(label, s.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()["c"])
        print("PAID edges", s.run("MATCH ()-[r:PAID]->() RETURN count(r) AS c").single()["c"])
        print("Self transfers", s.run("MATCH (t:Transaction {is_self: true}) RETURN count(t) AS c").single()["c"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--entities-xlsx", help="optional: qib_synthetic_transactions.xlsx, for exact entity types")
    ap.add_argument("--uri", default="bolt://localhost:7687")
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", required=True)
    a = ap.parse_args()
    ents, txns = prepare(a.csv, a.entities_xlsx)
    with GraphDatabase.driver(a.uri, auth=(a.user, a.password)) as d:
        load(d, ents, txns)
