"""Image <-> canonical garment space via thin-plate-spline warp on landmarks."""
import numpy as np, cv2
from .landmarks import CANONICAL, LANDMARKS

class CanonicalMap:
    """Bidirectional TPS map between image pixels and a canonical WxH raster."""
    def __init__(self, image_landmarks, canon_size=(1000, 1500)):
        self.W, self.H = canon_size
        names = [n for n in LANDMARKS if n in image_landmarks]
        src = np.array([image_landmarks[n] for n in names], np.float32)
        dst = np.array([(CANONICAL[n][0] * self.W, CANONICAL[n][1] * self.H) for n in names], np.float32)
        m = [cv2.DMatch(i, i, 0) for i in range(len(names))]
        # NB: OpenCV TPS applyTransformation maps the *second* shape onto the first.
        self.to_canon = cv2.createThinPlateSplineShapeTransformer()
        self.to_canon.estimateTransformation(src[None], dst[None], m)   # image -> canon
        self.to_image = cv2.createThinPlateSplineShapeTransformer()
        self.to_image.estimateTransformation(dst[None], src[None], m)   # canon -> image
        self.names = names

    def image_to_canon(self, img, border=cv2.BORDER_CONSTANT):
        return self._warp(img, self.to_image, (self.W, self.H), border)

    def canon_to_image(self, canon_img, image_shape, border=cv2.BORDER_CONSTANT):
        return self._warp(canon_img, self.to_canon, (image_shape[1], image_shape[0]), border)

    @staticmethod
    def _warp(img, tps_inverse, out_size, border):
        """Warp by sampling: for each output pixel, ask the *inverse* TPS where it came from.
        Evaluated at every pixel centre (chunked) — exact, no grid/resize misalignment."""
        W, H = out_size
        gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        pts = np.stack([gx.ravel(), gy.ravel()], 1)
        out = np.empty_like(pts)
        step = 200_000
        for i in range(0, len(pts), step):
            _, m = tps_inverse.applyTransformation(pts[i:i + step][None]); out[i:i + step] = m[0]
        mx = out[:, 0].reshape(H, W); my = out[:, 1].reshape(H, W)
        return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=border)

    def points_to_canon(self, pts):
        _, out = self.to_canon.applyTransformation(np.asarray(pts, np.float32)[None]); return out[0]

    def points_to_image(self, pts):
        _, out = self.to_image.applyTransformation(np.asarray(pts, np.float32)[None]); return out[0]
