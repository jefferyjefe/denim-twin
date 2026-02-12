#!/usr/bin/env python3
"""Side-by-side evaluation interface + failure-case gallery (plan Phase 2 deliverables) as a static HTML page.
Reads experiments/pairs/*/ (before_used, pred, diff, after_used/real, NOTE.md, cmp_median/metrics.json) and
data/priors/exclude.txt. Images are embedded as base64 thumbnails so the page is self-contained (research use only)."""
import base64, glob, json, os, html
from pathlib import Path
import cv2
ROOT = Path(__file__).resolve().parents[1]; PAIRS = ROOT / "experiments/pairs"; OUT = PAIRS / "GALLERY.html"
EXCL = {}
for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines():
    if l.strip() and not l.startswith("#"): k, _, why = l.partition("#"); EXCL[k.strip()] = why.strip()
def thumb(p, h=260):
    im = cv2.imread(str(p)); 
    if im is None: return ""
    s = h / im.shape[0]; im = cv2.resize(im, None, fx=s, fy=s); ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return f'<img src="data:image/jpeg;base64,{base64.b64encode(buf).decode()}" style="height:{h}px">'
rows_ok, rows_fail = [], []
for d in sorted(PAIRS.glob("*/")):
    pid = d.name; note = (d / "NOTE.md").read_text() if (d / "NOTE.md").exists() else ""
    if not note: continue
    title = html.escape(note.splitlines()[0][:80])
    if pid in EXCL or "rejected" in note[:80] or not (d / "pred.png").exists():
        why = EXCL.get(pid) or (note.splitlines()[2] if len(note.splitlines()) > 2 else "rejected")
        rows_fail.append(f"<tr><td><b>{pid}</b></td><td>{thumb(d / 'before_used.png', 160) or thumb(d / 'cropped_before.png', 160)}</td><td>{thumb(d / 'after_used.png', 160)}</td><td>{html.escape(why)}</td></tr>"); continue
    m = {x["system"]: x for x in json.load(open(d / "cmp_median/metrics.json"))["rows"]} if (d / "cmp_median/metrics.json").exists() else {}
    p, c, n = m.get("prediction", {}), m.get("null:crop-only", {}), m.get("null:no-op", {})
    met = "".join(f"<tr><td>{k}</td><td>{p.get(k, float('nan')):.3f}</td><td>{c.get(k, float('nan')):.3f}</td><td>{n.get(k, float('nan')):.3f}</td></tr>" for k in ("sil_iou_vs_real", "hem_chamfer", "dE_edge_band_vs_real", "fringe_iou_vs_real"))
    flags = html.escape(next((l for l in note.splitlines() if l.startswith("flags:")), ""))
    rows_ok.append(f"""<h3>{pid} — {title}</h3><p style="color:#666">{flags}</p>
<div style="display:flex;gap:8px;flex-wrap:wrap"><div>before{thumb(d/'before_used.png')}</div><div>prediction{thumb(d/'pred.png')}</div><div>diff (§4.8){thumb(d/'diff.png')}</div><div>real after{thumb(d/'after_used.png')}</div><div>real registered{thumb(d/'real.png')}</div>
<table border=1 style="border-collapse:collapse;font-size:12px"><tr><th>metric</th><th>pred</th><th>crop-only</th><th>no-op</th></tr>{met}</table></div>""")
page = f"""<!doctype html><meta charset=utf-8><title>denim-twin — pair evaluation gallery</title>
<body style="font-family:system-ui;max-width:1400px;margin:auto"><h1>Pair evaluation (auto pipeline) — {len(rows_ok)} evaluated, {len(rows_fail)} rejected</h1>
<p>Research use only: source images are copyrighted tutorial photos and are not redistributed; this page is for internal evaluation.</p>
{''.join(rows_ok)}
<h2>Failure gallery (rejected inputs, with reason)</h2><table border=1 style="border-collapse:collapse"><tr><th>pair</th><th>before</th><th>after</th><th>reason</th></tr>{''.join(rows_fail)}</table></body>"""
OUT.write_text(page); print(OUT, f"{len(rows_ok)} ok / {len(rows_fail)} rejected", f"{OUT.stat().st_size/1e6:.1f} MB")
