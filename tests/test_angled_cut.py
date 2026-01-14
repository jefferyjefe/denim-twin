import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from denimtwin.canon.cut2d import cut_mask_canon_angled, cut_mask_canon
def test_angled_reduces_to_flat_when_equal():
    a = cut_mask_canon_angled((100, 150), 0.3, 0.3); f = cut_mask_canon((100, 150), inseam_fraction=0.3)
    assert (a != f).mean() < 0.02
def test_outer_higher_when_outer_frac_smaller():
    m = cut_mask_canon_angled((100, 150), inner_frac=0.4, outer_frac=0.2)
    first = lambda x: np.nonzero(m[:, x])[0].min()
    assert first(20) < first(44) and first(79) < first(56)   # outer columns cut higher than inner columns
