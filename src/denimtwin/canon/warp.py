"""Image <-> canonical garment space via thin-plate-spline warp on landmarks.

**The two directions are separate TPS fits, and they are not inverses of each other.** OpenCV gives no inverse for a
thin-plate spline, so this class estimates one map each way from the same landmark correspondences. Both are exact at
those landmarks and neither is constrained anywhere else. EXP_0029 measured the consequence on the seven usable pairs:
the image -> canonical -> image round trip is sub-pixel at the landmarks, a median of **10.7 px** over the rest of the
garment and **835 px** at worst, and a *region* sent the same way returns with a median IoU of **0.638** with itself.
Every canonical quantity in this project — the cut line, `inseam_fraction`, the parametric template, the wash — is
expressed away from the landmarks and inherits that.

`exact=True` fixes it by iteration rather than by a second fit: the approximate map gives a starting point, and each
step corrects it using the forward map, which is the one that is actually defined. Six steps take the round-trip error
below a tenth of a pixel on every pair measured. It costs one forward evaluation per step, so it is off by default for
image warping (millions of points) and on for point mapping (hundreds).
"""
import numpy as np, cv2
from .landmarks import CANONICAL, LANDMARKS

class CanonicalMap:
    """Bidirectional TPS map between image pixels and a canonical WxH raster."""
    def __init__(self, image_landmarks, canon_size=(1000, 1500), exact=True, iters=6, tol=0.05,
                 drop_degenerate=True, min_sep_frac=0.01):
        self.W, self.H = canon_size
        self.exact, self.iters, self.tol = exact, iters, tol
        names = [n for n in LANDMARKS if n in image_landmarks]
        src = np.array([image_landmarks[n] for n in names], np.float32)
        dst = np.array([(CANONICAL[n][0] * self.W, CANONICAL[n][1] * self.H) for n in names], np.float32)
        # A thin-plate spline asked to pull two COINCIDENT source points apart has to turn space inside out, and that
        # is where this project's folds come from (EXP_0031). When a garment is photographed with its legs touching,
        # `landmarks_from_mask` puts hem_left_inner and hem_right_inner within a pixel or two of each other — and the
        # canonical template wants them 160 px apart. Measured on the two folding pairs: stretch ratios of 135x and
        # 106x for the inner hems and 101x and 80x for the inner knees, against 1.5x on a garment that does not fold.
        # Two points a pixel apart carry no information about how space should stretch between them, so the second is
        # dropped: it is a degenerate correspondence, not a measurement.
        self.dropped = []
        if drop_degenerate and len(src) > 3:
            span = float(np.linalg.norm(src.max(axis=0) - src.min(axis=0)))
            keep = []
            for i in range(len(src)):
                if any(np.linalg.norm(src[i] - src[j]) < min_sep_frac * span for j in keep):
                    self.dropped.append(names[i]); continue
                keep.append(i)
            if len(keep) >= 4 and len(keep) < len(src):
                src, dst = src[keep], dst[keep]
                names = [names[i] for i in keep]
            else:
                self.dropped = []
        m = [cv2.DMatch(i, i, 0) for i in range(len(names))]
        # NB: OpenCV TPS applyTransformation maps the *second* shape onto the first.
        self.to_canon = cv2.createThinPlateSplineShapeTransformer()
        self.to_canon.estimateTransformation(src[None], dst[None], m)   # image -> canon
        self.to_image = cv2.createThinPlateSplineShapeTransformer()
        self.to_image.estimateTransformation(dst[None], src[None], m)   # canon -> image
        self.names = names

    def image_to_canon(self, img, border=cv2.BORDER_CONSTANT, exact=None):
        return self._warp(img, lambda p: self._to_image_pts(p, exact), (self.W, self.H), border)

    def canon_to_image(self, canon_img, image_shape, border=cv2.BORDER_CONSTANT):
        """Canonical raster -> image. Sampling this direction asks the FORWARD map (image -> canonical) where each
        output pixel came from, so it needs no inverse and takes no `exact` switch — only `image_to_canon` does."""
        return self._warp(canon_img, self._to_canon_pts, (image_shape[1], image_shape[0]), border)

    def _to_canon_pts(self, pts):
        _, out = self.to_canon.applyTransformation(np.asarray(pts, np.float32)[None]); return out[0]

    def _to_image_pts(self, pts, exact=None):
        """Canonical -> image. With `exact`, refine the second TPS's answer against the forward map."""
        use = self.exact if exact is None else exact
        _, out = self.to_image.applyTransformation(np.asarray(pts, np.float32)[None])
        x = np.asarray(out[0], np.float32)
        if not use: return x
        y = np.asarray(pts, np.float32)
        res = lambda z: np.linalg.norm(np.asarray(self._to_canon_pts(z), np.float32) - y, axis=1)
        cur = res(x)
        for _ in range(self.iters):
            todo = cur > self.tol
            if not todo.any(): break
            y_hat = np.asarray(self._to_canon_pts(x), np.float32)
            r = y - y_hat
            # first-order correction: how far does the approximate inverse move for this residual?
            _, a = self.to_image.applyTransformation((y_hat + r)[None])
            _, b = self.to_image.applyTransformation(y_hat[None])
            step = np.asarray(a[0], np.float32) - np.asarray(b[0], np.float32)
            # Backtrack per point. Without this the iteration DIVERGES where the two fits disagree most — on two of
            # the seven pairs it ran to 9.5 million pixels, which is the correction being applied in a place where
            # the map it is correcting against is meaningless. A step that does not reduce the residual is not taken.
            improved = np.zeros(len(x), bool)
            for alpha in (1.0, 0.5, 0.25, 0.1, 0.03):
                cand = np.where((todo & ~improved)[:, None], x + alpha * step, x).astype(np.float32)
                rc = res(cand)
                better = (rc < cur) & todo & ~improved
                if better.any():
                    x = np.where(better[:, None], cand, x).astype(np.float32)
                    cur = np.where(better, rc, cur)
                    improved |= better
                if improved[todo].all(): break
            if not improved.any(): break
        return x

    @staticmethod
    def _warp(img, inverse_fn, out_size, border):
        """Warp by sampling: for each output pixel, ask the *inverse* map where it came from.
        Evaluated at every pixel centre (chunked) — exact, no grid/resize misalignment."""
        W, H = out_size
        gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        pts = np.stack([gx.ravel(), gy.ravel()], 1)
        out = np.empty_like(pts)
        step = 200_000
        for i in range(0, len(pts), step):
            out[i:i + step] = inverse_fn(pts[i:i + step])
        mx = out[:, 0].reshape(H, W); my = out[:, 1].reshape(H, W)
        return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=border)

    def fold_fraction(self, mask_or_points, h=2.0, samples=1500):
        """Fraction of the garment where the image -> canonical map FOLDS (turns space inside out).

        A thin-plate spline through landmarks is not guaranteed to be injective, and when it is not there is no
        inverse to find: the region on one side of the fold is mapped on top of the region on the other. EXP_0030
        measured this on the seven usable pairs — it folds over 0.0-3.1% of the garment on five of them and **40.1%
        and 37.2%** on the other two, which are exactly the two where a region does not survive the round trip
        (IoU 0.077 and 0.178 against 0.967-1.000 for the rest). Correcting the inverse cannot help there; the
        landmarks are wrong, and the honest response is to say so rather than to render a mangled cut.

        Sign of the Jacobian determinant, by finite differences, over up to `samples` points of the mask."""
        a = np.asarray(mask_or_points)
        if a.dtype == bool or (a.ndim == 2 and a.shape[1] != 2):
            ys, xs = np.nonzero(np.asarray(a, bool))
            if not len(xs): return 0.0
            idx = np.linspace(0, len(xs) - 1, min(samples, len(xs))).astype(int)
            P = np.stack([xs[idx], ys[idx]], 1).astype(np.float32)
        else:
            P = np.asarray(a, np.float32)
        f0 = np.asarray(self._to_canon_pts(P), np.float32)
        fx = np.asarray(self._to_canon_pts(P + np.array([h, 0], np.float32)), np.float32)
        fy = np.asarray(self._to_canon_pts(P + np.array([0, h], np.float32)), np.float32)
        jx = (fx - f0) / h; jy = (fy - f0) / h
        det = jx[:, 0] * jy[:, 1] - jx[:, 1] * jy[:, 0]
        return float((det <= 0).mean())

    def points_to_canon(self, pts):
        return self._to_canon_pts(pts)

    def points_to_image(self, pts, exact=None):
        return self._to_image_pts(pts, exact)
