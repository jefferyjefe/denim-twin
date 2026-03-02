"""Every numeric claim in EXP_0015's method-comparison section must match the artefacts it cites.

Adopted from review 5, finding 9 (which found six wrong figures). Written against the *data*, parsing the note, so it
keeps working when the numbers legitimately change — it fails when the note and the run disagree.
"""
import json, os, re
ROOT = os.path.join(os.path.dirname(__file__), "..")
NOTE = os.path.join(ROOT, "experiments/EXP_0015_fringe_measurement_negative/NOTE.md")
METHODS = os.path.join(ROOT, "reports/fringe_methods/methods.json")

def _rows():
    d = [r for r in json.load(open(METHODS)) if r.get("status") == "ok"]
    return [r for r in d if r["id"].startswith("web")], [r for r in d if r["id"].startswith("pair")]

def test_the_photo_census_matches_the_run():
    web, pair = _rows()
    m = re.search(r"\*\*(\d+) harvested unpaired \+ (\d+)\s*\n?paired\*\*", open(NOTE).read())
    assert m, "the note no longer states a census in the expected form"
    assert (int(m.group(1)), int(m.group(2))) == (len(web), len(pair)), (m.groups(), len(web), len(pair))

def test_the_quoted_ranges_match_the_run():
    web, pair = _rows()
    txt = open(NOTE).read()
    row = re.search(r"\| harvested unpaired \(\d+ photos[^|]*\| ([\d.]+)–([\d.]+) \| ([\d.]+)–([\d.]+) \|", txt)
    assert row, "the harvested row is missing or reformatted"
    sam_lo, sam_hi, dir_lo, dir_hi = (float(x) for x in row.groups())
    got_sam = [r["sam_rel"] for r in web if r["sam_rel"] is not None]
    got_dir = [r["direct_rel"] for r in web if r["direct_rel"] is not None]
    assert abs(min(got_sam) - sam_lo) < 0.002 and abs(max(got_sam) - sam_hi) < 0.002, (sam_lo, sam_hi, min(got_sam), max(got_sam))
    assert abs(min(got_dir) - dir_lo) < 0.0005 and abs(max(got_dir) - dir_hi) < 0.0005, (dir_lo, dir_hi, min(got_dir), max(got_dir))

def test_the_web_channel_yield_matches_the_file():
    w = json.load(open(os.path.join(ROOT, "data/priors/fringe_unpaired_web.json")))
    m = re.search(r"\*\*(\d+) of (\d+) candidates measure\*\*", open(NOTE).read())
    assert m, "the note no longer states the web-channel yield"
    assert (int(m.group(1)), int(m.group(2))) == (w["n"], w["candidates"]), (m.groups(), w["n"], w["candidates"])

def test_the_prior_sample_count_matches_the_prior():
    p = json.load(open(os.path.join(ROOT, "data/priors/fringe.json")))
    m = re.search(r"\| after-wash samples in the prior \| \d+ \| \*\*(\d+)\*\*", open(NOTE).read())
    assert m, "the note no longer states the after-wash sample count"
    assert int(m.group(1)) == p["n_after_wash_combined"], (m.group(1), p["n_after_wash_combined"])

def test_excluded_pairs_are_not_in_the_method_comparison():
    ex = {l.split()[0] for l in open(os.path.join(ROOT, "data/priors/exclude.txt")).read().splitlines()
          if l.strip() and not l.startswith("#")}
    _, pair = _rows()
    leaked = [r["id"] for r in pair if r["id"].split(":")[1] in ex]
    assert not leaked, leaked
