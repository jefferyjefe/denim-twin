import sys, numpy as np, cv2
sys.path.insert(0, "/Users/jefferyhuang/denim-twin/src")
from denimtwin.canon import upright as U

base = "/Users/jefferyhuang/denim-twin/experiments/pairs/2691c1a8d0/"
m0 = cv2.imread(base + "bmask.png", cv2.IMREAD_GRAYSCALE) > 127
img0 = cv2.imread(base + "before_used.png")
if img0 is None or img0.shape[:2] != m0.shape:
    img0 = np.zeros(m0.shape + (3,), np.uint8)
print("mask", m0.shape, "area", m0.sum(), "img", None if img0 is None else img0.shape)
a0, e0 = U.tilt_angle(m0)
print(f"base tilt {a0:.2f} elong {e0:.3f} maxcorr {U.max_correctable_tilt(e0)}")

def rot(img, m, d):
    h, w = m.shape[:2]
    M = cv2.getRotationMatrix2D((w/2, h/2), -d, 1.0)
    cos, sin = abs(M[0,0]), abs(M[0,1])
    nw, nh = int(h*sin + w*cos), int(h*cos + w*sin)
    M[0,2] += nw/2 - w/2; M[1,2] += nh/2 - h/2
    return (cv2.warpAffine(img, M, (nw,nh)),
            cv2.warpAffine(m.astype(np.uint8), M, (nw,nh)) > 0)

print(f"{'imposed':>8}{'estimate':>10}{'elong':>7}{'applied':>9}{'out_tilt':>10}")
for d in range(0, 31, 2):
    im, mm = rot(img0, m0, d)
    ang, el = U.tilt_angle(mm)
    i2, m2, applied = U.upright(im, mm)
    ot, _ = U.tilt_angle(m2)
    print(f"{d:>8}{ang:>10.2f}{el:>7.2f}{applied:>9.2f}{ot:>10.2f}")
