"""Review 4 — `run_pair.py --wash` mutates the masks the NULL BASELINES are built from.

tools/run_pair.py:159-163 replaces `bmask` and `removed` with the wash-shrunk masks:
    cut, bmask_w, removed_w, wash_changed = apply_wash(...)
    bmask, removed = bmask_w, removed_w; keep = bmask & ~removed
Those masks are then written to keep_mask.png / removed_mask.png (line 183) and handed to compare.py,
which builds `garment_before = keep | removed` and defines the nulls from them (tools/compare.py:32-36):
    "null:no-op": (before, garment_before), "null:crop-only": (np.where(keep, before, bg), keep)
So turning the wash on silently moves the reference the prediction is compared against. The A/B in
EXP_0013 Part B ("sil IoU vs real | -0.01 ... +0.01 | unchanged") therefore compares prediction deltas of
+-0.011 against a null that itself drifted by up to +0.017 under the same switch.
"""
import json, glob, os
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
BASE, WASH = os.path.join(ROOT, "experiments/pairs"), os.path.join(ROOT, "experiments/pairs_wash")
pytestmark = pytest.mark.skipif(not (os.path.isdir(BASE) and os.path.isdir(WASH)),
                                reason="needs the EXP_0013 batch artefacts")


def _rows(base):
    out = {}
    for f in sorted(glob.glob(f"{base}/*/cmp_median/metrics.json")):
        out[f.split(os.sep)[-3]] = {r["system"]: r for r in json.load(open(f))["rows"]}
    return out


def test_null_baselines_are_unchanged_by_the_wash_switch():
    """The nulls do not use the prediction, so `--wash median` must leave them byte-identical.
    observed (null:no-op sil_iou_vs_real, experiments/pairs_wash vs experiments/pairs):
      4c30342e20 0.2852 vs 0.2793 (+0.0059), e97924ad2d 0.5602 vs 0.5436 (+0.0166),
      f9c0e56308 0.4450 vs 0.4358 (+0.0092), 8d9f0df4ad 0.4285 vs 0.4207 (+0.0078)
    i.e. drift of the same size as the prediction deltas EXP_0013 Part B calls 'unchanged'."""
    w, n = _rows(WASH), _rows(BASE)
    common = sorted(set(w) & set(n))
    if len(common) < 5:
        import pytest
        pytest.skip("needs both pair batches on disk (experiments/pairs and experiments/pairs_wash); "
                    "scoring artefacts are gitignored, so this only runs locally after run_pairs_batch.py")
    bad = []
    for pid in common:
        for null in ("null:no-op", "null:crop-only"):
            a, b = w[pid][null]["sil_iou_vs_real"], n[pid][null]["sil_iou_vs_real"]
            if abs(a - b) > 1e-6: bad.append(f"{pid} {null}: {a:.4f} (wash) vs {b:.4f} (no wash), delta {a-b:+.4f}")
    assert not bad, "the wash switch moved the null baselines:\n  " + "\n  ".join(bad)
