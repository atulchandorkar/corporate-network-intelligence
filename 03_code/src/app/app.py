"""QIB payment network explorer (Plotly Dash + Cytoscape).

Tabs:
  RM brief          summary, top customers and suppliers, written insights and recommendations for the relationship manager
  Company network   one company in the centre, its direct counterparties on the first ring, theirs on the second
  Self transfers    a company moving money between its QIB account and its own account elsewhere
  Banks             QIB's flows with each Qatar bank (QNB, Doha Bank, CBQ, ...) and QIB-to-QIB
  Industry flows    money moving from one industry to another (Sankey + matrix); government is an industry
  QIB overview      the largest relationships across all QIB customers
Every transaction in the data has a QIB account on one side. The company picked at the top is the primary filter;
the filters on the left apply to every tab. Branding (logo in assets/, QIB blue and orange, Open Sans) is for internal use.

Run:
  pip install -r requirements.txt
  export NEO4J_PASSWORD=...          # optional: without it the app reads 01_data/processed/*.json
  python app.py                      # http://127.0.0.1:8050
"""
from pathlib import Path

import dash_cytoscape as cyto
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update

import rm_brief
from analytics import QIB, bank_table, cp_side, filter_flows, industry_of, industry_pairs, qib_side, self_by_company_bank
from data_access import open_source
from network import ROUTE_COLOR, ROUTE_LABEL, TYPE_COLOR, ego_network, pair_table, ring_positions

SRC = open_source()
ENTS = SRC.entities().set_index("id", drop=False)
ALL_FLOWS = SRC.all_flows()
ALL_FLOWS["m"] = ALL_FLOWS.m.astype(str)
MONTHS = sorted(ALL_FLOWS.m.unique())
PURPOSES = sorted(ALL_FLOWS.c.unique())
BANKS = ALL_FLOWS.groupby("b").v.sum().sort_values(ascending=False).index.tolist()
BANKS = [QIB] + [b for b in BANKS if b != QIB]
TYPES = ["Company (GRE)", "Company", "Government", "Charity", "Individual"]
DEFAULT = ENTS[ENTS.name == "Qatar Airways Group"].index[0] if (ENTS.name == "Qatar Airways Group").any() else ENTS.index[0]
MONTH_LABEL = {i: pd.Timestamp(m[:4] + "-" + m[4:] + "-01").strftime("%b %y") for i, m in enumerate(MONTHS)}
OUT_C, IN_C, ON_C, ACCENT, ORANGE = "#DF7A00", "#4f63d2", ROUTE_COLOR["ON_US"], "#0075B0", "#DF7A00"

QAR = lambda v: ("−" if v < 0 else "") + "QAR " + (f"{abs(v)/1e9:,.2f}B" if abs(v) >= 1e9 else f"{abs(v)/1e6:,.1f}M" if abs(v) >= 1e6 else f"{abs(v)/1e3:,.0f}K")
short = lambda s: (s.split(" (")[0] if len(s) > 26 else s)[:30]
bank_lbl = lambda b: "QIB (both sides)" if b == QIB else b
name = lambda u: ENTS.at[u, "name"] if u in ENTS.index else u

company_opts = [{"label": f"{r.name}  ·  {r.type}{'  ·  QIB' if r.qib else ''}", "value": r.id}
                for r in ENTS.sort_values("name").itertuples()]

STYLE = [
    {"selector": "node", "style": {
        "background-color": "data(color)", "width": "data(size)", "height": "data(size)", "label": "data(label)",
        "font-size": 11, "color": "#1d1d24", "text-valign": "bottom", "text-margin-y": 4,
        "text-background-color": "#ffffff", "text-background-opacity": 0.75, "text-background-padding": 2,
        "border-width": 1, "border-color": "#ffffff"}},
    {"selector": "node[?qib]", "style": {"border-width": 3, "border-color": "#1d1d24"}},
    {"selector": "node[?bank_node]", "style": {"shape": "round-rectangle", "font-weight": "bold"}},
    {"selector": "node[level = 0]", "style": {"font-size": 14, "font-weight": "bold", "border-width": 5,
                                              "border-color": "#c9a227", "z-index": 10}},
    {"selector": "node[level = 2]", "style": {"opacity": 0.85, "font-size": 9}},
    {"selector": "edge", "style": {
        "line-color": "data(color)", "target-arrow-color": "data(color)", "target-arrow-shape": "triangle",
        "arrow-scale": 0.8, "width": "data(w)", "curve-style": "bezier", "opacity": 0.55}},
    {"selector": "edge[?plain]", "style": {"target-arrow-shape": "none", "opacity": 0.7}},
    {"selector": "edge[tier = 2]", "style": {"opacity": 0.18, "line-style": "dashed"}},
    {"selector": ":selected", "style": {"border-color": "#c9a227", "border-width": 5}},
]
FONT = dict(family="Open Sans, Segoe UI, sans-serif", color="#00111A")
TABLE_KW = dict(page_size=12, sort_action="native", style_table={"overflowX": "auto"},
                style_cell={"fontFamily": "Open Sans, Segoe UI, system-ui, sans-serif", "fontSize": 13, "padding": "6px", "textAlign": "left"},
                style_header={"fontWeight": "600", "backgroundColor": "#e2f0f8"})

app = Dash(__name__, title="QIB payment network explorer", suppress_callback_exceptions=True)
server = app.server

card = lambda title, id_: html.Div([html.Div(title, className="k-label"), html.Div("—", id=id_, className="k-val")], className="kpi")
panel = lambda title, note, *children: html.Div([html.H3(title), html.P(note, className="note"), *children], className="panel")
graph = lambda id_: dcc.Graph(id=id_, config={"displayModeBar": False})


def money_cols(cols, money=(), ints=()):
    return [{"name": n, "id": i, "type": "numeric", "format": {"specifier": ",.0f"}} if i in money or i in ints
            else {"name": n, "id": i} for i, n in cols]


filters = html.Aside(className="controls", children=[
    html.Label("Bank route"),
    dcc.Checklist(id="routes", value=list(ROUTE_LABEL), options=[{"label": " " + v, "value": k} for k, v in ROUTE_LABEL.items()]),
    html.Label("Counterparty bank"),
    html.Div([html.Button("All", id="banks-all", className="mini"), html.Button("None", id="banks-none", className="mini")]),
    dcc.Checklist(id="banks", value=BANKS, options=[{"label": " " + bank_lbl(b), "value": b} for b in BANKS]),
    html.Label("Counterparty type"),
    dcc.Checklist(id="types", value=TYPES, options=[{"label": " " + t, "value": t} for t in TYPES]),
    html.Label("Purpose"),
    dcc.Dropdown(id="purposes", options=PURPOSES, multi=True, placeholder="All purposes"),
])

topbar = html.Div(className="topbar", children=[
    html.Div([html.Label("Company"), dcc.Dropdown(id="center", options=company_opts, value=DEFAULT, clearable=False)], style={"minWidth": "340px", "flex": "2"}),
    html.Div([html.Label("Period"), dcc.RangeSlider(id="months", min=0, max=len(MONTHS) - 1, step=1, value=[0, len(MONTHS) - 1],
                                                    marks={i: MONTH_LABEL[i] for i in range(0, len(MONTHS), 3)})], style={"minWidth": "320px", "flex": "2"}),
    html.Div([html.Label("Self transfers, Banks and Industry tabs show"), dcc.RadioItems(id="scope", value="co", inline=True, options=[
        {"label": " This company ", "value": "co"}, {"label": " All QIB customers", "value": "all"}])]),
])

