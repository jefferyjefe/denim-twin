import sys, numpy as np, cv2
sys.path.insert(0, "/Users/jefferyhuang/denim-twin/src")
from denimtwin.canon import upright as U
def rot_exp(m, d):
    h, w = m.shape[:2]
    M = cv2.getRotationMatrix2D((w/2, h/2), d, 1.0)
    cos, sin = abs(M[0,0]), abs(M[0,1])
    nw, nh = int(h*sin+w*cos), int(h*cos+w*sin)
    M[0,2]+=nw/2-w/2; M[1,2]+=nh/2-h/2
    return cv2.warpAffine(m.astype(np.uint8), M, (nw,nh))>0
def rot_fix(m, d):
    h, w = m.shape[:2]
    M = cv2.getRotationMatrix2D((w/2, h/2), d, 1.0)
    return cv2.warpAffine(m.astype(np.uint8), M, (w,h))>0
m = cv2.imread("/Users/jefferyhuang/denim-twin/experiments/pairs/2691c1a8d0/bmask.png", cv2.IMREAD_GRAYSCALE)>127
for name, f in (("expand", rot_exp), ("fixed", rot_fix)):
    print("==", name)
    for d in range(10, 27, 2):
        mm = f(m, d); a,e = U.tilt_angle(mm)
        _, m2, ap = U.upright(np.zeros(mm.shape+(3,),np.uint8), mm)
        ot,_ = U.tilt_angle(m2)
        print(f"  {d:>3}{a:>10.2f}{e:>7.3f}{ap:>9.2f}{ot:>10.2f}")
