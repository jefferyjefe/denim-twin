"""Hem roughness (eval/hem_texture.py): must separate a jagged hem from a smooth one, and must not be fooled by
a curved-but-smooth hem, an angled hem, or image scale alone."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from denimtwin.eval.hem_texture import hem_roughness, hem_profile

def _mask(kind, W=800, H=600, edge=430, amp=6, seed=0, curve=0.0, tilt=0.0):
    """Garment block whose bottom edge is smooth, curved, tilted, or frayed.

    The frayed edge is *spatially correlated* noise (a smoothed random field), not per-column jitter. That matters:
    SAM does not resolve individual threads, so on real photos a frayed hem's mask is a smooth outline with occasional
    notches — measured contour compactness 1.46-2.10 across 8 real frayed garments. Per-column jitter produces
    compactness ~8, which is not a garment mask at all and would be refused by the quality gate (correctly)."""
    rng = np.random.default_rng(seed)
    m = np.zeros((H, W), bool)
    noise = np.zeros(W)
    if kind == "frayed":
        raw = rng.normal(0, 1, W)
        kern = np.ones(9) / 9.0
        noise = np.convolve(raw, kern, mode="same")
        noise = noise / (np.abs(noise).max() + 1e-9) * amp
    for x in range(60, W - 60):
        t = (x - 60) / (W - 120)
        y = edge + curve * np.sin(np.pi * t) * 40 + tilt * (t - 0.5) * 60 + noise[x]
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

def test_a_broken_mask_reports_a_high_compactness_for_the_caller_to_see():
    """2 of 9 high-resolution FINISHED hems were called frayed because SAM's mask was speckled (EXP_0016 addendum).

    A compactness *gate* was the first response and was removed: review 6 showed compactness is a garment-shape
    statistic (2.33 shorts, 3.95 full-length jeans) that also rises with fray depth, so as a gate it refused the
    project's own subject and silently zeroed the deepest frays. Broken masks are now handled at source by consensus
    segmentation (EXP_0019) and human verification; compactness is still reported so a caller can see it."""
    from denimtwin.eval.hem_texture import mask_compactness
    import cv2
    m = _mask("smooth")
    rng = np.random.default_rng(3)
    # SAM's real failure on patterned/bleached denim: coarse blobs of the garment go missing, so the OUTER outline
    # wanders (interior speckle alone does not — the external contour ignores holes).
    field = cv2.GaussianBlur(rng.normal(0, 1, m.shape).astype(np.float32), (0, 0), 6.0)
    broken = m & (field > -0.02)
    assert mask_compactness(broken) > 3.0 > mask_compactness(m)
    r = hem_roughness(broken, waist_px=680)
    assert r["compactness"] > 3.0 and r["ok"], "compactness is reported, not enforced"
    r_gated = hem_roughness(broken, waist_px=680, max_compactness=3.0)
    assert not r_gated["ok"] and "compactness" in r_gated.get("reason", ""), r_gated

def test_a_clean_mask_reports_its_compactness_and_is_judged():
    r = hem_roughness(_mask("frayed"), waist_px=680)
    assert r["ok"] and 1.0 <= r["compactness"] <= 3.0 and r["p90_px"] > 0

def test_the_compactness_gate_is_off_by_default_because_it_refuses_jeans():
    """Review 6: an exact full-length jeans silhouette scores ~4-5, so a 3.0 gate refuses the project's subject."""
    from denimtwin.eval.hem_texture import mask_compactness
    tall = np.zeros((1400, 700), bool)
    tall[100:400, 180:520] = True                    # body
    tall[400:1300, 180:330] = True; tall[400:1300, 370:520] = True    # two long legs
    assert mask_compactness(tall) > 3.0
    assert hem_roughness(tall, waist_px=340)["ok"], "the default must not refuse a pair of jeans"
