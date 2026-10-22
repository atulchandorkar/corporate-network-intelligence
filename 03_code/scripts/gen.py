# Run with PYTHONHASHSEED=0 for an identical data set each time (set iteration order affects sampling).
import random, datetime as dt, string
import numpy as np, pandas as pd

random.seed(42); np.random.seed(42)
from pathlib import Path
OUT = str(Path(__file__).resolve().parents[2] / "01_data" / "synthetic") + "/"   # run with PYTHONHASHSEED=0 for the same data

# ---------------- Banks ----------------
BANKS = {  # name: (code, IBAN bank id)
    "Qatar Islamic Bank": (4, "QISB"),
    "Qatar National Bank": (1, "QNBA"),
    "Commercial Bank of Qatar": (2, "CBQA"),
    "Doha Bank": (3, "DOHB"),
    "Ahli Bank": (5, "ABQQ"),
    "Qatar International Islamic Bank": (6, "QIIB"),
    "Masraf Al Rayan": (7, "MAFR"),
    "Dukhan Bank": (8, "BRWA"),
    "HSBC Bank Middle East - Qatar": (9, "BBME"),
    "Standard Chartered Bank - Qatar": (10, "SCBL"),
}
QIB = "Qatar Islamic Bank"
OTHER_BANKS = [b for b in BANKS if b != QIB]
OTHER_BANK_W = [30, 14, 10, 5, 8, 10, 6, 4, 3]  # QNB biggest

# ---------------- Entities ----------------
# name, kind, industry, size weight, group, role-tags
C = []
def add(name, kind, ind, w, group=None, tags=()):
    C.append(dict(name=name, kind=kind, industry=ind, w=w, group=group, tags=set(tags)))

