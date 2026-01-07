#!/usr/bin/env python3
"""Click landmarks on a jeans photo. Usage: annotate_landmarks.py IMAGE [--out landmarks.json]

Keys: left-click = place current landmark, u = undo, s = save, q = quit.
Prompts follow denimtwin.canon.landmarks.LANDMARKS order. Records annotator + timestamp
so manual effort can be measured later (plan §4.2)."""
import argparse, json, os, sys, time, getpass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import cv2
from denimtwin.canon.landmarks import LANDMARKS

p = argparse.ArgumentParser()
p.add_argument("image"); p.add_argument("--out"); p.add_argument("--max-side", type=int, default=1400)
a = p.parse_args()
out_path = a.out or os.path.splitext(a.image)[0] + "_landmarks.json"
orig = cv2.imread(a.image); assert orig is not None, "unreadable image"
scale = min(1.0, a.max_side / max(orig.shape[:2]))
disp = cv2.resize(orig, None, fx=scale, fy=scale)
pts = {}; t0 = time.time()

def draw():
    im = disp.copy()
    for n, (x, y) in pts.items():
        cv2.circle(im, (int(x * scale), int(y * scale)), 5, (0, 255, 255), -1)
        cv2.putText(im, n, (int(x * scale) + 6, int(y * scale) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    nxt = next((n for n in LANDMARKS if n not in pts), None)
    msg = f"click: {nxt}" if nxt else "all placed — press s to save"
    cv2.putText(im, msg, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    cv2.imshow("landmarks", im)

def on_mouse(ev, x, y, flags, _):
    if ev == cv2.EVENT_LBUTTONDOWN:
        nxt = next((n for n in LANDMARKS if n not in pts), None)
        if nxt: pts[nxt] = (x / scale, y / scale); draw()

cv2.namedWindow("landmarks"); cv2.setMouseCallback("landmarks", on_mouse); draw()
while True:
    k = cv2.waitKey(50) & 0xFF
    if k == ord("u") and pts: pts.pop(list(pts)[-1]); draw()
    elif k == ord("s"):
        json.dump({"image": os.path.abspath(a.image), "landmarks": pts, "annotator": getpass.getuser(),
                   "seconds": round(time.time() - t0, 1), "source": "manual"}, open(out_path, "w"), indent=2)
        print("saved", out_path); break
    elif k == ord("q"): break
cv2.destroyAllWindows()