brief_tab = html.Div(className="main", children=[
    html.Div(className="panel", children=[html.H2(id="br-title"), html.Div(id="br-chips", className="chips"), html.P(id="br-head", className="headline")]),
    html.Div(className="kpis", children=[card("Receipts (money in)", "br-in"), card("Payments (money out)", "br-out"), card("Net flow", "br-net"),
                                         card("Paying customers", "br-nc"), card("Suppliers paid", "br-ns"), card("Paid to other banks", "br-leak"),
                                         card("Own money moved out", "br-self")]),
    html.Div(className="row2", children=[
        panel("Key insights", "Written from the transactions in the period and filters you picked.", html.Ul(id="br-ins", className="insights")),
        panel("Recommendations for the relationship manager", "Ranked by the money involved. Each one names the counterparties to start with.", html.Div(id="br-recs", className="recs")),
    ]),
    html.Div(className="row2", children=[
        html.Div([html.H3("Top customers (who pays this company)"), dash_table.DataTable(id="br-cust", **TABLE_KW)]),
        html.Div([html.H3("Top suppliers (who this company pays)"), dash_table.DataTable(id="br-supp", **TABLE_KW)]),
    ]),
    html.Div(className="row2", children=[graph("br-month"), graph("br-bank")]),
    html.Div(className="row2", children=[graph("br-ind"), html.Div([html.H3("New and lapsed relationships"), dash_table.DataTable(id="br-change", **TABLE_KW)])]),
])

ego_tab = html.Div(className="main", children=[
    html.Div(className="egoctl", children=[
        html.Div([html.Label("Network depth"), dcc.RadioItems(id="depth", value=2, inline=True, options=[
            {"label": " 1st level ", "value": 1}, {"label": " 1st + 2nd level", "value": 2}])]),
        html.Div([html.Label("Money direction (vs centre)"), dcc.RadioItems(id="direction", value="both", inline=True, options=[
            {"label": " Both ", "value": "both"}, {"label": " In ", "value": "in"}, {"label": " Out", "value": "out"}])]),
        html.Div([html.Label("Max 2nd-level entities"), dcc.Slider(id="max_l2", min=10, max=120, step=10, value=50,
                                                                   marks={10: "10", 50: "50", 120: "120"})], style={"minWidth": "200px", "flex": "1"}),
        html.Div([html.Label("Layout"), dcc.RadioItems(id="layout", value="rings", inline=True, options=[
            {"label": " Rings ", "value": "rings"}, {"label": " Force", "value": "cose"}])]),
    ]),
    html.Div(className="kpis", children=[
        card("Money in", "k-in"), card("Money out", "k-out"), card("Net", "k-net"), card("1st-level counterparties", "k-l1"),
        card("2nd-level entities", "k-l2"), card("Stays inside QIB", "k-onus"), card("Self transfers", "k-self")]),
    html.Div(className="legend", children=[
        *[html.Span([html.I(style={"background": c}), t]) for t, c in TYPE_COLOR.items()],
        html.Span([html.I(style={"background": "#fff", "border": "3px solid #1d1d24"}), "QIB customer"]),
        *[html.Span([html.B(style={"background": c}), ROUTE_LABEL[r]]) for r, c in ROUTE_COLOR.items()],
    ]),
    cyto.Cytoscape(id="graph", elements=[], stylesheet=STYLE, layout={"name": "preset"},
                   style={"width": "100%", "height": "640px"}, minZoom=0.15, maxZoom=4),
    html.Div(id="node-info", className="info"),
    html.Div(className="row2", children=[graph("monthly"), graph("purpose")]),
    html.H3("Counterparties of the centre company"),
    dash_table.DataTable(id="table", filter_action="native", **TABLE_KW),
])

self_tab = html.Div(className="main", children=[
    html.Div(id="self-callout", className="callout"),
    html.Div(className="kpis", children=[card("Self-transfer value", "s-val"), card("Transfers", "s-n"), card("Companies", "s-co"),
                                         card("Moved out of QIB", "s-out"), card("Moved into QIB", "s-in"), card("Net leaving QIB", "s-net")]),
    panel("Where companies keep their other accounts",
          "Each line links a QIB customer to a bank where it holds another account of its own. Thicker lines carry more money. "
          "Orange: money mostly left QIB. Blue: money mostly came in. Green: between two QIB accounts. Click a company to open its network.",
          cyto.Cytoscape(id="self-graph", elements=[], stylesheet=STYLE,
                         layout={"name": "cose", "animate": False, "idealEdgeLength": 110, "nodeRepulsion": 30000, "gravity": 0.7},
                         style={"width": "100%", "height": "520px"}, minZoom=0.2, maxZoom=4)),
    html.Div(className="row2", children=[graph("self-co"), graph("self-bank")]),
    graph("self-month"),
    html.H3("Self-transfer detail (company and bank)"),
    dash_table.DataTable(id="self-table", **TABLE_KW),
])

bank_tab = html.Div(className="main", children=[
    panel("QIB and the other Qatar banks", "QIB in the centre. Line width shows the money exchanged with QIB customers "
          "(orange = QIB pays the bank, blue = QIB receives). Click a bank to analyse it below.",
          cyto.Cytoscape(id="bank-graph", elements=[], stylesheet=STYLE, layout={"name": "concentric", "animate": False, "minNodeSpacing": 60},
                         style={"width": "100%", "height": "460px"}, minZoom=0.3, maxZoom=3)),
    html.H3("All banks"),
    dash_table.DataTable(id="bank-table", **TABLE_KW),
    html.Div(className="egoctl", children=[html.Div([html.Label("Analyse bank"), dcc.Dropdown(
        id="bank-pick", options=[{"label": bank_lbl(b), "value": b} for b in BANKS], value=BANKS[1] if len(BANKS) > 1 else BANKS[0],
        clearable=False)], style={"minWidth": "320px"})]),
    html.Div(className="kpis", children=[card("QIB pays this bank", "b-pay"), card("QIB receives from it", "b-rec"), card("Net to QIB", "b-net"),
                                         card("QIB customers involved", "b-cust"), card("Counterparties", "b-cp"), card("Self-transfer share", "b-self")]),
    html.Div(className="row2", children=[graph("bank-month"), graph("bank-purpose")]),
    html.Div(className="row2", children=[
        html.Div([html.H3("QIB customers using this bank"), dash_table.DataTable(id="bank-cust", **TABLE_KW)]),
        html.Div([html.H3("Counterparties banking there"), dash_table.DataTable(id="bank-cps", **TABLE_KW)])]),
])