# Energy / industrial GREs
add("QatarEnergy", "GRE", "Oil & Gas", 10, "QE", ["hub"])
add("QatarEnergy LNG", "GRE", "Oil & Gas", 8, "QE", ["hub"])
add("Industries Qatar QPSC", "GRE", "Petrochemicals", 5, "IQ")
add("Qatar Petrochemical Company (QAPCO)", "GRE", "Petrochemicals", 4, "IQ")
add("Qatar Fertiliser Company (QAFCO)", "GRE", "Petrochemicals", 4, "IQ")
add("Qatar Steel Company", "GRE", "Manufacturing", 3, "IQ")
add("Mesaieed Petrochemical Holding Company", "GRE", "Petrochemicals", 2, "QE")
add("Muntajat", "GRE", "Petrochemicals", 2, "QE")
add("Qatar Fuel Company (WOQOD)", "GRE", "Fuel Distribution", 5, None, ["utility"])
add("Gulf International Services", "GRE", "Oil & Gas Services", 2, "QE")
add("Gulf Drilling International", "GRE", "Oil & Gas Services", 2, "QE")
add("Qatar Electricity & Water Company (QEWC)", "GRE", "Utilities", 4, None)
add("Kahramaa (Qatar General Electricity & Water Corporation)", "GRE", "Utilities", 7, None, ["utility", "hub"])
# Transport / telecom / media
add("Qatar Airways Group", "GRE", "Aviation", 10, "QR", ["hub"])
add("Qatar Duty Free", "GRE", "Retail", 3, "QR")
add("Qatar Aviation Services", "GRE", "Aviation", 2, "QR")
add("Ooredoo QPSC", "GRE", "Telecommunication", 8, None, ["utility", "hub"])
add("Vodafone Qatar", "Corporate", "Telecommunication", 4, None, ["utility"])
add("Qatar Gas Transport Company (Nakilat)", "GRE", "Shipping & Logistics", 4, None)
add("Qatar Navigation (Milaha)", "Corporate", "Shipping & Logistics", 4, None)
add("Gulf Warehousing Company (GWC)", "Corporate", "Shipping & Logistics", 3, None)
add("Mowasalat (Karwa)", "GRE", "Transport", 3, None)
add("Qatar Rail", "GRE", "Transport", 3, None)
add("Al Jazeera Media Network", "GRE", "Media", 2, None)
add("beIN Media Group", "Corporate", "Media", 3, None)
# Real estate / construction
add("Qatari Diar Real Estate Investment Company", "GRE", "Real Estate", 5, None, ["landlord"])
add("Barwa Real Estate Company", "Corporate", "Real Estate", 5, None, ["landlord"])
add("Ezdan Holding Group", "Corporate", "Real Estate", 4, None, ["landlord"])
add("United Development Company (UDC)", "Corporate", "Real Estate", 4, None, ["landlord"])
add("Msheireb Properties", "GRE", "Real Estate", 3, None, ["landlord"])
add("Mazaya Real Estate Development", "Corporate", "Real Estate", 2, None, ["landlord"])
add("Katara Hospitality", "GRE", "Hospitality", 3, None)
add("UrbaCon Trading & Contracting (UCC)", "Corporate", "Construction & Contracting", 5, "UCC", ["contractor"])
add("Midmac Contracting", "Corporate", "Construction & Contracting", 4, None, ["contractor"])
add("HBK Contracting Company", "Corporate", "Construction & Contracting", 3, None, ["contractor"])
add("Redco Construction - Almana", "Corporate", "Construction & Contracting", 3, None, ["contractor"])
add("QDVC (Qatari Diar Vinci Construction)", "Corporate", "Construction & Contracting", 3, None, ["contractor"])
add("Power International Holding", "Corporate", "Conglomerate", 5, "UCC", ["contractor"])
add("Qatar National Cement Company", "Corporate", "Building Materials", 3, None, ["supplier"])
add("Qatar Primary Materials Company", "GRE", "Building Materials", 2, None, ["supplier"])
add("Qatar Industrial Manufacturing Company", "Corporate", "Manufacturing", 2, None, ["supplier"])
# Conglomerates / trading
add("Estithmar Holding", "Corporate", "Conglomerate", 4, "EST", ["contractor"])
add("Elegancia Group", "Corporate", "Services", 2, "EST", ["supplier"])
add("Aamal Company", "Corporate", "Conglomerate", 3, None, ["supplier"])
add("Salam International Investment", "Corporate", "Conglomerate", 2, None, ["supplier"])
add("Al Faisal Holding", "Corporate", "Conglomerate", 3, None)
add("Alfardan Group", "Corporate", "Conglomerate", 3, None, ["supplier"])
add("Jaidah Group", "Corporate", "Automotive & Trading", 3, None, ["supplier"])
add("Nasser Bin Khaled Holding", "Corporate", "Automotive & Trading", 3, None, ["supplier"])
add("Teyseer Group", "Corporate", "Conglomerate", 2, None, ["supplier"])
add("Mannai Corporation", "Corporate", "IT & Trading", 3, None, ["supplier"])
add("Al Mana Group", "Corporate", "Retail", 2, None, ["supplier"])
# Food / retail / health
add("Hassad Food", "GRE", "Food & Agriculture", 3, None, ["supplier"])
add("Baladna QPSC", "Corporate", "Food & Agriculture", 4, None, ["supplier"])
add("Widam Food Company", "Corporate", "Food & Agriculture", 2, None, ["supplier"])
add("Qatar Flour Mills", "Corporate", "Food & Agriculture", 2, None, ["supplier"])
add("Al Meera Consumer Goods Company", "Corporate", "Retail", 4, None)
add("Medicare Group", "Corporate", "Healthcare", 2, None, ["supplier"])
add("Hamad Medical Corporation", "Government", "Healthcare", 5, None, ["hub"])
add("Qatar Foundation", "GRE", "Education", 5, None, ["hub"])
add("Aspire Zone Foundation", "GRE", "Sports", 2, None)
# Insurance / finance
add("Qatar Insurance Company (QIC)", "Corporate", "Insurance", 4, None, ["insurer"])
add("Doha Insurance Group", "Corporate", "Insurance", 2, None, ["insurer"])
add("Qatar Islamic Insurance Group", "Corporate", "Insurance", 2, None, ["insurer"])
add("QLM Life & Medical Insurance", "Corporate", "Insurance", 2, None, ["insurer"])
add("Al Khaleej Takaful Insurance", "Corporate", "Insurance", 1, None, ["insurer"])
add("Qatar Investment Authority", "Government", "Sovereign Investment", 4, None)
# Government
add("Ministry of Finance", "Government", "Public Administration", 10, None, ["hub", "payer", "taxman"])
add("Ministry of Defence", "Government", "Defence", 7, None, ["hub", "payer"])
add("Ministry of Interior", "Government", "Public Administration", 7, None, ["hub", "payer", "taxman"])
add("Ministry of Public Health", "Government", "Healthcare", 4, None, ["payer"])
add("Ministry of Education and Higher Education", "Government", "Education", 4, None, ["payer"])
add("Ministry of Municipality", "Government", "Public Administration", 3, None, ["payer", "taxman"])
add("Ministry of Commerce and Industry", "Government", "Public Administration", 3, None, ["taxman"])
add("Ministry of Labour", "Government", "Public Administration", 2, None, ["taxman"])
add("Ministry of Awqaf and Islamic Affairs", "Government", "Religious Affairs", 2, None, ["payer"])
add("Public Works Authority (Ashghal)", "Government", "Infrastructure", 8, None, ["hub", "payer"])
add("General Tax Authority", "Government", "Public Administration", 4, None, ["taxman"])
add("Supreme Committee for Delivery & Legacy", "Government", "Sports", 3, None, ["payer"])
add("Qatar Free Zones Authority", "Government", "Public Administration", 2, None, ["taxman"])
add("Qatar Tourism", "Government", "Tourism", 2, None, ["payer"])
# Charities
add("Qatar Charity", "Charity", "Charity & Non-Profit", 4, None, ["charity"])
add("Qatar Red Crescent Society", "Charity", "Charity & Non-Profit", 3, None, ["charity"])
add("Sheikh Eid Bin Mohammad Al Thani Charitable Association (Eid Charity)", "Charity", "Charity & Non-Profit", 3, None, ["charity"])
add("Sheikh Thani Bin Abdullah Foundation for Humanitarian Services (RAF)", "Charity", "Charity & Non-Profit", 2, None, ["charity"])
add("Education Above All Foundation", "Charity", "Charity & Non-Profit", 2, None, ["charity"])
add("Zakat Fund", "Charity", "Charity & Non-Profit", 2, None, ["charity"])

