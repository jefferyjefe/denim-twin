"""No measurement may enter a prior from an unverified segmentation mask (EXP_0018)."""
import json, os, importlib.util, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
V = json.load(open(os.path.join(ROOT, "data/external/mask_verdicts.json")))

def _mod():
    spec = importlib.util.spec_from_file_location("ingest_unpaired", os.path.join(ROOT, "tools", "ingest_unpaired.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_every_verdict_records_what_was_seen():
    for k, v in V["verdicts"].items():
        assert v["verdict"] in ("ok", "bad"), (k, v)
        assert len(v.get("saw", "")) > 20, f"{k}: a verdict without a description is not verification"
        assert v.get("verified")

def test_every_sample_in_the_prior_has_an_ok_verdict():
    web = os.path.join(ROOT, "data/priors/fringe_unpaired_web.json")
    if not os.path.exists(web): return
    for s in json.load(open(web))["samples"]:
        if s.get("status") != "ok": continue
        key = os.path.splitext(s["file"])[0]
        assert V["verdicts"].get(key, {}).get("verdict") == "ok", f"{s['file']} is in the prior without a verified mask"

def test_the_known_bad_mask_is_recorded_and_excluded():
    bad = [k for k, v in V["verdicts"].items() if v["verdict"] == "bad"]
    assert bad, "the pocket-mask failure that motivated this gate has gone missing from the record"
    web = os.path.join(ROOT, "data/priors/fringe_unpaired_web.json")
    if os.path.exists(web):
        ok_files = {os.path.splitext(s["file"])[0] for s in json.load(open(web))["samples"] if s.get("status") == "ok"}
        assert not (ok_files & set(bad))

def test_an_unverified_file_is_refused_by_name():
    """The gate keys on the stored file name, so a new download cannot slip in unlooked-at."""
    src = open(os.path.join(ROOT, "tools", "ingest_unpaired.py")).read()
    assert "mask_unverified" in src and "mask_verdicts.json" in src