ind_tab = html.Div(className="main", children=[
    html.Div(className="egoctl", children=[
        dcc.Checklist(id="ind-opts", value=["gre"], inline=True, options=[
            {"label": " Group government-related companies (GREs) as one industry   ", "value": "gre"},
            {"label": " Include individuals", "value": "ind"}]),
        html.Div([html.Label("Links shown"), dcc.Slider(id="ind-top", min=10, max=60, step=5, value=25,
                                                        marks={10: "10", 25: "25", 60: "60"})], style={"minWidth": "220px"}),
    ]),
    panel("How money moves between industries", "Left: the payer's industry. Right: the payee's industry. "
          "Government bodies are an industry of their own. Self transfers are excluded.", graph("ind-sankey")),
    html.Div(className="row2", children=[graph("ind-matrix"), graph("ind-net")]),
    html.H3("Largest industry flows"),
    dash_table.DataTable(id="ind-table", **TABLE_KW),
])

over_tab = html.Div(className="main", children=[
    html.P("The largest payer-to-payee relationships across all QIB customers (self transfers excluded). Click a dot to open it in Company network."),
    dcc.Slider(id="topn", min=50, max=600, step=50, value=200, marks={50: "50", 200: "200", 400: "400", 600: "600 links"}),
    cyto.Cytoscape(id="overview-graph", elements=[], stylesheet=STYLE,
                   layout={"name": "cose", "idealEdgeLength": 150, "nodeRepulsion": 60000, "nodeOverlap": 40, "gravity": 0.6, "animate": False},
                   style={"width": "100%", "height": "680px"}, minZoom=0.1, maxZoom=4),
    html.Div(className="row2", children=[graph("corridors"), graph("hubs")]),
])

app.layout = html.Div(className="page", children=[
    html.Header(className="brandbar", children=[
        # put your own logo in assets/logo.png to show it here
        *([html.Img(src=app.get_asset_url("logo.png"), alt="")] if (Path(__file__).parent / "assets" / "logo.png").exists() else []),
        html.Div([html.Strong("Corporate Network Intelligence"),
                  html.Span(f"Relationship manager view of company payment networks · synthetic data · source: {SRC.label}")]),
    ]),
    topbar,
    html.Div(className="layout", children=[
        filters,
        dcc.Tabs(id="tabs", value="brief", children=[
            dcc.Tab(label="RM brief", value="brief", children=brief_tab),
            dcc.Tab(label="Company network", value="ego", children=ego_tab),
            dcc.Tab(label="Self transfers", value="self", children=self_tab),
            dcc.Tab(label="Banks", value="banks", children=bank_tab),
            dcc.Tab(label="Industry flows", value="ind", children=ind_tab),
            dcc.Tab(label="QIB portfolio", value="overview", children=over_tab),
        ]),
    ]),
])


def node_size(v, vmax):
    return 18 + 52 * (v / vmax) ** 0.5 if vmax else 24


def fig_layout(fig, title, height=340, l=60, **kw):
    fig.update_layout(title=title, height=height, margin=dict(l=l, r=10, t=50, b=110),
                      legend=dict(orientation="h", yanchor="top", y=-0.2, x=0),
                      plot_bgcolor="white", font=FONT, **kw)
    return fig


def scoped(df, sc, center):
    """'This company' keeps only the flows touching the company picked at the top."""
    return df[(df.s == center) | (df.t == center)] if sc == "co" else df


def scope(months, routes, banks, types, purposes):
    m_from, m_to = MONTHS[months[0]], MONTHS[months[1]]
    return m_from, m_to, filter_flows(ALL_FLOWS, m_from, m_to, routes, banks, purposes, types, ENTS)


@app.callback(Output("banks", "value"), Input("banks-all", "n_clicks"), Input("banks-none", "n_clicks"), prevent_initial_call=True)
def bank_buttons(_a, _n):
    return BANKS if ctx.triggered_id == "banks-all" else []


# ---------- company network ----------

@app.callback(
    Output("graph", "elements"), Output("graph", "layout"), Output("table", "data"), Output("table", "columns"),
    Output("monthly", "figure"), Output("purpose", "figure"),
    Output("k-in", "children"), Output("k-out", "children"), Output("k-net", "children"),
    Output("k-l1", "children"), Output("k-l2", "children"), Output("k-onus", "children"), Output("k-self", "children"),
    Input("center", "value"), Input("depth", "value"), Input("direction", "value"), Input("months", "value"),
    Input("routes", "value"), Input("banks", "value"), Input("types", "value"), Input("purposes", "value"),
    Input("max_l2", "value"), Input("layout", "value"))
def update_ego(center, depth, direction, months, routes, banks, types, purposes, max_l2, layout):
    m_from, m_to = MONTHS[months[0]], MONTHS[months[1]]
    bank_arg = None if set(banks or []) == set(BANKS) else (banks or ["none"])
    f1, nodes, pairs, table = ego_network(SRC, ENTS, center, depth, m_from, m_to, routes or ["none"], purposes,
                                          direction, types or ["none"], max_l2, bank_arg)
    pos = ring_positions(nodes, pairs, center) if layout == "rings" else {}
    vmax = (nodes.inflow + nodes.outflow).max() if len(nodes) else 0
    emax = pairs.v.max() if len(pairs) else 1
    lv = dict(zip(nodes.id, nodes.level)) if len(nodes) else {center: 0}
    els = []
    for n in nodes.itertuples():
        el = {"data": {"id": n.id, "label": short(n.name) if n.level < 2 or (n.inflow + n.outflow) > vmax * 0.02 else "",
                       "name": n.name, "type": n.type, "bank": n.bank, "qib": n.qib, "level": int(n.level),
                       "color": TYPE_COLOR.get(n.type, "#888"), "size": node_size(n.inflow + n.outflow, vmax) * (1.4 if n.level == 0 else 1),
                       "inflow": n.inflow, "outflow": n.outflow}}
        if n.id in pos:
            el["position"] = {"x": pos[n.id][0], "y": pos[n.id][1]}
        els.append(el)
    for p in pairs.itertuples():
        if p.s in lv and p.t in lv:
            tier = 1 if center in (p.s, p.t) else 2
            els.append({"data": {"id": f"{p.s}>{p.t}", "source": p.s, "target": p.t, "color": ROUTE_COLOR[p.route],
                                 "w": 1 + 9 * (p.v / emax) ** 0.5, "tier": tier, "v": p.v, "n": int(p.n)}})
    lay = {"name": "preset", "fit": True, "padding": 30} if layout == "rings" else \
          {"name": "cose", "animate": False, "idealEdgeLength": 110, "nodeRepulsion": 12000, "fit": True}

    vin = f1[f1.t == center].v.sum()
    vout = f1[f1.s == center].v.sum()
    onus = f1[f1.r == "ON_US"].v.sum() / f1.v.sum() if f1.v.sum() else 0
    l1n, l2n = int((nodes.level == 1).sum()) if len(nodes) else 0, int((nodes.level == 2).sum()) if len(nodes) else 0
    own = filter_flows(ALL_FLOWS, m_from, m_to, routes, banks, purposes)
    own = own[(own.x == 1) & (own.s == center)]
    self_txt = f"{QAR(own.v.sum())} ({int(own.n.sum())})" if len(own) else "None"

    mm = [m for m in MONTHS if m_from <= m <= m_to]
    s_in = f1[f1.t == center].groupby("m").v.sum().reindex(mm, fill_value=0)
    s_out = f1[f1.s == center].groupby("m").v.sum().reindex(mm, fill_value=0)
    x = [MONTH_LABEL[MONTHS.index(m)] for m in mm]
    monthly = go.Figure([go.Bar(x=x, y=s_in.values, name="Money in", marker_color=IN_C),
                         go.Bar(x=x, y=-s_out.values, name="Money out", marker_color=OUT_C)])
    fig_layout(monthly, f"Monthly flows: {short(name(center))} (self transfers excluded)", barmode="relative", yaxis_title="QAR")
    pp = f1.groupby(["c", "r"]).v.sum().reset_index()
    purpose = go.Figure([go.Bar(y=pp[pp.r == r].c, x=pp[pp.r == r].v, orientation="h", name=ROUTE_LABEL[r],
                                marker_color=ROUTE_COLOR[r]) for r in ROUTE_LABEL if (pp.r == r).any()])
    fig_layout(purpose, "Purpose by bank route (centre's own payments)", l=180, barmode="stack")
    cols = [{"name": c, "id": c, "type": "numeric", "format": {"specifier": ",.0f"}} if "QAR" in c or c == "Payments"
            else {"name": c, "id": c} for c in table.columns if c != "id"]
    data = table.sort_values(["Level", "Paid to centre (QAR)"], ascending=[True, False]).to_dict("records") if len(table) else []
    return (els, lay, data, cols, monthly, purpose, QAR(vin), QAR(vout), ("+" if vin >= vout else "") + QAR(vin - vout),
            f"{l1n:,}", f"{l2n:,}", f"{onus:.0%}", self_txt)