# Individuals (fictional)
FIRST = ["Mohammed", "Ahmed", "Abdullah", "Khalid", "Hamad", "Fatima", "Mariam", "Aisha", "Rajesh", "Suresh",
         "Imran", "Farrukh", "Joseph", "Maria", "Ali", "Omar", "Yousef", "Noura", "Priya", "Anil",
         "Tariq", "Hassan", "Salma", "Ramon", "Bilal", "Faisal", "Rania", "Sanjay", "Grace", "Kareem"]
LAST = ["Al Kuwari", "Al Marri", "Al Sulaiti", "Al Naimi", "Al Hajri", "Al Mohannadi", "Al Emadi", "Nair",
        "Menon", "Khan", "Jamaluddin", "Fernandes", "Santos", "Hussain", "Haddad", "Mansour", "Sharma",
        "Pillai", "Qureshi", "Rahman", "Abdelaziz", "Mahmoud", "Dela Cruz", "Kaur"]
inds = set()
while len(inds) < 70:
    inds.add(f"{random.choice(FIRST)} {random.choice(LAST)}".upper())
for n in sorted(inds):
    add(n, "Individual", "Individual", 1, None, ["individual"])

E = pd.DataFrame(C)

# --- QIB customers: the account holders whose statements we generate ---
cust_names = [
    "QatarEnergy", "Ooredoo QPSC", "Qatar Airways Group", "Industries Qatar QPSC",
    "Qatar Fuel Company (WOQOD)", "Barwa Real Estate Company", "Qatari Diar Real Estate Investment Company",
    "UrbaCon Trading & Contracting (UCC)", "Power International Holding", "Midmac Contracting",
    "HBK Contracting Company", "Estithmar Holding", "Elegancia Group", "Aamal Company", "Baladna QPSC",
    "Hassad Food", "Al Meera Consumer Goods Company", "Qatar Navigation (Milaha)", "Gulf Warehousing Company (GWC)",
    "Qatar Gas Transport Company (Nakilat)", "Mowasalat (Karwa)", "Msheireb Properties", "Katara Hospitality",
    "Qatar National Cement Company", "Jaidah Group", "Mannai Corporation", "Medicare Group",
    "Qatar Islamic Insurance Group", "Al Khaleej Takaful Insurance", 
    "Qatar Electricity & Water Company (QEWC)", "Ministry of Awqaf and Islamic Affairs",
    "Qatar Charity", "Sheikh Eid Bin Mohammad Al Thani Charitable Association (Eid Charity)", "Qatar Foundation",
    "Alfardan Group", "Salam International Investment", "Qatar Steel Company", "Mazaya Real Estate Development",
    "Widam Food Company", "Qatar Primary Materials Company", "Qatar Rail", "Teyseer Group",
]
E["is_cust"] = E.name.isin(cust_names)
assert E.is_cust.sum() == len(cust_names)

