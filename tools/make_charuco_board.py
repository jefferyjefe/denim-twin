#!/usr/bin/env python3
"""Generate a printable ChArUco calibration board (PNG at 300 DPI + spec JSON).

Default: 8x11 squares, 25 mm squares, 18 mm markers, DICT_5X5_100 -> fits
US Letter when printed at 100% scale. Verify with a ruler after printing.
"""
import argparse, json
from pathlib import Path
import cv2, numpy as np

p = argparse.ArgumentParser()
p.add_argument("--cols", type=int, default=8)
p.add_argument("--rows", type=int, default=11)
p.add_argument("--square-mm", type=float, default=25.0)
p.add_argument("--marker-mm", type=float, default=18.0)
p.add_argument("--dpi", type=int, default=300)
p.add_argument("--out", default="protocol/charuco_board")
a = p.parse_args()

DICT = cv2.aruco.DICT_5X5_100
board = cv2.aruco.CharucoBoard((a.cols, a.rows), a.square_mm / 1000, a.marker_mm / 1000,
                               cv2.aruco.getPredefinedDictionary(DICT))
px = lambda mm: int(round(mm / 25.4 * a.dpi))
img = board.generateImage((px(a.cols * a.square_mm), px(a.rows * a.square_mm)), marginSize=0)
margin = px(10)
img = cv2.copyMakeBorder(img, margin, margin, margin, margin, cv2.BORDER_CONSTANT, value=255)
cv2.imwrite(a.out + ".png", img)
spec = dict(cols=a.cols, rows=a.rows, square_mm=a.square_mm, marker_mm=a.marker_mm,
            dictionary="DICT_5X5_100", dpi=a.dpi,
            printed_size_mm=[a.cols * a.square_mm + 20, a.rows * a.square_mm + 20])
Path(a.out + ".json").write_text(json.dumps(spec, indent=2) + "\n")
print(f"wrote {a.out}.png ({img.shape[1]}x{img.shape[0]} px) and {a.out}.json")
print("Print at 100% scale, then measure one square with a ruler and confirm", a.square_mm, "mm.")
