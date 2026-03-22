import sys, glob, numpy as np, cv2
sys.path.insert(0, "/Users/jefferyhuang/denim-twin/src")
from denimtwin.canon import upright as U
for p in sorted(glob.glob("/Users/jefferyhuang/denim-twin/experiments/*/2691c1a8d0/*mask*.png")) + \
         sorted(glob.glob("/Users/jefferyhuang/denim-twin/experiments/*/2691c1a8d0/*/*mask*.png")):
    m = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    if m is None: continue
    m = m > 127
    if m.sum() < 100: continue
    a, e = U.tilt_angle(m)
    print(f"{a:8.2f} {e:6.3f}  {m.shape}  {p.replace('/Users/jefferyhuang/denim-twin/','')}")