def rand_digits(n): return "".join(random.choice(string.digits) for _ in range(n))

def iban(bank_id, bban):
    # Valid ISO 13616 mod-97 check digits for QA
    s = bank_id + bban + "QA00"
    num = "".join(str(int(ch, 36)) for ch in s)
    chk = 98 - int(num) % 97
    return f"QA{chk:02d}{bank_id}{bban}"

# home bank for everyone
def home_bank(r):
    if r.is_cust:
        return QIB
    p = 0.30 if r.kind == "Individual" else 0.15   # some non-customers still bank with QIB
    if r.kind == "Government" and random.random() < 0.8:
        return "Qatar National Bank"
    return QIB if random.random() < p else random.choices(OTHER_BANKS, OTHER_BANK_W)[0]
E["bank"] = E.apply(home_bank, axis=1)
E["bban"] = [rand_digits(21) for _ in range(len(E))]
E["iban"] = [iban(BANKS[b][1], x) for b, x in zip(E.bank, E.bban)]
E["usd_bban"] = [rand_digits(21) for _ in range(len(E))]
E["usd_iban"] = [iban(BANKS[b][1], x) for b, x in zip(E.bank, E.usd_bban)]
E["cif"] = [rand_digits(7) for _ in range(len(E))]
E["cp_key"] = ["C_" + rand_digits(8) for _ in range(len(E))]
E["prospect_id"] = [("P" + rand_digits(7)) if random.random() < 0.35 else None for _ in range(len(E))]

# customer attributes
SECT = {
    "GRE": (701, "Corp 1 - Govt and Related Entities", "Corp I - GRE"),
    "Government": (700, "Corp 0 - Government", "Corp I - GRE"),
    "Corporate_L": (702, "Corp 2 - Large Corporates", "Corp II - Large Corporate"),
    "Corporate_C": (704, "Corp 4 - Contracting", "Corp IV - Contracting & Real Estate"),
    "Corporate_M": (703, "Corp 3 - Mid Corporates", "Corp III - Mid Market"),
    "Charity": (705, "Corp 5 - Non-Profit & Charities", "Corp III - Mid Market"),
}
IND_CODES = {}
for i, ind in enumerate(sorted(E.industry.unique())):
    IND_CODES[ind] = 4101 + i * 4 if ind != "Telecommunication" else 4205
OFFICERS = [(6112, "Mohamed Rajab"), (6118, "Sara Al Ansari"), (6125, "Rashid Al Khater"), (6131, "Vikram Desai"),
            (6140, "Nadia Saleh"), (6147, "Omar Al Baker"), (6153, "Lina Khoury"), (6160, "Abdulrahman Al Obaidli")]

def seg(r):
    if r.kind in ("GRE", "Government"): return SECT[r.kind]
    if r.kind == "Charity": return SECT["Charity"]
    if r.industry in ("Construction & Contracting", "Real Estate", "Building Materials"): return SECT["Corporate_C"]
    return SECT["Corporate_L"] if r.w >= 3 else SECT["Corporate_M"]

