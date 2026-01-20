"""Review 2: run_pair.py input handling. split_collage is extracted from the script (it runs argparse+SAM at import)."""
import sys, os, ast
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.hemfit import estimate_hems, cut_mask_from_lines
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
RP = os.path.join(os.path.dirname(__file__), "..", "tools", "run_pair.py")

def _split_collage():
    tree = ast.parse(open(RP).read()); fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "split_collage")
    ns = {"np": np, "cv2": cv2}; exec(compile(ast.Module([fn], []), "run_pair", "exec"), ns); return ns["split_collage"]

def test_split_collage_keeps_an_off_centre_single_garment():
    # run_pair.py:24-33 -- any uniform bright column band in the middle 35-65% is treated as a collage gutter and
    # the RIGHT part is discarded. A single wide photo with the garment right of centre loses the garment entirely.
    img, mask, lm = synthetic_jeans(jitter=0)
    canvas = np.full((900, 1400, 3), 235, np.uint8); canvas[:, 800:] = img
    out, note = _split_collage()(canvas)
    dark = (out.min(axis=2) < 100).mean()
    assert dark > 0.05, (out.shape, note)                       # observed: garment cropped out, note 'collage split'

def test_one_leg_hem_fit_is_flagged_not_silently_cut_on_one_leg():
    # run_pair.py:63 only requires ANY leg to have a line; cut_mask_from_lines then removes fabric on one leg and
    # keeps the other full-length; removed fraction 0.21 passes the 0.05-0.75 gate, so a half-cut pair is scored.
    img, mask, lm = synthetic_jeans(jitter=0); cm = CanonicalMap(lm)
    cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    legs = estimate_hems(keep, mask, lm); legs["right"] = None
    rem = cut_mask_from_lines(mask, lm, legs); rf = rem.sum() / mask.sum()
    gate_ok = 0.05 <= rf <= 0.75
    src = open(RP).read()
    assert not gate_ok or "all(" in src.split("hem fit failed")[0].splitlines()[-1], rf   # gate accepts, code uses any()
