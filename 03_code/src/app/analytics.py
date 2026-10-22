"""Self-transfer, bank and industry analytics over the flow table (s, t, m, r, c, b, x, n, v).

Every flow has a QIB account on one side. `b` is the bank on the other side: another Qatar bank, or
Qatar Islamic Bank itself when both accounts are at QIB (route ON_US).
"""
import pandas as pd

QIB = "Qatar Islamic Bank"
GRE = "Government-related (GRE)"


def filter_flows(flows, m_from, m_to, routes, banks, purposes, types=None, ents=None):
    keep = (flows.m >= m_from) & (flows.m <= m_to) & flows.r.isin(routes or []) & flows.b.isin(banks or [])
    if purposes:
        keep &= flows.c.isin(purposes)
    df = flows[keep]
    if types is not None and ents is not None:
        # counterparty type filter, on the side that is not the QIB account holder
        df = df[cp_side(df).map(ents.type).isin(types)]
    return df


def qib_side(df):
    """The QIB customer in each flow: payer when money leaves QIB, payee when it arrives."""
    return df.s.where(df.r != "OTHER_TO_QIB", df.t)


def cp_side(df):
    return df.t.where(df.r != "OTHER_TO_QIB", df.s)


# ---------- self transfers ----------

def self_by_company_bank(df):
    """One row per company and the bank holding its other account."""
    s = df[df.x == 1]
    if s.empty:
        return pd.DataFrame(columns=["id", "bank", "n", "out", "inn", "on", "net"])
    g = s.assign(out=s.v.where(s.r == "QIB_TO_OTHER", 0), inn=s.v.where(s.r == "OTHER_TO_QIB", 0),
                 on=s.v.where(s.r == "ON_US", 0))
    g = g.groupby(["s", "b"]).agg(n=("n", "sum"), out=("out", "sum"), inn=("inn", "sum"), on=("on", "sum")).reset_index()
    g = g.rename(columns={"s": "id", "b": "bank"})
    g["net"] = g.out - g.inn
    return g.sort_values("out", ascending=False)


# ---------- banks ----------

def bank_table(df):
    """One row per counterparty bank: value QIB pays to it, receives from it, and within QIB."""
    if df.empty:
        return pd.DataFrame(columns=["bank", "total", "share", "pays", "receives", "within", "n", "customers", "selfv"])
    d = df.assign(q=qib_side(df), pays=df.v.where(df.r == "QIB_TO_OTHER", 0),
                  receives=df.v.where(df.r == "OTHER_TO_QIB", 0), within=df.v.where(df.r == "ON_US", 0),
                  selfv=df.v.where(df.x == 1, 0))
    g = d.groupby("b").agg(total=("v", "sum"), pays=("pays", "sum"), receives=("receives", "sum"),
                           within=("within", "sum"), n=("n", "sum"), customers=("q", "nunique"), selfv=("selfv", "sum"))
    g["share"] = g.total / g.total.sum()
    return g.reset_index().rename(columns={"b": "bank"}).sort_values("total", ascending=False)


# ---------- industries ----------

def industry_of(ents, group_gre=True):
    ind = ents.industry.copy()
    if group_gre:
        ind[ents.gre.astype(bool) & (ents.type != "Government")] = GRE
    return ind


def industry_pairs(df, ents, group_gre=True, include_individuals=False):
    """Payer industry -> payee industry, self transfers excluded."""
    d = df[df.x == 0]
    ind = industry_of(ents, group_gre)
    d = d.assign(fi=d.s.map(ind), ti=d.t.map(ind))
    if not include_individuals:
        d = d[(d.fi != "Individuals") & (d.ti != "Individuals")]
    return d.groupby(["fi", "ti"]).agg(v=("v", "sum"), n=("n", "sum")).reset_index().sort_values("v", ascending=False)
