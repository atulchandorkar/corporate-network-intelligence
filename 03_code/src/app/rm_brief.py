"""Relationship-manager brief for one company: headline, insights and ranked recommendations.

Works on the flow table (s, t, m, r, c, b, x, n, v) after the dashboard filters. Mirrors the
RM brief in the web explorer (05_visualizations/interactive/explorer_src/template.html).
"""
import pandas as pd

from analytics import QIB

SHORT_BANK = {"Qatar National Bank": "QNB", "Commercial Bank of Qatar": "CBQ", "Qatar International Islamic Bank": "QIIB",
              "HSBC Bank Middle East - Qatar": "HSBC", "Standard Chartered Bank - Qatar": "Standard Chartered", QIB: "QIB"}


def qar(v):
    a = abs(v)
    s = f"{a/1e9:,.2f}B" if a >= 1e9 else f"{a/1e6:,.2f}M" if a >= 1e6 else f"{a/1e3:,.0f}K"
    return ("−" if v < 0 else "") + "QAR " + s


def bank_short(b):
    return SHORT_BANK.get(b, b)


def mlabel(m):
    return pd.Timestamp(m[:4] + "-" + m[4:] + "-01").strftime("%b %y")


def join(names):
    names = list(names)
    return "".join(names) if len(names) <= 1 else ", ".join(names[:-1]) + " and " + names[-1]


def pct(a, b):
    return round(100 * a / b) if b else 0


def _counterparties(rows, side, ents):
    if rows.empty:
        return pd.DataFrame(columns=["id", "name", "type", "industry", "bank", "bank_l", "v", "n", "months", "first", "last", "share"])
    g = rows.groupby(side).agg(v=("v", "sum"), n=("n", "sum"), months=("m", "nunique"), first=("m", "min"), last=("m", "max")).reset_index()
    g = g.rename(columns={side: "id"})
    e = ents.loc[g.id]
    g["name"], g["type"], g["industry"] = e.name.values, e.type.values, e.industry.values
    g["bank"] = [QIB if q else b for q, b in zip(e.qib.values, e.bank.values)]
    g["bank_l"] = g.bank.map(bank_short)
    g["share"] = g.v / g.v.sum()
    return g.sort_values("v", ascending=False).reset_index(drop=True)


def compute(flows, ents, c, months, types):
    """flows: already filtered by period, route, bank and purpose. Returns the numbers behind the brief."""
    e = ents.loc[c]
    other = flows.t.where(flows.s == c, flows.s)
    trade = flows[(flows.x == 0) & ((flows.s == c) | (flows.t == c)) & other.map(ents.type).isin(types)]
    inF, outF = trade[trade.t == c], trade[trade.s == c]
    selfF = flows[(flows.x == 1) & (flows.s == c)]
    by_m = lambda rows: rows.groupby("m").v.sum().reindex(months, fill_value=0)
    other_bank = (lambda rows: rows.b) if e.qib else (lambda rows: pd.Series(QIB, index=rows.index))
    cp = trade.t.where(trade.s == c, trade.s)
    first, last = trade.groupby(cp).m.min(), trade.groupby(cp).m.max()
    recent = months[-3:]
    changes = pd.DataFrame()
    if len(months) >= 6 and len(trade):
        val = trade.groupby(cp).v.sum()
        changes = pd.DataFrame({"id": val.index, "v": val.values, "first": first.reindex(val.index).values, "last": last.reindex(val.index).values})
        changes["status"] = ["New" if f >= recent[0] else "Lapsed" if l < recent[0] else "" for f, l in zip(changes["first"], changes["last"])]
        changes = changes[changes.status != ""].copy()
        changes["name"] = changes.id.map(ents.name)
        changes = changes.sort_values("v", ascending=False)
    rank = int(ents.pr.rank(ascending=False, method="first").get(c, 0))
    l1 = set(cp)
    base = flows[flows.x == 0]
    touch = base[base.s.isin(l1) | base.t.isin(l1)]
    l2 = (set(touch.s) | set(touch.t)) - l1 - {c}
    return dict(c=c, e=e, months=months, inF=inF, outF=outF, selfF=selfF,
                cust=_counterparties(inF, "s", ents), supp=_counterparties(outF, "t", ents),
                vin=inF.v.sum(), vout=outF.v.sum(), mIn=by_m(inF), mOut=by_m(outF),
                outOther=outF[other_bank(outF) != QIB], inOther=inF[other_bank(inF) != QIB],
                recent=recent, before=months[-6:-3], changes=changes, rank=rank, l1=l1, l2=l2, n_ents=len(ents))


