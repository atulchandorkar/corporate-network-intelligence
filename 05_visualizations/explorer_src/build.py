"""Embed the Neo4j exports into the explorer page.

    python build.py [processed_dir]

template.html -> ../../docs/index.html   (the GitHub Pages site: one self-contained HTML file)

Chart libraries are inlined when local copies exist (set CYTOSCAPE_JS / PLOTLY_JS to cytoscape.min.js 3.30.2 and
plotly.min.js 2.35.2), so the page works on networks that block CDNs; otherwise the page loads them from cdnjs.
"""
import os
import base64, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = sys.argv[1] if len(sys.argv) > 1 else str(HERE.parents[1] / '01_data' / 'processed') + '/'
ents = json.load(open(P + 'neo4j_entities.json')); flows = json.load(open(P + 'neo4j_flows.json')); banks = json.load(open(P + 'neo4j_bank_flows.json'))
ents = [{k: e[k] for k in ('id', 'name', 'type', 'industry', 'qib', 'bank', 'pr', 'bt', 'comm', 'gre')} for e in ents]
for f in flows: f['v'] = round(f['v']); f['m'] = str(f['m'])
banks = [{'from_bank': b['from_bank'], 'to_bank': b['to_bank'], 'm': str(b['m']), 'v': round(b['v'])} for b in banks]
data = json.dumps({'entities': ents, 'flows': flows, 'bank_flows': banks}, separators=(',', ':')).replace('</', '<\\/')
# bank logos, cropped from each bank's website header (bank_logos/logo_<key>.png)
BANK_KEYS = {'Qatar Islamic Bank': 'qib', 'Qatar National Bank': 'qnb', 'Dukhan Bank': 'dukhan', 'Commercial Bank of Qatar': 'cbq', 'Doha Bank': 'doha',
             'Standard Chartered Bank - Qatar': 'sc', 'Masraf Al Rayan': 'rayan', 'HSBC Bank Middle East - Qatar': 'hsbc', 'Ahli Bank': 'ahli', 'Qatar International Islamic Bank': 'qiib'}
logos = {b: 'data:image/png;base64,' + base64.b64encode((HERE / 'bank_logos' / f'logo_{k}.png').read_bytes()).decode() for b, k in BANK_KEYS.items()}
html = (HERE / 'template.html').read_text().replace('__DATA__', data).replace('__LOGOS__', json.dumps(logos))

BRAND = {'blue': '#0075B0', 'navy': '#00111A', 'orange': '#DF7A00'}
brand_css = f"""<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap">
<style>
:root {{ --brand-bar: {BRAND['blue']}; --accent: {BRAND['blue']}; --accent-soft: #e2f0f8; --ring: {BRAND['orange']}; --ink: {BRAND['navy']};
  --bg: #f4f7f9; --line: #dde5ea; --muted: #5c6b75; --gre: #00476b; --company: #5fa8d3; --out: {BRAND['orange']}; --in: #4f63d2; --onus: #7a5cc4;
  --font-display: "Open Sans", "Segoe UI", system-ui, sans-serif; --font-body: "Open Sans", "Segoe UI", system-ui, sans-serif; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --brand-bar: #0075B0; --accent: #4fb3e6; --accent-soft: #0d2a3a; --ring: #f29a2e;
  --ink: #e8f1f6; --bg: #0b1820; --panel: #11222c; --line: #24394a; --muted: #93a8b6; --gre: #4fb3e6; --company: #8cc6e8; --out: #f29a2e; --in: #8a9bf0; --onus: #a58cf0; }} }}
:root[data-theme="dark"] {{ --brand-bar: #0075B0; --accent: #4fb3e6; --accent-soft: #0d2a3a; --ring: #f29a2e;
  --ink: #e8f1f6; --bg: #0b1820; --panel: #11222c; --line: #24394a; --muted: #93a8b6; --gre: #4fb3e6; --company: #8cc6e8; --out: #f29a2e; --in: #8a9bf0; --onus: #a58cf0; }}
h1 {{ color: var(--ink); }}
#plainhead {{ display: none; }}
</style>"""
LIBS = {'cytoscape': os.environ.get('CYTOSCAPE_JS', ''), 'plotly': os.environ.get('PLOTLY_JS', '')}
def inline(h):
    for k, path in LIBS.items():
        if path and Path(path).exists():
            tag = next(l for l in h.splitlines() if l.startswith('<script src=') and k in l)
            h = h.replace(tag, '<script>' + Path(path).read_text().replace('\ufffd', '\\ufffd') + '</script>')
    return h
plain_bar = '''<div class="brandbar">
    <div class="bt"><strong>Corporate Network Intelligence</strong><span>Relationship manager view of QIB company payment networks <span class="badge">Synthetic data</span></span></div>
  </div>'''
shared = html.replace('<!--BRAND_CSS-->', brand_css).replace('<!--BRAND_BAR-->', plain_bar).replace('<title>Corporate Network Explorer</title>', '<title>Corporate Network Intelligence</title>')
wrap = lambda h: '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>[hidden]{display:none!important}body{margin:0}</style></head><body>' + h + '</body></html>'
out = HERE.parents[1] / 'docs' / 'index.html'
out.write_text(wrap(inline(shared)), encoding='utf-8')
print('wrote', out)
