"""Review 6 — what `eval/hem_texture.hem_roughness` and its compactness gate actually measure.

Every test here is expected to FAIL against the code as committed. Each says, in its docstring, the file:line of the
claim it contradicts, what was observed, and what the claim requires. Nothing here is a proposed fix.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pytest
from denimtwin.eval.hem_texture import hem_roughness, mask_compactness, DEFAULTS


def _garment(W=900, H=1500, waist=520, leg=180, rise=0.42, top=60, bot=None, hem_noise=None):
    """A geometrically PERFECT flat-lay silhouette: waistband block + two straight legs, every edge exact,
    no segmentation error anywhere. `hem_noise[x]` lifts the hem in column x (a fray)."""
    bot = bot if bot is not None else H - 60
    m = np.zeros((H, W), bool)
    cx = W // 2
    yr = int(top + rise * (bot - top))
    m[top:yr, cx - waist // 2: cx + waist // 2] = True
    for x0 in (cx - waist // 2, cx + waist // 2 - leg):
        for x in range(x0, x0 + leg):
            lift = 0 if hem_noise is None else int(hem_noise[x])
            m[yr:bot - lift, x] = True
    return m


def test_the_compactness_gate_refuses_a_perfect_full_length_jeans_silhouette():
    """hem_texture.py:28 (max_compactness=3.0) and :77-80 refuse any mask whose contour compactness exceeds 3.0,
    on the stated ground that such an outline is "speckled or torn" (hem_texture.py:31-35).

    Compactness is perimeter^2/(4*pi*A): a pure SHAPE statistic. It is ~1.7 for a 3:1 rectangle, 3.22 for 8:1 and
    3.85 for 10:1 — i.e. it exceeds 3.0 for any sufficiently elongated silhouette, however clean the mask.
    The project's subject is "photos of ONE pair of jeans"; a pair of jeans is exactly that shape.

    observed: an exact, noise-free jeans silhouette (waist 520 px, two 180 px legs, no mask error of any kind)
              -> compactness 3.95, ok=False, reason "mask outline too ragged to judge (compactness 3.95 > 3.0)",
              and p90_px suppressed to 0.0. The two real "broken masks" the gate was built for scored 3.96 and
              4.05 (hem_texture.py:34) — indistinguishable from a perfect pair of jeans.
    expected: a perfect mask is judged, not refused; the gate must key on mask quality, not on garment aspect."""
    m = _garment()
    r = hem_roughness(m, waist_px=520)
    assert r["ok"], (f"a geometrically exact jeans silhouette is refused as a broken mask: "
                     f"compactness={r['compactness']:.2f} > {DEFAULTS['max_compactness']}, reason={r.get('reason')!r}")


def test_compactness_separates_shorts_from_jeans_not_good_masks_from_broken_ones():
    """hem_texture.py:31-35 claims compactness is "~1.5-2.1 for a clean garment silhouette ... and much higher for a
    speckled or torn segmentation". It is a function of leg length, not of mask quality.

    observed: identical, exact silhouettes differing ONLY in how long the legs are —
              shorts (rise 0.60) 2.33, jeans (rise 0.42) 3.95, skinny jeans (leg 120 px) 5.30.
              No mask error is present in any of them.
    expected: compactness of a perfect mask does not depend on the garment being long-legged."""
    got = {"shorts": mask_compactness(_garment(H=900, rise=0.60)),
           "jeans": mask_compactness(_garment()),
           "skinny": mask_compactness(_garment(leg=120))}
    # FIXED (review 6, finding 1): there is no gate any more. The evidence above is why — an exact silhouette's
    # compactness is a function of leg length, so no bound on it can mean "this mask is broken". Mask validity comes
    # from consensus segmentation and human verification instead. The spread is asserted so the reason stays on record.
    assert DEFAULTS["max_compactness"] is None, "the compactness gate is back; it refuses full-length jeans"
    assert got["jeans"] > 1.5 * got["shorts"], (
        "compactness no longer varies with leg length; if that is true the finding needs revisiting: "
        + ", ".join(f"{k}={v:.2f}" for k, v in got.items()))


def test_p90_zero_does_not_mean_finished_hem_it_means_fewer_than_ten_percent_of_columns_notched():
    """hem_texture.py:7-10 and EXP_0016/NOTE.md:20-21 read `p90 == 0` as "a finished hem ... deviates from its own
    local median by nothing at all", and EXP_0016 publishes "0 false positives on controls (0/14)" on that reading.

    p90 is the 90th percentile of an integer-valued residual, so it is exactly 0 for ANY hem where fewer than 10% of
    the measured columns deviate — no matter how deep those columns are cut. A sparse fray is therefore reported
    with a value byte-identical to a sewn hem.

    observed: 8 px deep notches placed on 0% / 5% / 8% / 12% of the hem columns of the same garment ->
              p90_px = 0.0 / 0.0 / 0.0 / 8.0. The 8%-frayed hem and the smooth hem both report p90_px == 0.0.
              (`rough_fraction`, which does separate them — 0.009 vs 0.075 — is computed at hem_texture.py:90 and
              used by nothing: compare.py:67-69 and EXP_0016 both read p90 only.)
    expected: a hem with 8 px notches is not reported identically to a hem with none."""
    W, waist, leg = 1000, 520, 180
    legs = list(range(W // 2 - waist // 2, W // 2 - waist // 2 + leg)) + \
           list(range(W // 2 + waist // 2 - leg, W // 2 + waist // 2))
    def notched(frac):
        rng = np.random.default_rng(1)
        n = np.zeros(W)
        k = int(frac * len(legs) / 6)            # notches 6 px wide, over `frac` of the hem columns
        for i in rng.choice(np.arange(len(legs) - 6), size=k, replace=False) if k else []:
            for j in range(6): n[legs[i + j]] = 8
        return _garment(W=W, H=900, rise=0.60, waist=waist, leg=leg, hem_noise=n)
    got = {f: hem_roughness(notched(f), waist_px=waist) for f in (0.0, 0.05, 0.08, 0.12)}
    p90 = {f: r["p90_px"] for f, r in got.items()}
    # STANDS as a limitation, now named and measured (EXP_0021). `p90 > 0` is exactly `rough_fraction > 0.10`, so the
    # blind spot is "a fray touching fewer than a tenth of the hem columns". It is not fixable by lowering the
    # percentile at this resolution: the nine real finished-hem controls themselves deviate on up to 7.3% of columns
    # (reports/fringe_methods/controls_roughness.json), so any statistic that fires below ~10% fires on them too.
    assert p90[0.08] == p90[0.0] == 0.0, "the blind spot moved; the documented detection limit needs recomputing"
    for f, r in got.items():
        assert r["reads_as_frayed"] == (r["rough_fraction"] > r["fray_threshold_on_rough_fraction"])
        assert r["reads_as_frayed"] == (r["p90_px"] > 0), f"p90 and rough_fraction disagree at coverage {f}"
    assert got[0.08]["rough_fraction"] > got[0.0]["rough_fraction"], (
        "the companion number no longer separates the sparse fray from the smooth hem, so the limitation is "
        f"unreportable: {[(f, r['rough_fraction']) for f, r in got.items()]}")
    doc = __import__("denimtwin.eval.hem_texture", fromlist=["x"]).__doc__
    assert "0.10" in doc and "detection limit" in doc, "the module no longer states its detection limit"


def test_the_compactness_gate_is_a_fray_depth_cutoff_the_deepest_frays_are_refused():
    """hem_texture.py:77-80 refuses a mask above compactness 3.0 as "broken"; EXP_0016/NOTE.md (addendum) calls the
    gate "the load-bearing part". A frayed hem has a longer outline than a smooth one by construction, so the gate
    is monotone in fray depth: past a certain depth every genuinely frayed hem is refused.

    observed: one exact shorts silhouette (waist 520 px), notches 5 px wide every 10 px, no mask error of any kind —
              fray  0 px -> compactness 2.33, ok=True,  p90 0.0
              fray  2 px -> compactness 2.47, ok=True,  p90 2.0
              fray  4 px -> compactness 2.68, ok=True,  p90 4.0
              fray  6 px -> compactness 2.90, ok=True,  p90 6.0
              fray  8 px -> compactness 3.13, ok=FALSE, p90 forced to 0.0
              fray 12 px -> compactness 3.61, ok=FALSE, p90 forced to 0.0
              fray 16 px -> compactness 4.13, ok=FALSE, p90 forced to 0.0
              For scale: the real frayed garments in EXP_0016 measure p90 1-9 px, so this cutoff sits inside the
              range of the signal the metric exists to detect. The same effect is visible on a real photo — pair
              f9c0e56308 (frayed) at 0.5 scale segments to compactness 3.35 and is refused, where the identical mask
              measured p90 = 3.0 under the pre-gate code.
    expected: deeper fray produces a larger reported roughness, not a refusal."""
    def notched(amp):
        n = np.zeros(1000)
        for i in range(0, 1000, 10): n[i:i + 5] = amp
        return _garment(W=1000, H=900, rise=0.60, waist=520, leg=180, top=60, bot=840, hem_noise=n)
    got = {amp: hem_roughness(notched(amp), waist_px=520) for amp in (0, 4, 8, 16)}
    refused = {a: round(r["compactness"], 2) for a, r in got.items() if not r["ok"]}
    assert not refused, (
        f"the gate refuses the deepest frays on a perfect silhouette (fray px -> compactness): {refused}; "
        f"reported p90 by fray depth: { {a: r['p90_px'] for a, r in got.items()} }")


def test_roughness_is_reported_in_raw_pixels_so_it_ranks_photo_size_not_fray():
    """compare.py:67-69 stores `hem_rough_p90_pred/real/err_px` in PIXELS, and EXP_0017/NOTE.md:10-14 averages
    `hem_rough_err_px` across 11 pairs whose photographs span 267-4680 px on the long side to declare
    "prediction 0.91 px vs crop-only 1.27 px".

    tests/test_hem_texture.py:43-49 states the scaling as intended behaviour ("a 6 px jag at 1x is 12 px at 2x").
    That makes the px error a function of how big the contributor's photo was, so a mean over pairs of different
    sizes is dominated by the largest photographs, not by which system models fray better.

    observed: the SAME garment and the SAME fray, rendered at 1x / 2x / 3x, give |pred-real| = 4.0 / 8.0 / 12.0 px.
              A 0.36 px "margin" between systems is smaller than the change caused by one contributor cropping
              their photo. `p90_rel` (hem_texture.py:92) exists and is not used anywhere.
    expected: the quantity aggregated across pairs is scale-free."""
    def pair(k):
        n = np.zeros(1000 * k)
        for i in range(0, 1000 * k, 20 * k):
            n[i:i + 10 * k] = 4 * k
        real = _garment(W=1000 * k, H=900 * k, rise=0.60, waist=520 * k, leg=180 * k, top=60 * k,
                        bot=840 * k, hem_noise=n)
        pred = _garment(W=1000 * k, H=900 * k, rise=0.60, waist=520 * k, leg=180 * k, top=60 * k, bot=840 * k)
        a = hem_roughness(pred, waist_px=520 * k); b = hem_roughness(real, waist_px=520 * k)
        return abs(a["p90_px"] - b["p90_px"])
    e1, e2 = pair(1), pair(2)
    # FIXED at the aggregation layer (review 6): the px value is scale-dependent BY DESIGN — it is a pixel
    # measurement — so the fix is that nothing aggregates it across photographs of different sizes any more.
    # tools/compare.py records hem_rough_rel_* (p90 / waist width) and EXP_0017 is recomputed on that.
    src = open(os.path.join(os.path.dirname(__file__), "..", "tools", "compare.py")).read()
    assert "hem_rough_rel_pred" in src and "hem_rough_rel_real" in src, \
        "compare.py no longer records a scale-free roughness"
    r = hem_roughness(_garment(W=1000, H=900, rise=0.60, waist=520, leg=180, top=60, bot=840), waist_px=520)
    assert "p90_rel" in r, "hem_roughness stopped returning a scale-free value"
    assert abs(e2 - e1) >= 0.5 * max(e1, 1e-9), (
        f"the px value has become scale-free, which would make this test's premise wrong: "
        f"|err| {e1} px at 1x, {e2} px at 2x")


@pytest.mark.xfail(reason="ACCEPTED LIMITATION (review 6, finding 5): hem roughness is a spatial-frequency statistic, "
                          "not a fray detector. A decorative edge that undulates faster than the 6%-of-waist window — "
                          "scallop, picot, lettuce, wavy overlock — reads as fray at 1-2 px. Stated in the module "
                          "docstring; no scalloped-hem photograph exists in the dataset to calibrate against, and "
                          "inventing a rule for one would be fitting on zero examples.", strict=True)
def test_a_smooth_decorative_scalloped_hem_is_not_reported_as_fray():
    """hem_texture.py:7-10 justifies roughness as an asymmetry between two classes: "A finished hem (cuffed, sewn,
    serged) is a smooth curve ... A frayed hem is jagged". The metric implements only "deviates from its own local
    median over a 6%-of-waist window", which is a statement about spatial FREQUENCY, not about fray. Any finished
    edge that undulates faster than the window — a scalloped or picot hem, a lettuce edge, a decorative zig-zag,
    a wavy overlocked edge — is reported as roughness in the same range as the real frayed garments.
    tests/test_hem_texture.py:37-41 only checks a single smooth curve over the whole garment, which is slower than
    the window and therefore passes.

    observed: an exact shorts silhouette (waist 520 px, window 31 px) with a perfectly smooth cosine scallop and no
              fray at all —
                  scallop period 40 px, amplitude  6 px -> p90 2.0 px, compactness 2.38, ok=True
                  scallop period 60 px, amplitude  8 px -> p90 1.0 px, compactness 2.37, ok=True
              The real frayed garments in EXP_0016 measure p90 1-9 px, and the compactness gate accepts both of
              these, so neither the metric nor the gate can tell a scalloped hem from a frayed one.
    expected: a smooth decorative edge reads as finished (p90 0), like the cuffed controls."""
    got = {}
    for period, amp in ((40, 6), (60, 8)):
        n = np.array([amp * 0.5 * (1 + np.cos(2 * np.pi * x / period)) for x in range(1000)])
        r = hem_roughness(_garment(W=1000, H=900, rise=0.60, waist=520, leg=180, top=60, bot=840, hem_noise=n),
                          waist_px=520)
        got[(period, amp)] = (r["p90_px"], round(r["compactness"], 2), r["ok"])
    assert all(v[0] == 0.0 for v in got.values()), (
        f"a smooth, unfrayed scalloped hem reports fray-range roughness (p90, compactness, ok): {got}")
