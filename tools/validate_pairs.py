#!/usr/bin/env python3
"""Vision check for pair records: tag every downloaded pair image with CLIP zero-shot
(whole_garment_flat / worn / hem_closeup / tools_or_other) and flag records whose 'before' / 'after_*'
images are not whole-garment views. Writes data/external/pairs_validation.jsonl and prints a summary."""
import json, hashlib, os, sys, urllib.parse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; IMG = ROOT / "data/external/pair_images"; OUT = ROOT / "data/external/pairs_validation.jsonl"
LABELS = {"whole_garment_flat": "a photo of a whole pair of jeans or denim shorts laid flat or hanging, no person, the entire garment visible",
          "worn": "a photo of a person wearing jeans or denim shorts",
          "hem_closeup": "a close-up photo of a frayed denim hem or cut edge or fabric texture",
          "other": "a photo of scissors, a ruler, a store, a sign, a shelf, text, or something that is not a garment"}
import torch, open_clip
from PIL import Image
model, _, pre = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k"); tok = open_clip.get_tokenizer("ViT-B-32")
with torch.no_grad():
    T = model.encode_text(tok(list(LABELS.values()))); T /= T.norm(dim=-1, keepdim=True)
def tag(path):
    with torch.no_grad():
        v = model.encode_image(pre(Image.open(path).convert("RGB")).unsqueeze(0)); v /= v.norm(dim=-1, keepdim=True); p = (100 * v @ T.T).softmax(-1)[0]
    i = int(p.argmax()); return list(LABELS)[i], float(p[i])
recs = [json.loads(l) for l in (ROOT / "data/external/pairs.jsonl").read_text().splitlines() if l.strip()]
usable = 0
with OUT.open("w") as f:
    for r in recs:
        pid = hashlib.sha1(r["page_url"].encode()).hexdigest()[:10]; tags = []
        for im in r["images"]:
            p = IMG / f"{pid}_{im['role']}_{hashlib.sha1(im['url'].encode()).hexdigest()[:8]}{os.path.splitext(urllib.parse.urlparse(im['url']).path)[1] or '.jpg'}"
            if not p.exists(): tags.append({"role": im["role"], "tag": "missing"}); continue
            t, c = tag(p); tags.append({"role": im["role"], "tag": t, "conf": round(c, 2), "file": p.name})
        ok_before = any(t["role"] == "before" and t["tag"] == "whole_garment_flat" for t in tags)
        ok_after = any(t["role"].startswith("after") and t["tag"] == "whole_garment_flat" for t in tags)
        status = "usable" if ok_before and ok_after else ("partial" if ok_before or ok_after else "unusable")
        usable += status == "usable"
        f.write(json.dumps({"page_url": r["page_url"], "title": r["title"], "status": status, "images": tags}) + "\n")
        print(f"{status:8s} {r['title'][:45]:45s} " + " ".join(f"{t['role']}={t['tag']}" for t in tags if t["role"] in ("before", "after_cut", "after_wash")))
print(f"\n{usable}/{len(recs)} pages usable (whole-garment before AND after)")
