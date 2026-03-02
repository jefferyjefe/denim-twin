"""Hem roughness (eval/hem_texture.py): must separate a jagged hem from a smooth one, and must not be fooled by
a curved-but-smooth hem, an angled hem, or image scale alone."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from denimtwin.eval.hem_texture import hem_roughness, hem_profile

def _mask(kind, W=800, H=600, edge=430, amp=6, seed=0, curve=0.0, tilt=0.0):
    """Garment block whose bottom edge is smooth, curved, tilted, or jagged."""
    rng = np.random.default_rng(seed)
    m = np.zeros((H, W), bool)
    for x in range(60, W - 60):
        t = (x - 60) / (W - 120)
        y = edge + curve * np.sin(np.pi * t) * 40 + tilt * (t - 0.5) * 60
        if kind == "frayed": y += rng.integers(-amp, amp + 1)
        m[100:int(round(y)), x] = True
    return m

def test_a_frayed_hem_is_rougher_than_a_smooth_one():
    r_smooth = hem_roughness(_mask("smooth"), waist_px=680)
    r_frayed = hem_roughness(_mask("frayed"), waist_px=680)
    assert r_smooth["ok"] and r_frayed["ok"]
    assert r_smooth["p90_px"] == 0.0, r_smooth
    assert r_frayed["p90_px"] >= 3.0, r_frayed
    assert r_frayed["mean_px"] > 5 * max(r_smooth["mean_px"], 1e-6)

def test_a_curved_or_tilted_hem_is_still_smooth():
    """A cuffed hem is not a straight line — the metric must follow the shape, not penalise it."""
    for kw in ({"curve": 1.0}, {"tilt": 1.0}, {"curve": 1.0, "tilt": 1.0}):
        r = hem_roughness(_mask("smooth", **kw), waist_px=680)
        assert r["p90_px"] <= 1.0, (kw, r)

def test_roughness_scales_with_the_image_but_zero_stays_zero():
    """The signal grows with resolution (a 6 px jag at 1x is 12 px at 2x) — but a smooth hem stays exactly 0,
    which is the asymmetry the fray discriminator relies on (EXP_0016)."""
    big_frayed = hem_roughness(_mask("frayed", W=1600, H=1200, edge=860, amp=12), waist_px=1360)
    small_frayed = hem_roughness(_mask("frayed", W=800, H=600, edge=430, amp=6), waist_px=680)
    assert big_frayed["p90_px"] > small_frayed["p90_px"]
    assert hem_roughness(_mask("smooth", W=1600, H=1200, edge=860), waist_px=1360)["p90_px"] == 0.0

def test_hem_profile_uses_the_hem_not_the_whole_outline():
    m = _mask("smooth")
    x, y = hem_profile(m)
    assert len(x) > 100 and y.min() > 300      # only the lower boundary region is returned

def test_too_few_columns_is_reported_not_guessed():
    m = np.zeros((200, 200), bool); m[50:100, 90:100] = True
    r = hem_roughness(m, waist_px=10)
    assert not r["ok"] and r["p90_px"] == 0.0
