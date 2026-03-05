"""Every experiment's quoted numbers must still match the artefacts they came from.

Four of review 6's twelve findings were the same failure: a note stated a number, then the data underneath it changed.
`tools/check_claims.py` re-derives each annotated claim; this test makes it part of the suite.
"""
import subprocess, sys, os, glob, json
ROOT = os.path.join(os.path.dirname(__file__), "..")

def test_every_annotated_claim_still_holds():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_claims.py")], capture_output=True, text=True)
    assert r.returncode == 0, "an experiment note disagrees with its own artefacts:\n" + r.stdout + r.stderr

def test_claim_files_are_well_formed():
    for cf in glob.glob(os.path.join(ROOT, "experiments", "*", "claims.json")):
        for c in json.load(open(cf)):
            assert "claim" in c and "source" in c, (cf, c)
            assert ("note_regex" in c) or ("claimed" in c), (cf, c)
            assert ("path" in c) or ("count" in c), (cf, c)

def test_the_experiments_that_quote_numbers_have_claim_files():
    """A short list, grown deliberately: an experiment whose headline is a number should be checkable."""
    for exp in ("EXP_0015_fringe_measurement_negative", "EXP_0018_segmentation_is_the_bottleneck"):
        assert os.path.exists(os.path.join(ROOT, "experiments", exp, "claims.json")), exp