@app.callback(Output("node-info", "children"), Input("graph", "mouseoverNodeData"), Input("graph", "tapNodeData"))
def node_info(hover, tap):
    d = tap if ctx.triggered_id == "graph" and ctx.triggered[0]["prop_id"].endswith("tapNodeData") else hover
    if not d:
        return "Hover over a dot for details. Click a dot to re-centre the network on it."
    where = "QIB customer" if d["qib"] else f"banks with {d['bank']}"
    lvl = ["Centre", "1st level", "2nd level"][d["level"]]
    return [html.B(d["name"]), f"  ·  {d['type']}  ·  {where}  ·  {lvl}  ·  in view: in {QAR(d['inflow'])}, out {QAR(d['outflow'])}"]


@app.callback(Output("center", "value"), Output("tabs", "value"),
              Input("graph", "tapNodeData"), Input("overview-graph", "tapNodeData"), Input("self-graph", "tapNodeData"),
              Input("self-table", "active_cell"), State("self-table", "derived_viewport_data"), prevent_initial_call=True)
def recenter(tap, tap_over, tap_self, cell, rows):
    if ctx.triggered_id == "self-table":
        return (rows[cell["row"]]["id"], "ego") if cell and rows else (no_update, no_update)
    d = {"overview-graph": tap_over, "self-graph": tap_self}.get(ctx.triggered_id, tap)
    if not d or d.get("bank_node"):
        return no_update, no_update
    return d["id"], "ego"


@app.callback(Output("center", "value", allow_duplicate=True), Input("br-cust", "active_cell"), Input("br-supp", "active_cell"), Input("br-change", "active_cell"),
              State("br-cust", "derived_viewport_data"), State("br-supp", "derived_viewport_data"), State("br-change", "derived_viewport_data"),
              prevent_initial_call=True)
def brief_click(c1, c2, c3, r1, r2, r3):
    cell, rows = {"br-cust": (c1, r1), "br-supp": (c2, r2), "br-change": (c3, r3)}[ctx.triggered_id]
    return rows[cell["row"]]["id"] if cell and rows else no_update


# ---------- RM brief ----------

@app.callback(
    Output("br-title", "children"), Output("br-chips", "children"), Output("br-head", "children"),
    Output("br-in", "children"), Output("br-out", "children"), Output("br-net", "children"), Output("br-nc", "children"),
    Output("br-ns", "children"), Output("br-leak", "children"), Output("br-self", "children"),
    Output("br-ins", "children"), Output("br-recs", "children"),
    Output("br-cust", "data"), Output("br-cust", "columns"), Output("br-supp", "data"), Output("br-supp", "columns"),
    Output("br-change", "data"), Output("br-change", "columns"),
    Output("br-month", "figure"), Output("br-bank", "figure"), Output("br-ind", "figure"),
    Input("center", "value"), Input("months", "value"), Input("routes", "value"), Input("banks", "value"),
    Input("types", "value"), Input("purposes", "value"))
def update_brief(c, months, routes, banks, types, purposes):
    m_from, m_to = MONTHS[months[0]], MONTHS[months[1]]
    mm = [m for m in MONTHS if m_from <= m <= m_to]
    df = filter_flows(ALL_FLOWS, m_from, m_to, routes, banks, purposes)
    B = rm_brief.compute(df, ENTS, c, mm, types or [])
    head, ins, recs = rm_brief.write(B, ENTS)
    e = B["e"]
    chips = [e["type"], e["industry"], "QIB customer" if e["qib"] else "Banks with " + rm_brief.bank_short(e["bank"]),
             f"Influence rank #{B['rank']} of {B['n_ents']}"]
    leak = f"{rm_brief.pct(B['outOther'].v.sum(), B['vout'])}%" if e["qib"] and B["vout"] else "–"
    so = B["selfF"][B["selfF"].r == "QIB_TO_OTHER"].v.sum()
    rec_divs = [html.Div(className="rec", children=[html.Span(f"{i + 1} · {r['tag']}", className="tag"), html.H4(r["title"]), html.P(r["body"])])
                for i, r in enumerate(recs)] or [html.P("No recommendation passes its threshold for this company and these filters.")]
    cols = money_cols([("name", "Name"), ("bank_l", "Bank"), ("v", "Value (QAR)"), ("share_p", "Share %"), ("n", "Payments"), ("last_l", "Last active")],
                      money=("v",), ints=("n",))
    prep = lambda d: d.assign(share_p=(d.share * 100).round(0), last_l=d["last"].map(rm_brief.mlabel), v=d.v.round(0)).head(25).to_dict("records") if len(d) else []
    ch = B["changes"]
    ch_rows = ch.assign(first_l=ch["first"].map(rm_brief.mlabel), last_l=ch["last"].map(rm_brief.mlabel), v=ch.v.round(0)).head(25).to_dict("records") if len(ch) else []
    ch_cols = money_cols([("name", "Counterparty"), ("status", "Status"), ("v", "Value (QAR)"), ("first_l", "First"), ("last_l", "Last")], money=("v",))

    x = [rm_brief.mlabel(m) for m in mm]
    fm = go.Figure([go.Bar(x=x, y=B["mIn"].values, name="Money in", marker_color=IN_C),
                    go.Bar(x=x, y=-B["mOut"].values, name="Money out", marker_color=OUT_C),
                    go.Scatter(x=x, y=(B["mIn"] - B["mOut"]).values, name="Net", mode="lines+markers", line=dict(color="#00111A", width=2))])
    fig_layout(fm, "Receipts and payments by month", barmode="relative", yaxis_title="QAR")
    ob = (lambda rows: rows.b) if e["qib"] else (lambda rows: pd.Series(QIB, index=rows.index))
    bi, bo = B["inF"].groupby(ob(B["inF"])).v.sum(), B["outF"].groupby(ob(B["outF"])).v.sum()
    bks = sorted(set(bi.index) | set(bo.index), key=lambda k: bi.get(k, 0) + bo.get(k, 0))
    fb = go.Figure([go.Bar(y=[rm_brief.bank_short(k) for k in bks], x=[-bo.get(k, 0) for k in bks], orientation="h", name="Paid to accounts at", marker_color=OUT_C),
                    go.Bar(y=[rm_brief.bank_short(k) for k in bks], x=[bi.get(k, 0) for k in bks], orientation="h", name="Received from accounts at", marker_color=IN_C)])
    fig_layout(fb, "Which banks the money moves through", l=140, barmode="relative", height=max(340, 30 * len(bks) + 150))
    ind = industry_of(ENTS)
    ii, io = B["inF"].groupby(B["inF"].s.map(ind)).v.sum(), B["outF"].groupby(B["outF"].t.map(ind)).v.sum()
    inds = sorted(set(ii.index) | set(io.index), key=lambda k: ii.get(k, 0) + io.get(k, 0))
    fi = go.Figure([go.Bar(y=inds, x=[-io.get(k, 0) for k in inds], orientation="h", name="Paid to", marker_color=OUT_C),
                    go.Bar(y=inds, x=[ii.get(k, 0) for k in inds], orientation="h", name="Received from", marker_color=IN_C)])
    fig_layout(fi, "Counterparties by industry", l=200, barmode="relative", height=max(340, 28 * len(inds) + 150))
    return (e["name"], [html.Span(t, className="chip") for t in chips if t], head,
            rm_brief.qar(B["vin"]), rm_brief.qar(B["vout"]), ("+" if B["vin"] >= B["vout"] else "") + rm_brief.qar(B["vin"] - B["vout"]),
            f"{len(B['cust'])}", f"{len(B['supp'])}", leak, rm_brief.qar(so) if so else "None",
            [html.Li(t) for t in ins], rec_divs, prep(B["cust"]), cols, prep(B["supp"]), cols, ch_rows, ch_cols, fm, fb, fi)


