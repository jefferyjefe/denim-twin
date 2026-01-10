#!/usr/bin/env python3
"""Run capture-quality checks on images. Usage: check_capture.py IMG [IMG...] [--board protocol/charuco_board.json]"""
import argparse, json, sys
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), "..", "src"))
from denimtwin.capture.board import load_board
from denimtwin.capture.quality import check_image

p = argparse.ArgumentParser()
p.add_argument("images", nargs="+")
p.add_argument("--board", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "protocol", "charuco_board.json"))
p.add_argument("--no-board", action="store_true")
p.add_argument("--json", action="store_true")
a = p.parse_args()
board = spec = None
if not a.no_board:
    board, spec = load_board(a.board)
bad = 0
for im in a.images:
    r = check_image(im, board, spec)
    bad += not r.ok
    if a.json: print(json.dumps(r.__dict__))
    else:
        status = "OK  " if r.ok else "FAIL"
        scale = f" {r.mm_per_px:.3f} mm/px" if r.mm_per_px else ""
        scale += " [cutout bg]" if r.cutout_background else ""
        print(f"{status} {im}  blur={r.blur_score:.0f} mean={r.mean_intensity:.0f} board={r.board_corners}{scale}"
              + ("" if r.ok else "  <- " + "; ".join(r.reasons)))
sys.exit(1 if bad else 0)
