#!/usr/bin/env python3
"""Build a blinded judging set: for each experiments/*/ with orig.png + pred.png (+ real.png),
copy to reports/judge/<hash>/{A,B}.png with random A/B assignment and a hidden key. Agent judges; key unblinds."""
import json, hashlib, random, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; out = ROOT / "reports/judge"; out.mkdir(parents=True, exist_ok=True)
key = {}; random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
for d in sorted(ROOT.glob("experiments/*")):
    if not (d / "pred.png").exists() or not (d / "orig.png").exists(): continue
    h = hashlib.sha1(d.name.encode()).hexdigest()[:8]; dd = out / h; dd.mkdir(exist_ok=True)
    shutil.copy(d / "orig.png", dd / "original.png")
    cands = [("prediction", d / "pred.png")] + ([("real", d / "real.png")] if (d / "real.png").exists() else [])
    random.shuffle(cands)
    for label, (kind, p) in zip("AB", cands): shutil.copy(p, dd / f"{label}.png"); key.setdefault(h, {})[label] = kind
(out / "KEY.json").write_text(json.dumps(key, indent=1)); print(f"{len(key)} pairs ->", out)