# ---------- self transfers ----------

@app.callback(
    Output("self-callout", "children"), Output("s-val", "children"), Output("s-n", "children"), Output("s-co", "children"),
    Output("s-out", "children"), Output("s-in", "children"), Output("s-net", "children"),
    Output("self-graph", "elements"), Output("self-co", "figure"), Output("self-bank", "figure"), Output("self-month", "figure"),
    Output("self-table", "data"), Output("self-table", "columns"),
    Input("months", "value"), Input("routes", "value"), Input("banks", "value"), Input("purposes", "value"),
    Input("scope", "value"), Input("center", "value"))
def update_self(months, routes, banks, purposes, scope, center):
    m_from, m_to = MONTHS[months[0]], MONTHS[months[1]]
    df = scoped(filter_flows(ALL_FLOWS, m_from, m_to, routes, banks, purposes), scope, center)
    s = df[df.x == 1]
    pr = self_by_company_bank(df)
    out, inn = pr.out.sum(), pr.inn.sum()
    co_net = pr.groupby("id").net.sum().sort_values(ascending=False)
    bank_out = pr[pr.bank != QIB].groupby("bank").out.sum().sort_values(ascending=False)
    callout = [html.B(f"{s.s.nunique()} QIB customers moved {QAR(s.v.sum())} between their own accounts. ")] + (
        [f"Net {QAR(abs(out - inn))} of their own money {'left' if out >= inn else 'came into'} QIB"
         + (f", most of it to {bank_out.index[0]}" if len(bank_out) and out >= inn else "") + ". "
         + (f"The largest net outflow is {name(co_net.index[0])} ({QAR(co_net.iloc[0])}), a candidate for a liquidity or deposit conversation."
            if len(co_net) and co_net.iloc[0] > 0 else "")] if len(pr) else ["No self transfers in the current filters."])

    tot = lambda r: r.out + r.inn + r.on
    co_tot = pr.assign(t=tot(pr)).groupby("id").t.sum()
    b_tot = pr.assign(t=tot(pr)).groupby("bank").t.sum()
    emax = max(1, tot(pr).max() if len(pr) else 1)
    cmax, bmax = max(1, co_tot.max() if len(co_tot) else 1), max(1, b_tot.max() if len(b_tot) else 1)
    els = [{"data": {"id": c, "label": short(name(c)), "name": name(c), "color": TYPE_COLOR.get(ENTS.at[c, "type"], "#888"),
                     "size": node_size(v, cmax), "qib": True}} for c, v in co_tot.items()]
    els += [{"data": {"id": "bank:" + b, "label": "QIB 2nd account" if b == QIB else b, "bank_node": True,
                      "color": ON_C if b == QIB else "#5d5d68", "size": 26 + 40 * (v / bmax) ** 0.5}} for b, v in b_tot.items()]
    els += [{"data": {"id": f"{r.id}>{r.bank}", "source": r.id, "target": "bank:" + r.bank, "plain": True,
                      "w": 1 + 9 * (tot(r) / emax) ** 0.5, "color": ON_C if r.on else OUT_C if r.out >= r.inn else IN_C}}
            for r in pr.itertuples()]

    top = co_tot.sort_values(ascending=False).head(20).index[::-1]
    per = lambda col: pr.groupby("id")[col].sum().reindex(top, fill_value=0)
    ylab = [short(name(c)) for c in top]
    fco = go.Figure([go.Bar(y=ylab, x=-per("out"), customdata=per("out"), orientation="h", name="Out of QIB", marker_color=OUT_C,
                            hovertemplate="%{y}: QAR %{customdata:,.0f}<extra>Out of QIB</extra>"),
                     go.Bar(y=ylab, x=per("inn"), orientation="h", name="Into QIB", marker_color=IN_C),
                     go.Bar(y=ylab, x=per("on"), orientation="h", name="Between own QIB accounts", marker_color=ON_C)])
    fig_layout(fco, "By company: out of QIB (left), back in or within QIB (right)", height=max(340, 24 * len(top) + 110), l=200, barmode="relative")
    banks_o = b_tot.sort_values().index
    perb = lambda col: pr.groupby("bank")[col].sum().reindex(banks_o, fill_value=0)
    blab = ["QIB 2nd account" if b == QIB else b for b in banks_o]
    fb = go.Figure([go.Bar(y=blab, x=-perb("out"), customdata=perb("out"), orientation="h", name="Out of QIB", marker_color=OUT_C,
                           hovertemplate="%{y}: QAR %{customdata:,.0f}<extra>Out of QIB</extra>"),
                    go.Bar(y=blab, x=perb("inn"), orientation="h", name="Into QIB", marker_color=IN_C),
                    go.Bar(y=blab, x=perb("on"), orientation="h", name="Between own QIB accounts", marker_color=ON_C)])
    fig_layout(fb, "By bank holding the other account", height=max(340, 30 * len(banks_o) + 110), l=200, barmode="relative")
    mm = [m for m in MONTHS if m_from <= m <= m_to]
    net = (s[s.r == "QIB_TO_OTHER"].groupby("m").v.sum().reindex(mm, fill_value=0)
           - s[s.r == "OTHER_TO_QIB"].groupby("m").v.sum().reindex(mm, fill_value=0))
    fm = go.Figure(go.Bar(x=[MONTH_LABEL[MONTHS.index(m)] for m in mm], y=net.values, marker_color=[OUT_C if v >= 0 else IN_C for v in net.values]))
    fig_layout(fm, "Net own-account money leaving QIB, by month (above zero = more left than came back)", height=300, yaxis_title="QAR")

    rows = pr.assign(name=pr.id.map(name), bank=pr.bank.map(lambda b: "QIB (own accounts)" if b == QIB else b))
    cols = money_cols([("name", "Company"), ("bank", "Other account at"), ("n", "Transfers"), ("out", "Out of QIB (QAR)"),
                       ("inn", "Into QIB (QAR)"), ("on", "Between QIB accounts (QAR)"), ("net", "Net leaving QIB (QAR)")],
                      money=("out", "inn", "on", "net"), ints=("n",))
    return (callout, QAR(s.v.sum()), f"{int(s.n.sum()):,}", f"{s.s.nunique()}", QAR(out), QAR(inn), QAR(out - inn),
            els, fco, fb, fm, rows.round(0).to_dict("records"), cols)


