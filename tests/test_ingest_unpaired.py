"""The unpaired after-wash channel must refuse anything whose post-wash state is not evidenced on the page."""
import sys, os, json, importlib.util
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools")); sys.path.insert(0, os.path.join(ROOT, "src"))
spec = importlib.util.spec_from_file_location("ingest_unpaired", os.path.join(ROOT, "tools", "ingest_unpaired.py"))
IU = importlib.util.module_from_spec(spec); spec.loader.exec_module(IU)

GOOD = {"page_url": "https://x/y", "image_url": "https://x/a.jpg", "license_or_terms": "copyright / all rights reserved",
        "state_evidence": "I threw them in the wash and the hem frayed beautifully.", "hem_finish": "frayed"}

def test_a_complete_record_is_accepted():
    assert IU.validate(GOOD) is None

def test_missing_or_empty_fields_are_refused():
    for k in IU.REQUIRED:
        assert IU.validate({**GOOD, k: ""}) == f"missing_{k}", k
        assert IU.validate({k2: v for k2, v in GOOD.items() if k2 != k}) == f"missing_{k}", k

def test_evidence_must_actually_mention_a_wash():
    assert IU.validate({**GOOD, "state_evidence": "The finished shorts look great with sneakers."}) == "state_evidence_does_not_mention_a_wash"
    assert IU.validate({**GOOD, "state_evidence": "washed"}) == "state_evidence_too_short"     # a label, not a quote
    assert IU.validate({**GOOD, "state_evidence": "Nach dem Waschen sind die Fransen perfekt."}) is None

def test_finished_hems_are_not_fringe_samples():
    for h in ("cuffed", "hemmed", "serged", None):
        assert IU.validate({**GOOD, "hem_finish": h}) != None

def test_image_url_must_be_http():
    assert IU.validate({**GOOD, "image_url": "file:///etc/passwd"}) == "image_url_not_http"