cust = E[E.is_cust].copy()
cust["sector"] = cust.apply(seg, axis=1)
cust["officer"] = [random.choice(OFFICERS) for _ in range(len(cust))]
cust["rating"] = [random.choices([1, 2, 3, 4, 5, 6, 7], [10, 25, 25, 18, 12, 6, 4])[0] for _ in range(len(cust))]
cust["vintage"] = [dt.date(1985, 1, 1) + dt.timedelta(days=random.randint(0, 13000)) for _ in range(len(cust))]
cust = cust.set_index("name")
E = E.set_index("name")

# ---------------- Relationships ----------------
def pick_type(c, p):
    """Return (classification, direction D/C, median QAR, sub_class) for customer c paying/receiving p."""
    ce, pe = E.loc[c], E.loc[p]
    if ce.group and ce.group == pe.group:
        return ("Intercompany Transfer", random.choice("DC"), 4_000_000, "Group Treasury")
    if "utility" in ce.tags and pe.kind != "Government":
        return ("Utility Payment", "C", 25_000 if pe.kind != "Individual" else 600, c)
    if "utility" in pe.tags:
        return ("Utility Payment", "D", 40_000, p)
    if pe.kind == "Individual":
        if "charity" in ce.tags: return ("Donation Received", "C", 2_000, "Individual Donation")
        if "landlord" in ce.tags: return ("Rent Received", "C", 9_000, "Residential Lease")
        if "insurer" in ce.tags: return (random.choice(["Insurance Premium", "Claim Settlement"]), None, 5_000, "Retail Policy")
        return (random.choice(["Salary Payment", "Salary Payment", "Employee Reimbursement"]), "D", 22_000, "WPS Payroll")
    if pe.kind == "Government":
        if "taxman" in pe.tags and ("payer" not in pe.tags or random.random() < 0.5):
            return ("Government Fees & Taxes", "D", 180_000, p)
        if ce.kind in ("GRE", "Government"):
            return ("Government Funding", "C", 25_000_000, "Budget Allocation")
        return ("Government Contract Payment", "C", 3_500_000, "Project Milestone")
    if pe.kind == "Charity":
        if "charity" in ce.tags: return ("Charity Grant Transfer", random.choice("DC"), 400_000, "Joint Program")
        return (random.choice(["Charity Donation", "Zakat Payment"]), "D", 150_000, p)
    if "charity" in ce.tags:
        return ("Donation Received", "C", 300_000, "Corporate Donation")
    if "insurer" in pe.tags:
        return ("Insurance Premium", "D", 90_000, "Corporate Policy")
    if "insurer" in ce.tags:
        return ("Insurance Premium", "C", 90_000, "Corporate Policy")
    if "landlord" in pe.tags:
        return ("Rent Payment", "D", 150_000, "Commercial Lease")
    if "landlord" in ce.tags and random.random() < 0.5:
        return ("Rent Received", "C", 150_000, "Commercial Lease")
    if "contractor" in pe.tags and ce.kind in ("GRE", "Government") :
        return ("Contract Payment", "D", 2_500_000, "Project Milestone")
    if "contractor" in ce.tags and ("supplier" in pe.tags or pe.industry in ("Building Materials", "Manufacturing")):
        return ("Supplier Payment", "D", 600_000, "Materials Purchase")
    if pe.industry in ("Oil & Gas", "Petrochemicals", "Shipping & Logistics", "Aviation") or ce.industry in ("Oil & Gas", "Petrochemicals"):
        return (random.choice(["Trade Finance Settlement", "Supplier Payment"]), random.choice("DC"), 1_800_000, "LC / Supply Contract")
    return ("Supplier Payment", random.choice("DDC"), 280_000, "Goods & Services")

