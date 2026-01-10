#!/usr/bin/env python3
"""Harvest curator: tag downloaded harvest images as flat_lay / on_model / detail / junk using CLIP
zero-shot (open_clip, ViT-B/32) and write data/external/curated.jsonl. Falls back to a heuristic
(foreground fraction/aspect) if open_clip is unavailable."""
import json, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; IMG = ROOT / "data/external/images"; OUT = ROOT / "data/external/curated.jsonl"
LABELS = {"flat_lay": "a photo of a pair of jeans laid flat, no person", "on_model": "a photo of a person wearing jeans",
          "detail": "a close-up photo of denim fabric texture or a jeans hem or pocket", "junk": "a scanned page of a book, a drawing, a logo, or something that is not jeans"}
done = {json.loads(l)["file"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()
files = [f for f in sorted(IMG.glob("*")) if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and f.name not in done]
if not files: print("nothing new"); sys.exit(0)
try:
    import torch, open_clip
    from PIL import Image
    model, _, pre = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k"); tok = open_clip.get_tokenizer("ViT-B-32")
    with torch.no_grad():
        T = model.encode_text(tok(list(LABELS.values()))); T /= T.norm(dim=-1, keepdim=True)
    def tag(f):
        with torch.no_grad():
            im = pre(Image.open(f).convert("RGB")).unsqueeze(0); v = model.encode_image(im); v /= v.norm(dim=-1, keepdim=True)
            p = (100 * v @ T.T).softmax(-1)[0]
        i = int(p.argmax()); return list(LABELS)[i], float(p[i]), "clip"
except Exception as e:
    print("open_clip unavailable, heuristic fallback:", e)
    import cv2, numpy as np
    def tag(f):
        im = cv2.imread(str(f)); 
        if im is None: return "junk", 1.0, "heuristic"
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); h, w = g.shape
        bluish = (im[..., 0].astype(int) - im[..., 2].astype(int) > 20).mean()
        return ("flat_lay" if bluish > 0.2 and 0.5 < h / w < 2 else "junk"), 0.5, "heuristic"
with OUT.open("a") as o:
    n = 0
    for f in files:
        lab, conf, how = tag(f); o.write(json.dumps(dict(file=f.name, label=lab, confidence=round(conf, 3), method=how)) + "\n"); n += 1
print(f"tagged {n}")
