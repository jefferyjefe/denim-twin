#!/usr/bin/env python3
"""Fetch recent arXiv candidates for the literature watcher (deterministic). Prints JSON list."""
import json, sys, urllib.request, urllib.parse, xml.etree.ElementTree as ET, datetime as dt
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / "src"))
from denimtwin.prereqs import require_network as _require_network
Q = ['garment reconstruction', 'sewing pattern reconstruction image', 'cloth simulation tearing OR cutting',
     'fabric fraying OR yarn rendering', 'identity preserving image editing diffusion garment', 'conformal prediction image regression']
_require_network("tools/arxiv_watch.py", "query the arXiv API")
ns = {"a": "http://www.w3.org/2005/Atom"}; out = []; since = (dt.datetime.utcnow() - dt.timedelta(days=int(sys.argv[1]) if len(sys.argv) > 1 else 8))
for q in Q:
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": f"all:{q}", "sortBy": "submittedDate", "sortOrder": "descending", "max_results": 15})
    root = ET.fromstring(urllib.request.urlopen(url, timeout=60).read())
    for e in root.findall("a:entry", ns):
        pub = dt.datetime.strptime(e.find("a:published", ns).text[:10], "%Y-%m-%d")
        if pub < since: continue
        out.append(dict(query=q, title=" ".join(e.find("a:title", ns).text.split()), url=e.find("a:id", ns).text,
                        published=pub.date().isoformat(), summary=" ".join(e.find("a:summary", ns).text.split())[:600]))
seen = set(); uniq = [o for o in out if not (o["url"] in seen or seen.add(o["url"]))]
print(json.dumps(uniq, indent=1))