rels = []
orgs = E[E.kind != "Individual"]
indiv = E[E.kind == "Individual"].index.tolist()
for c in cust.index:
    w = E.loc[c, "w"]
    n_cp = int(np.clip(np.random.poisson(4 + 2.2 * w), 4, 40))
    pool = [x for x in orgs.index if x != c]
    weights = np.array([orgs.loc[x, "w"] ** 1.6 * (3 if "hub" in orgs.loc[x, "tags"] else 1) *
                        (4 if E.loc[c, "group"] and orgs.loc[x, "group"] == E.loc[c, "group"] else 1) for x in pool], float)
    chosen = set(np.random.choice(pool, size=min(n_cp, len(pool)), replace=False, p=weights / weights.sum()))
    # always-on links: utilities, MoF
    for must in ["Kahramaa (Qatar General Electricity & Water Corporation)", "Ooredoo QPSC", "General Tax Authority"]:
        if must != c and random.random() < 0.7: chosen.add(must)
    # a few individuals (kept small)
    k_ind = np.random.choice([1, 2, 3, 4, 6], p=[0.25, 0.25, 0.2, 0.15, 0.15])
    chosen |= set(random.sample(indiv, k_ind))
    for p in chosen:
        cls, d, med, sub = pick_type(c, p)
        freq = np.random.lognormal(0, 0.9) * (E.loc[c, "w"] * E.loc[p, "w"]) ** 0.5
        if E.loc[p, "kind"] == "Individual": freq *= 1.6
        if E.loc[p, "kind"] == "Charity": freq *= 1.8
        rels.append(dict(c=c, p=p, cls=cls, d=d, med=med, sub=sub, freq=freq))
R = pd.DataFrame(rels)
print("relationships", len(R), "customers", len(cust))

# ---------------- Transactions ----------------
CLS_META = {  # classification: (transaction_code, transaction_type, channel)
    "Utility Payment": (335, "ACUT", "BILL_PAYMENT"),
    "Salary Payment": (213, "ACSA", "WPS_SALARY"),
    "Employee Reimbursement": (214, "ACOT", "FUNDS_TRANSFER"),
    "Supplier Payment": (221, "ACOT", "FUNDS_TRANSFER"),
    "Contract Payment": (222, "ACOT", "FUNDS_TRANSFER"),
    "Government Contract Payment": (231, "ACIN", "FUNDS_TRANSFER"),
    "Government Funding": (232, "ACIN", "FUNDS_TRANSFER"),
    "Government Fees & Taxes": (341, "ACGP", "BILL_PAYMENT"),
    "Trade Finance Settlement": (410, "ACLC", "SWIFT"),
    "Intercompany Transfer": (250, "ACIC", "FUNDS_TRANSFER"),
    "Rent Payment": (261, "ACOT", "CHEQUE"),
    "Rent Received": (262, "ACIN", "CHEQUE"),
    "Charity Donation": (271, "ACOT", "FUNDS_TRANSFER"),
    "Zakat Payment": (272, "ACOT", "FUNDS_TRANSFER"),
    "Donation Received": (273, "ACIN", "FUNDS_TRANSFER"),
    "Charity Grant Transfer": (274, "ACOT", "FUNDS_TRANSFER"),
    "Insurance Premium": (281, "ACOT", "FUNDS_TRANSFER"),
    "Claim Settlement": (282, "ACIN", "FUNDS_TRANSFER"),
}
CHANNELS = [("Internet Banking", "OIB", 45), ("Mobile Banking", "OMB", 15), ("Host-to-Host", "H2H", 20),
            ("Branch", "BRN", 10), ("SWIFT", "SWF", 10)]
START, END = dt.date(2022, 8, 1), dt.date(2023, 7, 31)
DAYS = [START + dt.timedelta(d) for d in range((END - START).days + 1)]
DAY_W = np.array([0.08 if d.weekday() == 4 else 0.25 if d.weekday() == 5 else 1.0 for d in DAYS])  # Fri/Sat weekend
DAY_W[[i for i, d in enumerate(DAYS) if d.day >= 25 or d.day <= 2]] *= 1.6  # month-end payroll/settlements
DAY_W /= DAY_W.sum()

