"""ChArUco board detection and metric scale estimation."""
import json
from pathlib import Path
import cv2, numpy as np

def load_board(spec_path):
    s = json.loads(Path(spec_path).read_text())
    d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, s["dictionary"]))
    board = cv2.aruco.CharucoBoard((s["cols"], s["rows"]), s["square_mm"] / 1000,
                                   s["marker_mm"] / 1000, d)
    return board, s

def detect(gray, board):
    """Return (charuco_corners Nx2, charuco_ids N) or (None, None)."""
    det = cv2.aruco.CharucoDetector(board)
    corners, ids, _, _ = det.detectBoard(gray)
    if corners is None or ids is None or len(ids) < 4:
        return None, None
    return np.asarray(corners).reshape(-1, 2), np.asarray(ids).ravel()

def mm_per_pixel(corners, ids, spec):
    """Approximate scale from mean spacing of adjacent detected chessboard corners.
    Valid for near-overhead shots; use full pose for obliques."""
    cols = spec["cols"] - 1
    pts = {int(i): c for i, c in zip(np.asarray(ids).ravel(), np.asarray(corners).reshape(-1, 2))}
    dists = []
    for i, p in pts.items():
        r, c = divmod(i, cols)
        for j in (i + 1 if c + 1 < cols else None, i + cols):
            if j is not None and j in pts:
                dists.append(np.linalg.norm(p - pts[j]))
    return spec["square_mm"] / float(np.median(dists)) if dists else None
