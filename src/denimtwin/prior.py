"""Fringe-depth prior lookup (plan §4.7/§4.9). Leave-one-out and state-conditional by construction:
the excluded pair is removed from BOTH the paired rows and the unpaired after-wash samples."""
import numpy as np

def predict_depth_rel(prior, state, exclude=None, pairs_jsonl=None):
    """Return (depth_rel_mean, n_eff, sd) for `state` in {'after_cut','after_wash'} with `exclude` left out.
    `exclude` removes every id that shares a photograph with it, not just the id itself (see `aliases_for`)."""
    drop = aliases_for(exclude, pairs_jsonl) if (exclude and pairs_jsonl) else ({exclude} if exclude else set())
    rows = [x for x in prior.get("pairs", []) if x.get("pair") not in drop and x.get("kind") == state]
    pool = [x["depth_rel"] for x in rows]
    if state == "after_wash":
        pool += [s["depth_rel"] for s in prior.get("unpaired", {}).get("samples", []) if s.get("pair") not in drop and s.get("status", "ok") == "ok"]
    if not pool: return 0.0, 0, 0.0
    return float(np.mean(pool)), len(pool), (float(np.std(pool)) if len(pool) >= 2 else 0.0)


def aliases_for(exclude, pairs_jsonl):
    """Every pair id that shares a photograph with `exclude`.

    Leave-one-out by page id is not enough: two records can list the same image URL (the contributor TEST submission
    #1 re-used a real tutorial's after-wash photo, so `4c30342e20` was scored against a prior containing its own
    photograph — review 5, finding 4). Exclude by *image*, not by page."""
    import json, hashlib, collections
    if not exclude: return set()
    by_img = collections.defaultdict(set)
    try:
        lines = open(pairs_jsonl).read().splitlines()
    except OSError:
        return {exclude}
    for l in lines:
        if not l.strip(): continue
        r = json.loads(l); pid = hashlib.sha1(r["page_url"].encode()).hexdigest()[:10]
        for i in r.get("images", []):
            if i.get("url"): by_img[i["url"]].add(pid)
    out = {exclude}
    for pids in by_img.values():
        if exclude in pids: out |= pids
    return out
