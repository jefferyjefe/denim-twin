"""Review 3 (rewritten against denimtwin.prior after the fix): leave-one-out must exclude the pair from the unpaired pool too."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); ROOT = os.path.join(os.path.dirname(__file__), "..")
from denimtwin.prior import predict_depth_rel

def test_excluded_pair_leaks_through_the_unpaired_pool():
    pr = {"pairs": [{"pair": "A", "kind": "after_wash", "depth_rel": 0.10}, {"pair": "B", "kind": "after_wash", "depth_rel": 0.12}],
          "unpaired": {"samples": [{"pair": "A", "status": "ok", "depth_rel": 0.50}]}}
    rel, n, sd = predict_depth_rel(pr, "after_wash", exclude="A")
    assert abs(rel - 0.12) < 1e-9 and n == 1

def test_interval_sd_falls_back_to_pooled_sd_that_includes_the_excluded_pair():
    pr = {"pairs": [{"pair": "A", "kind": "after_wash", "depth_rel": 0.10}, {"pair": "B", "kind": "after_wash", "depth_rel": 0.12}, {"pair": "C", "kind": "after_wash", "depth_rel": 0.90}]}
    _, _, sd_wo_C = predict_depth_rel(pr, "after_wash", exclude="C"); _, _, sd_with = predict_depth_rel(pr, "after_wash", exclude=None)
    assert sd_wo_C < sd_with

def test_state_conditional():
    pr = {"pairs": [{"pair": "A", "kind": "after_cut", "depth_rel": 0.0}], "unpaired": {"samples": [{"pair": "Z", "status": "ok", "depth_rel": 0.3}]}}
    assert predict_depth_rel(pr, "after_cut")[0] == 0.0 and abs(predict_depth_rel(pr, "after_wash")[0] - 0.3) < 1e-9

def test_repo_prior_contains_the_same_pair_paired_and_unpaired():
    fj = json.load(open(os.path.join(ROOT, "data/priors/fringe.json"))); uj = json.load(open(os.path.join(ROOT, "data/priors/fringe_unpaired.json")))
    paired = {r["pair"] for r in fj["pairs"] if r["kind"] == "after_wash"}; unp = {s["pair"] for s in uj["samples"] if s["status"] == "ok"}
    assert not (paired & unp), paired & unp

def test_fringe_unpaired_ignores_the_prior_exclude_list():
    assert "exclude" in open(os.path.join(ROOT, "tools/fringe_unpaired.py")).read()
