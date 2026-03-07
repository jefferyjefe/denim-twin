#!/usr/bin/env python3
"""Run run_pair.py on every 'usable' page in data/external/pairs_validation.jsonl.
Picks the first whole-garment 'before' and the first whole-garment 'after_wash' (else 'after_cut').
Writes experiments/pairs/<pageid>/ and a summary table experiments/pairs/SUMMARY.md."""
import json, hashlib, subprocess, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; IMG = ROOT / "data/external/pair_images"; OUT = ROOT / os.environ.get("PAIRS_OUT", "experiments/pairs"); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "src")); from denimtwin.util.coins import coin_key

RECS = [json.loads(l) for l in (ROOT / "data/external/pairs.jsonl").read_text().splitlines() if l.strip()]
rows = []
for line in (ROOT / "data/external/pairs_validation.jsonl").read_text().splitlines():
    v = json.loads(line)
    if v["status"] != "usable": continue
    pid = hashlib.sha1(v["page_url"].encode()).hexdigest()[:10]
    pick = lambda roles: next((t["file"] for t in v["images"] if t["role"] in roles and t.get("tag") == "whole_garment_flat"), None)
    before = pick(("before",)); after = pick(("after_wash",)) or pick(("after_cut",)); kind = "after_wash" if pick(("after_wash",)) else "after_cut"
    if not before or not after: continue
    # manual crops recorded in pairs.jsonl (fractional boxes) -> cropped copies
    rec = next((r for r in RECS if hashlib.sha1(r["page_url"].encode()).hexdigest()[:10] == pid), None)
    def cropped(fname, role):
        if not rec: return str(IMG / fname)
        h8 = os.path.splitext(fname)[0].rsplit("_", 1)[-1]
        im = next((i for i in rec["images"] if h8 == hashlib.sha1(i["url"].encode()).hexdigest()[:8] and i.get("crop")), None)
        if not im: return str(IMG / fname)
        import cv2; img = cv2.imread(str(IMG / fname)); h, w = img.shape[:2]; x0, y0, x1, y1 = im["crop"]
        out = OUT / pid / f"cropped_{role}.png"; out.parent.mkdir(parents=True, exist_ok=True); cv2.imwrite(str(out), img[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]); return str(out)
    before_p, after_p = cropped(before, "before"), cropped(after, kind)
    od = OUT / pid
    cropped = ",".join(k for k, p_ in (("before", before_p), ("after", after_p)) if "cropped_" in p_)
    mmpp = None
    if rec:
        h8 = os.path.splitext(before)[0].rsplit("_", 1)[-1]
        mmpp = next((i.get("mm_per_px") for i in rec["images"] if h8 == hashlib.sha1(i["url"].encode()).hexdigest()[:8] and i.get("mm_per_px")), None)
    coin = coin_key(rec.get("scale_detail", "")) if (rec and mmpp is None and str(rec.get("scale_ref", "")).startswith("coin")) else None   # detection happens inside run_pair with the garment masked
    cmd = [sys.executable, str(ROOT / "tools/run_pair.py"), "--before", before_p, "--after", after_p, "--out", str(od), "--state", kind] + (["--cropped", cropped] if cropped else []) + (["--mm-per-px", str(mmpp)] if mmpp else []) + (["--coin", coin] if coin else [])
    if os.environ.get("PAIRS_REFINE"): cmd += ["--refine-landmarks"]
    if os.environ.get("PAIRS_SEG"): cmd += ["--seg", os.environ["PAIRS_SEG"]]
    if os.environ.get("PAIRS_UPRIGHT"): cmd += ["--upright-deadband", os.environ["PAIRS_UPRIGHT"]]
    if os.environ.get("PAIRS_WASH"): cmd += ["--wash", os.environ["PAIRS_WASH"]]
    _hf = (rec or {}).get("hem_finish")
    if _hf in ("raw", "cuffed", "hemmed", "serged"): cmd += ["--edge-treatment", _hf]   # a cuffed hem must not be frayed
    if os.environ.get("PAIRS_USE_PRIOR") and (ROOT / "data/priors/fringe.json").exists(): cmd += ["--prior", str(ROOT / "data/priors/fringe.json"), "--exclude", pid]   # leave-one-out, state-conditional
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0
    metrics = None
    if ok and (od / "cmp_median/metrics.json").exists():
        m = json.load(open(od / "cmp_median/metrics.json"))["rows"]; metrics = {x["system"]: x for x in m}
    why = next((l for l in (r.stdout + r.stderr).splitlines() if l.startswith("REJECT") or "failed" in l), (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else "")
    rows.append((pid, v["title"][:40], kind, ok, metrics, why if not ok else ""))
    print(pid, v["title"][:40], kind, "OK" if ok else "FAIL")
md = "# Found-pair batch (auto pipeline)\n\n| page | title | after | status | sil IoU pred / crop / no-op | chamfer px pred / crop | edge ΔE pred / crop | fringe IoU pred / no-op |\n|---|---|---|---|---|---|---|---|\n"
for pid, t, k, ok, m, err in rows:
    if m: p, c, n = m["prediction"], m["null:crop-only"], m["null:no-op"]; md += f"| {pid} | {t} | {k} | ok | {p['sil_iou_vs_real']:.2f} / {c['sil_iou_vs_real']:.2f} / {n['sil_iou_vs_real']:.2f} | {p['hem_chamfer']:.0f} / {c['hem_chamfer']:.0f} | {p['dE_edge_band_vs_real']:.1f} / {c['dE_edge_band_vs_real']:.1f} | {p['fringe_iou_vs_real']:.2f} / {n['fringe_iou_vs_real']:.2f} |\n"
    else: md += f"| {pid} | {t} | {k} | FAIL: {err[:60]} | | | | |\n"
(OUT / "SUMMARY.md").write_text(md); print(md)
# Which code and which knobs produced this batch. Two batches are only comparable if these match: review 4's
# null-baseline test compares experiments/pairs against experiments/pairs_wash, and it fails — loudly, on an
# unrelated finding — whenever one of them was regenerated and the other was not.
import subprocess as _sp, hashlib as _hl
def _git(*a):
    try: return _sp.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True).stdout.strip()
    except Exception: return ""
KNOBS = ("PAIRS_REFINE", "PAIRS_SEG", "PAIRS_UPRIGHT", "PAIRS_WASH", "PAIRS_USE_PRIOR")
# A content hash of the code that actually produces a pair result. The commit id is too strict — an edit to an
# unrelated tool makes two batches look incomparable — and too loose, because uncommitted edits do not move it.
PIPELINE = sorted([str(q.relative_to(ROOT)) for q in (ROOT / "src/denimtwin").rglob("*.py")] +
                  ["tools/run_pair.py", "tools/compare.py", "tools/run_pairs_batch.py", "tools/null_baselines.py"])
_h = _hl.sha256()
for rel in PIPELINE:
    f = ROOT / rel
    _h.update(rel.encode()); _h.update(f.read_bytes() if f.exists() else b"")
(OUT / "provenance.json").write_text(json.dumps({
    "pipeline_sha256": _h.hexdigest()[:16],
    "pipeline_files": len(PIPELINE),
    "commit": _git("rev-parse", "HEAD"),
    "knobs": {k: os.environ.get(k) for k in KNOBS if os.environ.get(k)},
    "n_pairs": len(rows),
}, indent=1))