# ---------- banks ----------

@app.callback(Output("bank-graph", "elements"), Output("bank-table", "data"), Output("bank-table", "columns"),
              Input("months", "value"), Input("routes", "value"), Input("banks", "value"), Input("types", "value"),
              Input("purposes", "value"), Input("bank-pick", "value"), Input("scope", "value"), Input("center", "value"))
def update_banks(months, routes, banks, types, purposes, pick, sc, center):
    _, _, df = scope(months, routes, banks, types, purposes)
    df = scoped(df, sc, center)
    bt = bank_table(df)
    vmax = max(1, bt.total.max() if len(bt) else 1)
    els = [{"data": {"id": "QIB", "label": "QIB", "bank_node": True, "color": ACCENT, "size": 80, "level": 0 if pick == QIB else 1}}]
    for r in bt.itertuples():
        if r.bank == QIB:
            continue
        els.append({"data": {"id": r.bank, "label": r.bank, "bank_node": True, "size": 30 + 50 * (r.total / vmax) ** 0.5,
                             "color": "#c9a227" if r.bank == pick else "#5d5d68", "level": 1}})
        for src, dst, v, c in (("QIB", r.bank, r.pays, OUT_C), (r.bank, "QIB", r.receives, IN_C)):
            if v:
                els.append({"data": {"id": f"{src}>{dst}", "source": src, "target": dst, "color": c, "w": 1 + 14 * (v / vmax) ** 0.5}})
    rows = bt.assign(bank=bt.bank.map(bank_lbl), share=(bt.share * 100).round(1))
    cols = money_cols([("bank", "Bank"), ("total", "Total (QAR)"), ("share", "Share %"), ("pays", "QIB pays (QAR)"),
                       ("receives", "QIB receives (QAR)"), ("within", "Within QIB (QAR)"), ("n", "Payments"),
                       ("customers", "QIB customers"), ("selfv", "Self transfers (QAR)")],
                      money=("total", "pays", "receives", "within", "selfv"), ints=("n", "customers"))
    return els, rows.round({"total": 0, "pays": 0, "receives": 0, "within": 0, "selfv": 0}).to_dict("records"), cols


@app.callback(Output("bank-pick", "value"), Input("bank-graph", "tapNodeData"), Input("bank-table", "active_cell"),
              State("bank-table", "derived_viewport_data"), prevent_initial_call=True)
def pick_bank(tap, cell, rows):
    if ctx.triggered_id == "bank-table":
        if not cell or not rows:
            return no_update
        lbl = rows[cell["row"]]["bank"]
        return QIB if lbl == bank_lbl(QIB) else lbl
    return QIB if tap and tap["id"] == "QIB" else (tap["id"] if tap else no_update)


@app.callback(
    Output("b-pay", "children"), Output("b-rec", "children"), Output("b-net", "children"), Output("b-cust", "children"),
    Output("b-cp", "children"), Output("b-self", "children"), Output("bank-month", "figure"), Output("bank-purpose", "figure"),
    Output("bank-cust", "data"), Output("bank-cust", "columns"), Output("bank-cps", "data"), Output("bank-cps", "columns"),
    Input("months", "value"), Input("routes", "value"), Input("types", "value"), Input("purposes", "value"), Input("bank-pick", "value"),
    Input("scope", "value"), Input("center", "value"))
def update_bank_detail(months, routes, types, purposes, pick, sc, center):
    m_from, m_to, df = scope(months, routes, [pick], types, purposes)
    df = scoped(df, sc, center)
    pay = df[df.r == "QIB_TO_OTHER"].v.sum()
    rec = df[df.r == "OTHER_TO_QIB"].v.sum()
    within = df[df.r == "ON_US"].v.sum()
    q, c = qib_side(df), cp_side(df)
    mm = [m for m in MONTHS if m_from <= m <= m_to]
    x = [MONTH_LABEL[MONTHS.index(m)] for m in mm]
    by = lambda r: df[df.r == r].groupby("m").v.sum().reindex(mm, fill_value=0)
    fm = go.Figure([go.Bar(x=x, y=by("OTHER_TO_QIB"), name="Into QIB", marker_color=IN_C),
                    go.Bar(x=x, y=-by("QIB_TO_OTHER"), name="Out of QIB", marker_color=OUT_C),
                    go.Bar(x=x, y=by("ON_US"), name="Within QIB", marker_color=ON_C)])
    fig_layout(fm, f"Monthly flows with {bank_lbl(pick)}", barmode="relative", yaxis_title="QAR")
    pp = df.groupby("c").v.sum().sort_values()
    fp = go.Figure(go.Bar(y=pp.index, x=pp.values, orientation="h", marker_color=ACCENT))
    fig_layout(fp, "Purpose of the flows", height=max(340, 26 * len(pp) + 90), l=210)
    d = df.assign(q=q, cp=c, selfv=df.v.where(df.x == 1, 0))
    cu = d.groupby("q").agg(v=("v", "sum"), n=("n", "sum"), selfv=("selfv", "sum")).reset_index().sort_values("v", ascending=False)
    cu = cu.assign(name=cu.q.map(name), type=cu.q.map(ENTS.type)).round(0)
    cp = d[d.x == 0].groupby("cp").agg(v=("v", "sum"), n=("n", "sum")).reset_index().sort_values("v", ascending=False)
    cp = cp.assign(name=cp.cp.map(name), type=cp.cp.map(ENTS.type)).round(0)
    ccols = money_cols([("name", "QIB customer"), ("type", "Type"), ("v", "Value (QAR)"), ("n", "Payments"), ("selfv", "Of which self (QAR)")],
                       money=("v", "selfv"), ints=("n",))
    pcols = money_cols([("name", "Counterparty"), ("type", "Type"), ("v", "Value (QAR)"), ("n", "Payments")], money=("v",), ints=("n",))
    net = rec - pay
    return (QAR(pay) if pick != QIB else f"Within QIB: {QAR(within)}", QAR(rec), ("+" if net >= 0 else "") + QAR(net),
            f"{q.nunique():,}", f"{c.nunique():,}", f"{df[df.x == 1].v.sum() / df.v.sum():.0%}" if df.v.sum() else "–",
            fm, fp, cu.to_dict("records"), ccols, cp.to_dict("records"), pcols)


