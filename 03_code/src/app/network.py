"""Ego-network logic: put one company in the centre, its direct counterparties on the first ring,
and their counterparties on the second ring, placed behind the first-level entity they trade with most."""
import math

import pandas as pd

ROUTE_LABEL = {"ON_US": "Both at QIB", "QIB_TO_OTHER": "QIB to other bank", "OTHER_TO_QIB": "Other bank to QIB"}
ROUTE_COLOR = {"ON_US": "#1f9e89", "QIB_TO_OTHER": "#e8743b", "OTHER_TO_QIB": "#3b6fd4"}
TYPE_COLOR = {"Company (GRE)": "#7a1e3a", "Company": "#c2577a", "Government": "#2f6f4f",
              "Charity": "#c9a227", "Individual": "#8a8f98"}


def pair_table(flows):
    """Aggregate flow rows into one row per payer -> payee, with the dominant route."""
    if flows.empty:
        return pd.DataFrame(columns=["s", "t", "n", "v", "route"])
    g = flows.groupby(["s", "t"]).agg(n=("n", "sum"), v=("v", "sum")).reset_index()
    dom = (flows.groupby(["s", "t", "r"]).v.sum().reset_index()
           .sort_values("v").drop_duplicates(["s", "t"], keep="last").rename(columns={"r": "route"}))
    return g.merge(dom[["s", "t", "route"]], on=["s", "t"])


def ego_network(source, ents, center, depth, m_from, m_to, routes, purposes, direction, types, max_l2, banks=None):
    """Return (l1_flows, nodes, edges, table) for the chosen centre and filters.

    Self transfers (a company paying its own account at another bank) are left out here;
    the Self transfers tab analyses them."""
    f1 = source.flows_touching([center], m_from, m_to, routes, purposes, banks)
    f1 = f1[f1.s != f1.t]
    if direction == "in":
        f1 = f1[f1.t == center]
    elif direction == "out":
        f1 = f1[f1.s == center]
    other = lambda r: r.t if r.s == center else r.s
    l1 = set(f1.apply(other, axis=1)) if len(f1) else set()
    if types:
        l1 = {u for u in l1 if ents.at[u, "type"] in types}
        f1 = f1[f1.s.isin(l1 | {center}) & f1.t.isin(l1 | {center})]

    level = {center: 0, **{u: 1 for u in l1}}
    edges_rows = [f1]
    parent = {}
    if depth == 2 and l1:
        f2 = source.flows_touching(sorted(l1), m_from, m_to, routes, purposes, banks)
        f2 = f2[(f2.s != center) & (f2.t != center) & (f2.s != f2.t)]
        p2 = pair_table(f2)
        # candidate second-level entities, strongest first
        cand = {}
        for r in p2.itertuples():
            for a, b in ((r.s, r.t), (r.t, r.s)):
                if a in l1 and b not in l1 and b != center:
                    if not types or ents.at[b, "type"] in types:
                        cand[b] = cand.get(b, 0) + r.v
                        if r.v > parent.get(b, ("", 0))[1]:
                            parent[b] = (a, r.v)
        l2 = sorted(cand, key=cand.get, reverse=True)[:max_l2]
        level.update({u: 2 for u in l2})
        keep = set(level)
        edges_rows.append(f2[f2.s.isin(keep) & f2.t.isin(keep)])
    flows = pd.concat(edges_rows, ignore_index=True) if edges_rows else f1
    pairs = pair_table(flows)

    # node totals inside the view
    vin = pairs.groupby("t").v.sum()
    vout = pairs.groupby("s").v.sum()
    nodes = []
    for u, lv in level.items():
        e = ents.loc[u]
        nodes.append(dict(id=u, name=e["name"], type=e["type"], bank=e["bank"], qib=bool(e["qib"]), level=lv,
                          industry=e.get("industry", ""), inflow=float(vin.get(u, 0)), outflow=float(vout.get(u, 0)),
                          parent=parent.get(u, (None,))[0]))
    nodes = pd.DataFrame(nodes)

    # table: one row per first/second-level entity, relative to the centre
    rows = []
    for n in nodes.itertuples():
        if n.level == 0:
            continue
        to_c = pairs[(pairs.s == n.id) & (pairs.t == center)]
        from_c = pairs[(pairs.s == center) & (pairs.t == n.id)]
        rows.append(dict(id=n.id, Entity=n.name, Type=n.type, Level="1st" if n.level == 1 else "2nd",
                         Bank=n.bank, **{"QIB customer": "Yes" if n.qib else "No"},
                         **{"Paid to centre (QAR)": round(to_c.v.sum()), "Received from centre (QAR)": round(from_c.v.sum()),
                            "Payments": int(to_c.n.sum() + from_c.n.sum()) if n.level == 1 else int(pairs[(pairs.s == n.id) | (pairs.t == n.id)].n.sum()),
                            "Via": _via_name(n, ents) if n.level == 2 else ""}))
    table = pd.DataFrame(rows)
    return f1, nodes, pairs, table


def _via_name(n, ents):
    return ents.at[n.parent, "name"] if n.parent in ents.index else ""


def ring_positions(nodes, pairs, center, width=1000):
    """Preset layout: centre at 0,0; first level on a ring; each second-level entity on an outer ring,
    behind its strongest first-level link."""
    pos = {center: (0.0, 0.0)}
    l1 = nodes[nodes.level == 1].copy()
    if l1.empty:
        return pos
    l1["flow"] = l1.inflow + l1.outflow
    order = ["Government", "Company (GRE)", "Company", "Charity", "Individual"]
    l1["k"] = l1.type.map({t: i for i, t in enumerate(order)})
    l1 = l1.sort_values(["k", "flow"], ascending=[True, False])
    n1 = len(l1)
    r1 = max(320, 34 * n1 / (2 * math.pi) * 2.2)
    angle = {}
    for i, u in enumerate(l1.id):
        a = 2 * math.pi * i / n1 - math.pi / 2
        angle[u] = a
        pos[u] = (r1 * math.cos(a), r1 * math.sin(a))
    l2 = nodes[nodes.level == 2]
    if not l2.empty:
        groups = l2.groupby("parent")
        slot = 2 * math.pi / n1
        for p, g in groups:
            base = angle.get(p, 0)
            k = len(g)
            for j, u in enumerate(g.sort_values("inflow", ascending=False).id):
                ring = j % 2
                spread = slot * 0.85
                a = base + (spread * ((j + 0.5) / k - 0.5) if k > 1 else 0)
                r2 = r1 + 260 + ring * 110
                pos[u] = (r2 * math.cos(a), r2 * math.sin(a))
    return pos
