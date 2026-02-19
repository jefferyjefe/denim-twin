"""Review 3: small-surface checks (coins.py, modification.py, template.py)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pytest
from denimtwin.util.coins import coin_key, COINS_MM
from denimtwin.modification import CutModification, WashProtocol

def test_coin_key_euro_sign_prefix_and_unreachable_table_entries():
    # coins.py:6-10 -- "€2" (sign before number, the common spelling) maps to nothing; aud_1 has no phrase at all;
    # a US "50 cent piece" (30.6 mm half dollar) is returned as eur_50c (24.25 mm): a 26% scale error.
    assert coin_key("€2 coin") == "eur_2"
    assert coin_key("australian 1 dollar") == "aud_1"
    assert coin_key("US 50 cent piece") != "eur_50c"

def test_modification_validate_accepts_out_of_range_parameters():
    # modification.py:33-38 -- validate() checks exactly-one-of but no ranges: inseam_fraction 2.0 (below the hem),
    # negative wash cycles and an EMPTY cut path all pass, and downstream cut2d would silently clip them.
    with pytest.raises(AssertionError): CutModification(inseam_fraction=2.0).validate()
    with pytest.raises(AssertionError): CutModification(inseam_fraction=0.5, wash=WashProtocol(cycles=-1)).validate()
    with pytest.raises(AssertionError): CutModification(cut_path_canonical=[]).validate()

def test_template_fit_score_is_not_an_iou():
    # template.py:56 -- fit() returns 1 - loss as the 'IoU', but loss = (1-IoU) + 0.5*gap_term + penalties, so the
    # reported number is not the silhouette IoU it is documented/used as (EXP_0010 tables).
    from denimtwin.canon import template as T
    from test_canon import synthetic_jeans
    img, mask, lm = synthetic_jeans(jitter=0)
    params, score, p = T.fit(mask, iters=150)
    r = T.render(p, *mask.shape); iou = (r & mask).sum() / (r | mask).sum()
    assert abs(score - iou) < 0.02, (score, iou)
