"""Fringe-depth prior lookup (plan §4.7/§4.9). Leave-one-out and state-conditional by construction:
the excluded pair is removed from BOTH the paired rows and the unpaired after-wash samples."""
import numpy as np

def predict_depth_rel(prior, state, exclude=None):
    """Return (depth_rel_mean, n_eff, sd) for `state` in {'after_cut','after_wash'} with `exclude` left out."""
    rows = [x for x in prior.get("pairs", []) if x.get("pair") != exclude and x.get("kind") == state]
    pool = [x["depth_rel"] for x in rows]
    if state == "after_wash":
        pool += [s["depth_rel"] for s in prior.get("unpaired", {}).get("samples", []) if s.get("pair") != exclude and s.get("status", "ok") == "ok"]
    if not pool: return 0.0, 0, 0.0
    return float(np.mean(pool)), len(pool), (float(np.std(pool)) if len(pool) >= 2 else 0.0)