N = 4600  # internal transfers add mirrored legs -> ~5,000 rows
idx = np.random.choice(len(R), size=N, p=(R.freq / R.freq.sum()).values)
rows, entry = [], 199360000000000
def ref(d): return f"FT{d.strftime('%y')}{d.timetuple().tm_yday:03d}" + "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))

def make_row(c, p, cls, d, sub, amt, date, ccy, reference, ch):
    global entry
    entry += random.randint(1, 40)
    ce, pe, cu = E.loc[c], E.loc[p], cust.loc[c]
    code, ttype, tchan = CLS_META[cls]
    if ttype in ("ACOT", "ACIN"): ttype = "ACOT" if d == "D" else "ACIN"
    if pe.bank == QIB and tchan == "FUNDS_TRANSFER": tchan = "INTERNAL_TRANSFER"
    o_iban = ce.usd_iban if ccy != "QAR" else ce.iban
    cp_iban = pe.usd_iban if ccy != "QAR" else pe.iban
    fx = {"QAR": 1, "USD": 3.64, "EUR": 3.95}[ccy]
    sec_code, sec_name, bu = cu.sector
    batch = (date.replace(day=1) + dt.timedelta(days=32)).replace(day=7)
    return {
        "BOOKING_DATE": date, "STMT_ENTRY_ID": str(entry), "TRANSACTION_CODE": code,
        "AMOUNT_LCY": round(amt, 2), "CURRENCY": ccy, "CUSTOMER_ID": ce.cif, "CUSTOMER_NAME": c,
        "DEBIT_CREDIT_IND": d, "CHANNEL_TYPE": ch[0], "TXN_CLASSIFICATION": cls, "TXN_SUB_CLASSIFICATION": sub,
        "TRANSACTION_CHANNEL": tchan,
        "PURPOSE_DESC": (random.choice(["Invoice settlement", "Monthly payment", "Project payment", "As per contract", "Advance payment"])
                         if random.random() < 0.45 else None),
        "O_IBAN_NUMBER": o_iban, "O_BANK_CD": BANKS[QIB][0],
        "CP_ACCOUNT_NUMBER": cp_iban[8:], "CP_CUSTOMER_NAME": p, "CP_BANK_CD": BANKS[pe.bank][0],
        "CP_IBAN_NUMBER": cp_iban, "CP_CURRENCY": ccy, "O_PART_IBAN": o_iban[4:], "CP_PART_IBAN": cp_iban[4:],
        "CHANNEL_ID": ch[1], "QIB_RATING": cu.rating, "UNIQUE_ID": pe.cp_key,
        "MATCH_CIF_ID": pe.cif if pe.bank == QIB else None,  # every QIB account holder has a CIF
        "PROSPECT_NAME": p, "TRANSACTION_TYPE": ttype, "TXN_INITIATED": "YES" if d == "D" else "NO",
        "ACCOUNT_OFFICER": cu.officer[0], "ACCOUNT_OFFICER_NAME": cu.officer[1],
        "SECTOR": sec_code, "SECTOR_NAME": sec_name, "INDUSTRY": IND_CODES[ce.industry], "INDUSTRY_NAME": ce.industry,
        "VINTAGE": cu.vintage, "BUSINESS_UNIT": bu, "BUSINESS_GROUP": "WBG", "BANK_NAME": QIB,
        "PROSPECT_ID": None if pe.bank == QIB or pe.kind == "Individual" else pe.prospect_id,
        "BOOKING_DATE_SK": int(date.strftime("%Y%m%d")), "BOOKING_MONTH_SK": int(date.strftime("%Y%m")),
        "BATCH_DATE": batch, "COMPANY_FLAG": None if pe.kind == "Individual" else "Y",
        "AMOUNT_FCY": round(amt / fx, 2) if ccy != "QAR" else None, "OUR_REFERENCE": reference,
    }

