"""Leave-one-out must exclude by PHOTOGRAPH, not by page id (adopted from review 5, finding 4).

The original defect: the contributor TEST submission re-used a tutorial's after-wash image, so one photograph carried
two pair ids and `4c30342e20` was scored against a prior containing its own photo. That record has been deleted; these
tests keep the invariant enforced for whatever arrives next.
"""
import json, os, hashlib, collections
ROOT = os.path.join(os.path.dirname(__file__), "..")
import sys; sys.path.insert(0, os.path.join(ROOT, "src"))
from denimtwin.prior import aliases_for, predict_depth_rel

PAIRS = os.path.join(ROOT, "data/external/pairs.jsonl")
PID = lambda r: hashlib.sha1(r["page_url"].encode()).hexdigest()[:10]

def test_no_photograph_carries_two_pair_ids():
    urls = collections.defaultdict(set)
    for l in open(PAIRS):
        if not l.strip(): continue
        r = json.loads(l)
        for im in r.get("images", []):
            if im["role"] == "after_wash": urls[im["url"]].add(PID(r))
    shared = {u[-40:]: sorted(v) for u, v in urls.items() if len(v) > 1}
    assert not shared, shared

def test_aliases_for_returns_every_id_sharing_a_photograph(tmp_path):
    f = tmp_path / "pairs.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in [
        {"page_url": "https://a/x", "images": [{"url": "https://img/1.jpg", "role": "after_wash"}]},
        {"page_url": "https://b/y", "images": [{"url": "https://img/1.jpg", "role": "after_wash"}]},
        {"page_url": "https://c/z", "images": [{"url": "https://img/2.jpg", "role": "after_wash"}]},
    ]))
    a = hashlib.sha1(b"https://a/x").hexdigest()[:10]; b = hashlib.sha1(b"https://b/y").hexdigest()[:10]
    c = hashlib.sha1(b"https://c/z").hexdigest()[:10]
    assert aliases_for(a, str(f)) == {a, b}
    assert aliases_for(c, str(f)) == {c}

def test_predict_drops_every_alias_from_the_pool(tmp_path):
    f = tmp_path / "pairs.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in [
        {"page_url": "https://a/x", "images": [{"url": "https://img/1.jpg", "role": "after_wash"}]},
        {"page_url": "https://b/y", "images": [{"url": "https://img/1.jpg", "role": "after_wash"}]},
    ]))
    a = hashlib.sha1(b"https://a/x").hexdigest()[:10]; b = hashlib.sha1(b"https://b/y").hexdigest()[:10]
    prior = {"pairs": [{"pair": a, "kind": "after_wash", "depth_rel": 0.02},
                       {"pair": b, "kind": "after_wash", "depth_rel": 0.02},
                       {"pair": "other", "kind": "after_wash", "depth_rel": 0.01}]}
    _, n_with, _ = predict_depth_rel(prior, "after_wash", a)                    # id only
    _, n_alias, _ = predict_depth_rel(prior, "after_wash", a, str(f))           # id + everything sharing its photo
    assert n_with == 2 and n_alias == 1

def test_the_intervals_that_gate_5_scores_contain_no_duplicate_photograph():
    p = os.path.join(ROOT, "experiments/pairs_prior/intervals_all.jsonl")
    if not os.path.exists(p): return
    ids = [json.loads(l)["garment_id"] for l in open(p) if l.strip()]
    dupe = {i for i in ids if ids.count(i) > 1}
    assert not dupe, dupe
    for i in ids:
        al = aliases_for(i, PAIRS)
        assert not (al - {i}) & set(ids), f"{i} is scored alongside {sorted(al - {i})}, which share its photograph"