def write(B, ents):
    """Headline, list of insight sentences, and up to six recommendations (tag, title, body) ranked by value."""
    e, months, cust, supp = B["e"], B["months"], B["cust"], B["supp"]
    vin, vout, inF, outF, selfF = B["vin"], B["vout"], B["inF"], B["outF"], B["selfF"]
    nm = e["name"]
    period = f"{mlabel(months[0])} to {mlabel(months[-1])}" if months else "the period"
    win = lambda rows, ms: rows[rows.m.isin(ms)].v.sum()
    ins, recs = [], []
    typ = lambda s: s.map(ents.type)
    gov_in = inF[typ(inF.s) == "Government"].v.sum()
    gre_in = inF[typ(inF.s) == "Company (GRE)"].v.sum()

    head = (f"{nm} has no payments in {period} with these filters." if vin + vout == 0 else
            f"In {period}, {nm} received {qar(vin)} from {len(cust)} payers and paid {qar(vout)} to {len(supp)} suppliers, "
            f"a net {'inflow' if vin >= vout else 'outflow'} of {qar(abs(vin - vout))}.")
    if not e["qib"]:
        head += f" It is not a QIB customer: it banks with {e['bank']} and trades with {len(B['l1'])} QIB customers."

    trend_in = None
    if len(B["recent"]) == 3 and len(B["before"]) == 3:
        ri, bi, ro, bo = win(inF, B["recent"]), win(inF, B["before"]), win(outF, B["recent"]), win(outF, B["before"])
        if bi and bo:
            ci, co = round(100 * (ri - bi) / bi), round(100 * (ro - bo) / bo)
            mood = ("Activity is steady" if abs(ci) < 10 and abs(co) < 10 else "Activity is picking up" if ci >= 0 and co >= 0
                    else "Activity is slowing" if ci < 0 and co < 0 else "Recent activity is mixed")
            ins.append(f"{mood}: receipts in {mlabel(B['recent'][0])}–{mlabel(B['recent'][2])} were {'up' if ci >= 0 else 'down'} {abs(ci)}% "
                       f"on the three months before, and payments were {'up' if co >= 0 else 'down'} {abs(co)}%.")
            trend_in = ci
    if len(cust):
        txt = f"{cust.name[0]} is the largest payer with {pct(cust.v[0], vin)}% of receipts; the top three payers bring {pct(cust.v[:3].sum(), vin)}%."
        if vin and gov_in / vin >= 0.4:
            txt += f" Government bodies account for {pct(gov_in, vin)}% of receipts"
            txt += f" and government-related companies {pct(gre_in, vin)}%" if gre_in / vin >= 0.1 else ""
            txt += ", so income follows government payment cycles."
        ins.append(txt)
    if len(supp):
        top_purpose = outF.groupby("c").v.sum().idxmax()
        ins.append(f"{supp.name[0]} is the largest supplier with {pct(supp.v[0], vout)}% of payments; the top three take "
                   f"{pct(supp.v[:3].sum(), vout)}%. The biggest payment purpose is {top_purpose}.")
    out_other, in_other = B["outOther"], B["inOther"]
    if e["qib"] and vout:
        s_other = supp[supp.bank != QIB]
        top_b = out_other.groupby("b").v.sum().idxmax() if len(out_other) else None
        txt = f"{pct(out_other.v.sum(), vout)}% of payments ({qar(out_other.v.sum())}) go to {len(s_other)} suppliers banking outside QIB"
        txt += f", most at {bank_short(top_b)}." if top_b else "."
        txt += f" {pct(in_other.v.sum(), vin)}% of receipts arrive from other banks." if vin else ""
        ins.append(txt)
    self_net = 0
    self_banks = []
    if len(selfF):
        so, si = selfF[selfF.r == "QIB_TO_OTHER"].v.sum(), selfF[selfF.r == "OTHER_TO_QIB"].v.sum()
        self_banks = sorted({bank_short(b) for b in selfF.b if b != QIB})
        ins.append(f"{nm} moved {qar(so)} of its own money from QIB to its accounts at {join(self_banks) or 'other banks'} and brought back "
                   f"{qar(si)}: a net {'outflow' if so >= si else 'inflow'} of {qar(abs(so - si))}.")
        self_net = so - si
    m_in, m_out = B["mIn"], B["mOut"]
    gaps = [m for m in months if m_out[m] > m_in[m]]
    if len(months) >= 4 and vin + vout:
        pk = m_in.idxmax()
        txt = f"Receipts peak in {mlabel(pk)} ({qar(m_in[pk])})."
        txt += (f" Payments exceeded receipts in {len(gaps)} of {len(months)} months ({join([mlabel(m) for m in gaps[:4]])}{', …' if len(gaps) > 4 else ''})."
                if gaps else " Receipts covered payments every month.")
        ins.append(txt)
    ch = B["changes"]
    if len(ch):
        nw, lp = ch[ch.status == "New"], ch[ch.status == "Lapsed"]
        txt = (f"{len(nw)} new counterpart{'y' if len(nw) == 1 else 'ies'} appeared in the last three months (largest: {nw.name.iloc[0]})"
               if len(nw) else "No new counterparties appeared in the last three months")
        txt += (f"; {len(lp)} went quiet, the largest being {lp.name.iloc[0]} ({qar(lp.v.iloc[0])} earlier in the period)." if len(lp) else "; none went quiet.")
        ins.append(txt)
    ins.append(f"In the payment network {nm} ranks #{B['rank']} of {B['n_ents']} by influence, trades directly with {len(B['l1'])} "
               f"entities and reaches {len(B['l2'])} more through them.")

    # recommendations; credit-style ones do not apply to government bodies
    gv = e["type"] == "Government"
    if not e["qib"]:
        intro = join(pd.concat([cust, supp]).loc[lambda d: d.id.map(ents.qib).astype(bool)].name.head(2))
        recs.append((vin + vout, "Acquisition", f"Bring {nm} to QIB",
                     f"{nm} banks with {e['bank']} but exchanged {qar(vin + vout)} with {len(B['l1'])} QIB customers. Ask {intro or 'those customers'} "
                     f"for an introduction and offer an account that keeps these payments on-us."))
    s_other = supp[(supp.bank != QIB) & ~supp.type.isin(["Government", "Individual"])]
    if e["qib"] and len(s_other) and out_other.v.sum() / max(vout, 1) >= 0.15:
        start = join([f"{r.name} ({qar(r.v)}, {r.bank_l})" for r in s_other.head(3).itertuples()])
        recs.append((s_other.v.sum(), "Supply chain", "Onboard key suppliers and offer supplier finance",
                     f"{qar(s_other.v.sum())} went to {len(s_other)} suppliers banking elsewhere. Start with {start}. A supply-chain finance "
                     f"programme lets them be paid early through QIB and keeps the money inside the bank."))
    c_other = cust[cust.bank != QIB]
    if e["qib"] and len(c_other) and in_other.v.sum() / max(vin, 1) >= 0.25:
        gov = c_other[c_other.type == "Government"]
        if len(gov) and gov.v.sum() / c_other.v.sum() > 0.5:
            recs.append((c_other.v.sum(), "Collections", "Finance government receivables",
                         f"{qar(gov.v.sum())} of receipts come from {join(gov.name.head(3))} through other banks. Offer contract or invoice "
                         f"financing against these government receivables and ask for payments to be directed to the QIB account."))
        else:
            recs.append((c_other.v.sum(), "Collections", "Capture receivables at QIB",
                         f"{len(c_other)} payers send {qar(c_other.v.sum())} from other banks, led by {join(c_other.name.head(3))}. "
                         f"Offer collection accounts with virtual IBANs so receipts land and reconcile at QIB."))
    if self_net > 0:
        recs.append((self_net, "Deposit retention", "Keep liquidity at QIB",
                     f"{nm} moved a net {qar(self_net)} of its own money to {join(self_banks)}. Ask why, and offer a liquidity sweep or a "
                     f"competitive term-deposit profit rate so surplus cash stays with QIB."))
    if not gv and len(gaps) >= 3 and vout:
        gap_v = [m_out[m] - m_in[m] for m in gaps]
        recs.append((sum(gap_v), "Working capital", "Offer a working-capital line for cash-gap months",
                     f"Payments ran ahead of receipts in {len(gaps)} months, by up to {qar(max(gap_v))}. A revolving Murabaha or "
                     f"overdraft-style facility sized to that gap smooths supplier payments."))
    if not gv and len(cust) and cust.share[0] >= 0.4 and cust.type[0] != "Government":
        recs.append((cust.v[0] * 0.5, "Risk", "Watch customer concentration",
                     f"{pct(cust.v[0], vin)}% of receipts come from {cust.name[0]}. Factor this into credit reviews and ask about contract terms and renewal dates."))
    if not gv and trend_in is not None and trend_in <= -20:
        recs.append((abs(win(inF, B["before"]) - win(inF, B["recent"])), "Early warning", "Check in on falling receipts",
                     f"Receipts dropped {abs(trend_in)}% in the last three months. Ask whether contracts ended or payments moved to another bank."))
    if not gv and trend_in is not None and trend_in >= 25:
        recs.append((win(inF, B["recent"]) - win(inF, B["before"]), "Growth", "Support the growth",
                     f"Receipts rose {trend_in}% in the last three months. Review limits and offer financing for the extra volume before a competitor does."))
    if len(ch):
        lp = ch[ch.status == "Lapsed"]
        if len(lp) and lp.v.sum() > 0.05 * (vin + vout):
            recs.append((lp.v.sum(), "Relationships", "Ask about lapsed counterparties",
                         f"{join(lp.name.head(3))} traded {qar(lp.v.head(3).sum())} earlier but nothing in the last three months. "
                         f"Find out whether the business ended or moved."))
    salary = outF[outF.c.str.contains("salary|payroll", case=False)]
    if e["qib"] and salary[salary.b != QIB].v.sum() >= max(1e6, 0.02 * vout):
        recs.append((salary.v.sum(), "Payroll", "Win the payroll mandate",
                     f"{qar(salary.v.sum())} of salary payments went out, part of it to other banks. Offer QIB payroll (WPS) and employee accounts."))
    recs.sort(key=lambda r: -r[0])
    return head, ins, [dict(tag=t, title=ti, body=b) for _, t, ti, b in recs[:6]]