# ---------- industries ----------

@app.callback(Output("ind-sankey", "figure"), Output("ind-matrix", "figure"), Output("ind-net", "figure"),
              Output("ind-table", "data"), Output("ind-table", "columns"),
              Input("months", "value"), Input("routes", "value"), Input("banks", "value"), Input("types", "value"),
              Input("purposes", "value"), Input("ind-opts", "value"), Input("ind-top", "value"), Input("scope", "value"), Input("center", "value"))
def update_industry(months, routes, banks, types, purposes, opts, top, sc, center):
    _, _, df = scope(months, routes, banks, types, purposes)
    if sc == "co":
        return company_industry(df, center, opts)
    pairs = industry_pairs(df, ENTS, "gre" in (opts or []), "ind" in (opts or []))
    total = pairs.v.sum() or 1
    shown = pairs.head(top)
    left = sorted(set(shown.fi), key=lambda k: -shown[shown.fi == k].v.sum())
    right = sorted(set(shown.ti), key=lambda k: -shown[shown.ti == k].v.sum())
    labels = [f"{k} (pays)" for k in left] + [f"{k} (receives)" for k in right]
    palette = ["#7a1e3a", "#2f6f4f", "#c2577a", "#3b6fd4", "#e8743b", "#1f9e89", "#c9a227", "#8a5cc2", "#5d5d68", "#a05a2c"]
    col = {k: palette[i % len(palette)] for i, k in enumerate(dict.fromkeys(left + right))}
    rgba = lambda h: f"rgba({int(h[1:3], 16)},{int(h[3:5], 16)},{int(h[5:7], 16)},0.35)"
    sk = go.Figure(go.Sankey(arrangement="snap",
                             node=dict(label=labels, pad=12, thickness=16, color=[col[k] for k in left] + [col[k] for k in right]),
                             link=dict(source=[left.index(r.fi) for r in shown.itertuples()],
                                       target=[len(left) + right.index(r.ti) for r in shown.itertuples()],
                                       value=shown.v.tolist(), color=[rgba(col[r.fi]) for r in shown.itertuples()],
                                       hovertemplate="%{source.label} → %{target.label}: QAR %{value:,.0f}<extra></extra>")))
    fig_layout(sk, f"Top {len(shown)} industry-to-industry flows ({shown.v.sum() / total:.0%} of value)", height=620, l=10)

    inds = pd.concat([pairs.groupby("fi").v.sum(), pairs.groupby("ti").v.sum()], axis=1).fillna(0).sum(axis=1).sort_values(ascending=False).index.tolist()
    mat = pairs.pivot_table(index="fi", columns="ti", values="v", aggfunc="sum").reindex(index=inds, columns=inds)
    hm = go.Figure(go.Heatmap(z=np.log10(mat.where(mat > 0)).values, x=inds, y=inds, customdata=mat.fillna(0).values,
                              colorscale=[[0, "#f4eef0"], [1, ACCENT]], showscale=False,
                              hovertemplate="%{y} → %{x}: QAR %{customdata:,.0f}<extra></extra>"))
    fig_layout(hm, "Industry to industry matrix (rows pay columns, log colour scale)", height=560, l=190)
    hm.update_yaxes(autorange="reversed")
    netpos = (pairs.groupby("ti").v.sum().reindex(inds, fill_value=0) - pairs.groupby("fi").v.sum().reindex(inds, fill_value=0)).sort_values()
    fn = go.Figure(go.Bar(y=netpos.index, x=netpos.values, orientation="h", marker_color=[IN_C if v >= 0 else OUT_C for v in netpos.values]))
    fig_layout(fn, "Net position by industry (received minus paid)", height=560, l=190)
    rows = pairs.assign(share=(pairs.v / total * 100).round(1)).round({"v": 0}).head(60)
    cols = money_cols([("fi", "From industry"), ("ti", "To industry"), ("v", "Value (QAR)"), ("share", "Share %"), ("n", "Payments")],
                      money=("v",), ints=("n",))
    return sk, hm, fn, rows.to_dict("records"), cols