for i in idx:
    r = R.iloc[i]
    d = r.d or random.choice("DC")
    if r.cls == "Insurance Premium" and E.loc[r.p, "kind"] == "Individual": d = "C"
    if r.cls == "Claim Settlement": d = "D" if "insurer" in E.loc[r.c, "tags"] else "C"
    cls = r.cls
    # occasional reversal-direction flows in a relationship (refunds, adjustments)
    if random.random() < 0.06 and cls not in ("Intercompany Transfer",):
        d = "C" if d == "D" else "D"
    amt = float(np.random.lognormal(np.log(r.med), 0.8))
    amt = round(amt, -2) if amt > 10_000 and random.random() < 0.6 else round(amt, 2)
    date = DAYS[np.random.choice(len(DAYS), p=DAY_W)]
    ccy = "QAR"
    if cls in ("Trade Finance Settlement",) and random.random() < 0.75: ccy = random.choice(["USD"] * 4 + ["EUR"])
    elif cls in ("Intercompany Transfer", "Supplier Payment") and random.random() < 0.08: ccy = "USD"
    if cls == "Salary Payment": ch = ("Host-to-Host", "H2H")
    elif ccy != "QAR": ch = ("SWIFT", "SWF")
    else: ch = random.choices([c[:2] for c in CHANNELS[:4]], [c[2] for c in CHANNELS[:4]])[0]
    reference = ref(date)
    rows.append(make_row(r.c, r.p, cls, d, r["sub"], amt, date, ccy, reference, ch))
    # internal transfer between two QIB customers: bank books the mirror leg on the counterparty's statement too
    if E.loc[r.p, "is_cust"] and random.random() < 0.3:
        rows.append(make_row(r.p, r.c, cls, "C" if d == "D" else "D", r["sub"], amt, date, ccy, reference, ch))

# ---------------- Self transfers ----------------
# A QIB customer moving money between its own accounts: mostly to/from its accounts at other Qatar banks
# (liquidity sweeps, loan servicing elsewhere), a few between two of its own QIB accounts.
CLS_META["Own Account Transfer"] = (255, "ACOT", "FUNDS_TRANSFER")
own_accts = {}
for c in sorted(cust.index):
    if random.random() < 0.6:
        banks = random.sample(OTHER_BANKS, k=random.choice([1, 1, 2]))
        own_accts[c] = [(b, rand_digits(21)) for b in banks]
    if random.random() < 0.25:
        own_accts.setdefault(c, []).append((QIB, rand_digits(21)))
SELF_N = 320
self_custs = sorted(own_accts)
self_w = np.array([E.loc[c, "w"] for c in self_custs], float)
for c in np.random.choice(self_custs, size=SELF_N, p=self_w / self_w.sum()):
    bank, bban = random.choice(own_accts[c])
    d = "D" if random.random() < 0.6 else "C"
    amt = round(float(np.random.lognormal(np.log(1_500_000 * E.loc[c, "w"] / 4), 0.9)), -3)
    date = DAYS[np.random.choice(len(DAYS), p=DAY_W)]
    ch = random.choice([("Internet Banking", "OIB"), ("Host-to-Host", "H2H")])
    row = make_row(c, c, "Own Account Transfer", d, "Own account - " + bank, amt, date, "QAR", ref(date), ch)
    cp_iban = iban(BANKS[bank][1], bban)
    row.update({"CP_ACCOUNT_NUMBER": cp_iban[8:], "CP_BANK_CD": BANKS[bank][0], "CP_IBAN_NUMBER": cp_iban,
                "CP_PART_IBAN": cp_iban[4:], "MATCH_CIF_ID": E.loc[c, "cif"], "PROSPECT_ID": None,
                "TRANSACTION_CHANNEL": "INTERNAL_TRANSFER" if bank == QIB else "FUNDS_TRANSFER",
                "PURPOSE_DESC": random.choice(["Liquidity transfer", "Own account funding", "Sweep to own account", None])})
    rows.append(row)

df = pd.DataFrame(rows).sort_values(["BOOKING_DATE", "STMT_ENTRY_ID"]).reset_index(drop=True)
df["STMT_ENTRY_ID"] = [str(199360000000000 + i * 37 + random.randint(0, 30)) for i in range(len(df))]
print(len(df))
df.to_pickle(OUT + "df.pkl")
E.reset_index().to_pickle(OUT + "E.pkl")
