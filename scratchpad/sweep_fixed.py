import sys, glob, numpy as np, cv2
sys.path.insert(0, "/Users/jefferyhuang/denim-twin/src")
from denimtwin.canon import upright as U
def rot_fixed(m, d):
    h, w = m.shape[:2]
    M = cv2.getRotationMatrix2D((w/2, h/2), -d, 1.0)
    return cv2.warpAffine(m.astype(np.uint8), M, (w, h)) > 0
for p in ["experiments/pairs/2691c1a8d0/bmask.png",
          "experiments/pairs_consensus/2691c1a8d0/bmask.png",
          "experiments/pairs/2691c1a8d0/before_native.png"]:
    m = cv2.imread("/Users/jefferyhuang/denim-twin/"+p, cv2.IMREAD_GRAYSCALE)
    if m is None: print("miss", p); continue
    m = m > 127
    print("==", p, m.shape, m.sum())
    for d in (0,14,16,18,20):
        mm = rot_fixed(m, d)
        a, e = U.tilt_angle(mm)
        img = np.zeros(mm.shape+(3,), np.uint8)
        _, m2, ap = U.upright(img, mm)
        ot,_ = U.tilt_angle(m2)
        print(f"  {d:>3}{a:>10.2f}{e:>7.2f}{ap:>9.2f}{ot:>10.2f}")