def company_industry(df, c, opts):
    """Payer industries -> the company -> payee industries."""
    ind = industry_of(ENTS, "gre" in (opts or []))
    d = df[(df.x == 0) & ((df.s == c) | (df.t == c))]
    if "ind" not in (opts or []):
        d = d[(d.s.map(ENTS.type) != "Individual") & (d.t.map(ENTS.type) != "Individual")]
    gin = d[d.t == c].groupby(d[d.t == c].s.map(ind)).agg(v=("v", "sum"), n=("n", "sum")).sort_values("v", ascending=False)
    gout = d[d.s == c].groupby(d[d.s == c].t.map(ind)).agg(v=("v", "sum"), n=("n", "sum")).sort_values("v", ascending=False)
    L, R, mid, nm = list(gin.index), list(gout.index), len(gin), ENTS.at[c, "name"]
    palette = ["#2f6f4f", "#00476b", "#5fa8d3", "#c9a227", "#8a5cc2", "#1a9e7a", "#a05a2c", "#5d5d68"]
    col = {k: palette[i % len(palette)] for i, k in enumerate(dict.fromkeys(L + R))}
    rgba = lambda h: f"rgba({int(h[1:3], 16)},{int(h[3:5], 16)},{int(h[5:7], 16)},0.4)"
    sk = go.Figure(go.Sankey(arrangement="snap", node=dict(label=[f"{k} (pays)" for k in L] + [short(nm)] + [f"{k} (is paid)" for k in R], pad=14, thickness=18,
                                                           color=[col[k] for k in L] + [ACCENT] + [col[k] for k in R]),
                             link=dict(source=list(range(mid)) + [mid] * len(R), target=[mid] * mid + [mid + 1 + i for i in range(len(R))],
                                       value=list(gin.v) + list(gout.v), color=[rgba(col[k]) for k in L] + [rgba(col[k]) for k in R],
                                       hovertemplate="%{source.label} → %{target.label}: QAR %{value:,.0f}<extra></extra>")))
    fig_layout(sk, f"{nm}: where its money comes from and goes to (self transfers excluded)", height=560, l=10)
    inds = sorted(set(L) | set(R), key=lambda k: gin.v.get(k, 0) + gout.v.get(k, 0))
    bars = go.Figure([go.Bar(y=inds, x=[-gout.v.get(k, 0) for k in inds], orientation="h", name="Paid to", marker_color=OUT_C),
                      go.Bar(y=inds, x=[gin.v.get(k, 0) for k in inds], orientation="h", name="Received from", marker_color=IN_C)])
    fig_layout(bars, "Receipts and payments by counterparty industry", height=max(360, 30 * len(inds) + 150), l=200, barmode="relative")
    tot = gin.v.sum() + gout.v.sum() or 1
    rows = [dict(fi=k, ti=nm, v=round(r.v), n=int(r.n), share=round(100 * r.v / tot, 1)) for k, r in gin.iterrows()] + \
           [dict(fi=nm, ti=k, v=round(r.v), n=int(r.n), share=round(100 * r.v / tot, 1)) for k, r in gout.iterrows()]
    cols = money_cols([("fi", "From"), ("ti", "To"), ("v", "Value (QAR)"), ("share", "Share %"), ("n", "Payments")], money=("v",), ints=("n",))
    empty = go.Figure()
    fig_layout(empty, "Industry matrix", height=200)
    empty.update_layout(xaxis_visible=False, yaxis_visible=False, annotations=[dict(text="Switch to All QIB customers to see the industry-to-industry matrix.",
                        showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper", font=dict(size=13, color="#5c6b75"))])
    return sk, empty, bars, sorted(rows, key=lambda r: -r["v"]), cols


# ---------- overview ----------

@app.callback(Output("overview-graph", "elements"), Output("corridors", "figure"), Output("hubs", "figure"),
              Input("topn", "value"), Input("months", "value"), Input("routes", "value"), Input("banks", "value"),
              Input("types", "value"), Input("purposes", "value"))
def overview(topn, months, routes, banks, types, purposes):
    _, _, df = scope(months, routes, banks, types, purposes)
    pairs = pair_table(df[df.x == 0]).sort_values("v", ascending=False).head(topn)
    ids = set(pairs.s) | set(pairs.t)
    tot = pd.concat([pairs.groupby("s").v.sum(), pairs.groupby("t").v.sum()], axis=1).fillna(0).sum(axis=1)
    vmax, emax = (tot.max(), pairs.v.max()) if len(pairs) else (1, 1)
    els = [{"data": {"id": u, "label": short(ENTS.at[u, "name"]) if tot[u] > vmax * 0.08 else "", "name": ENTS.at[u, "name"],
                     "type": ENTS.at[u, "type"], "bank": ENTS.at[u, "bank"], "qib": bool(ENTS.at[u, "qib"]), "level": 1,
                     "color": TYPE_COLOR.get(ENTS.at[u, "type"], "#888"), "size": node_size(tot[u], vmax),
                     "inflow": 0, "outflow": 0}} for u in ids]
    els += [{"data": {"id": f"{p.s}>{p.t}", "source": p.s, "target": p.t, "color": ROUTE_COLOR[p.route],
                      "w": 1 + 8 * (p.v / emax) ** 0.5, "tier": 1}} for p in pairs.itertuples()]

    bt = bank_table(df)
    bt = bt[bt.bank != QIB].sort_values("total")
    corr = go.Figure([go.Bar(y=bt.bank, x=-bt.pays, orientation="h", name="QIB pays out", marker_color=OUT_C),
                      go.Bar(y=bt.bank, x=bt.receives, orientation="h", name="QIB receives", marker_color=IN_C)])
    fig_layout(corr, "QIB corridors with other Qatar banks (QAR)", height=380, l=220, barmode="relative")
    h = ENTS.sort_values("pr", ascending=False).head(15).iloc[::-1]
    hubs = go.Figure(go.Bar(y=h.name.map(short), x=h.pr, orientation="h", marker_color=[TYPE_COLOR.get(t, "#888") for t in h.type]))
    fig_layout(hubs, "Most influential entities (PageRank, full year)", height=380, l=200)
    return els, corr, hubs


app.index_string = app.index_string.replace("</head>", """<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap"><style>
body{margin:0;font-family:"Open Sans","Segoe UI",system-ui,sans-serif;background:#f4f7f9;color:#00111A}
.page{max-width:1600px;margin:0 auto;padding:16px;display:grid;gap:12px}
.brandbar{display:flex;align-items:center;gap:16px;background:#0075B0;color:#fff;border-radius:10px;padding:10px 18px}
.brandbar img{height:46px}.brandbar strong{display:block;font-size:22px;font-weight:600}.brandbar span{font-size:12.5px;opacity:.9}
.topbar{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:end;background:#fff;border:1px solid #dde5ea;border-top:3px solid #0075B0;border-radius:10px;padding:10px 16px}
.topbar label{font-size:11px;letter-spacing:.07em;text-transform:uppercase;font-weight:600;color:#5c6b75;display:block;margin-bottom:4px}
.topbar label:has(input){display:inline-flex;align-items:center;gap:6px;text-transform:none;letter-spacing:0;font-size:13px;font-weight:400;color:#00111A;margin:2px 10px 2px 0}
.layout{display:grid;grid-template-columns:280px minmax(0,1fr);gap:16px;align-items:start}
@media(max-width:900px){.layout{grid-template-columns:1fr}}
.controls{background:#fff;border:1px solid #dde5ea;border-radius:8px;padding:14px;display:grid;gap:6px;align-content:start}
.controls label,.egoctl label{font-size:12px;font-weight:600;color:#5c6b75;margin-top:8px;display:block}
.controls label:has(input),.egoctl label:has(input){display:inline-flex;align-items:center;gap:6px;font-weight:400;color:#00111A;margin:2px 10px 2px 0;font-size:13px}
.controls label:has(input){display:flex}
.layout>*,.main>*,.row2>*,.tab-content{min-width:0}
.mini{font-size:11px;margin-right:6px;padding:2px 8px;border:1px solid #dde5ea;background:#fff;border-radius:4px;cursor:pointer}
.egoctl{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:end;background:#fff;border:1px solid #dde5ea;border-radius:8px;padding:10px 14px}
.main{display:grid;gap:12px;min-width:0;padding-top:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}
.kpi{background:#fff;border:1px solid #dde5ea;border-radius:8px;padding:10px 12px}
.k-label{font-size:12px;color:#5c6b75}.k-val{font-size:20px;font-variant-numeric:tabular-nums;margin-top:2px;white-space:nowrap}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:#5c6b75}
.legend i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:-1px;box-sizing:border-box}
.legend b{display:inline-block;width:18px;height:3px;margin-right:5px;vertical-align:3px}
#graph,#overview-graph,#self-graph,#bank-graph{background:#fff;border:1px solid #dde5ea;border-radius:8px}
.panel{background:#fff;border:1px solid #dde5ea;border-radius:8px;padding:10px 14px}.panel h3,.panel h2{margin:0}
.note{font-size:12px;color:#5c6b75;margin:4px 0 8px}
.callout{background:#e2f0f8;border-radius:8px;padding:10px 14px;font-size:14px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}.chip{font-size:12px;border-radius:999px;padding:3px 10px;background:#e2f0f8;color:#0075B0}
.headline{font-size:15px;line-height:1.5;margin:6px 0 0}
.insights{margin:0;padding-left:18px;display:grid;gap:8px;font-size:13.5px;line-height:1.5}
.recs{display:grid;gap:10px}.rec{border:1px solid #dde5ea;border-left:4px solid #DF7A00;border-radius:8px;padding:10px 12px;background:#f4f7f9}
.rec h4{margin:2px 0;font-size:14px}.rec p{margin:0;font-size:13px;line-height:1.5}.rec .tag{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#5c6b75}
.info{font-size:13px;color:#5c6b75;min-height:20px}
.row2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px}
.tab--selected{border-top:3px solid #0075B0!important;color:#0075B0!important;font-weight:600}
</style></head>""")

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
