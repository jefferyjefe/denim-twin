"""Review 6 — EXP_0016's numeric claims against experiments/EXP_0016_resolution_threshold/rows.json and the
control artefacts. Same contract as tests/test_exp0015_claims.py: written against the data, so it fails when the
note and the run disagree. Every test here is expected to FAIL.
"""
import json, os, re, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = os.path.join(ROOT, "experiments/EXP_0016_resolution_threshold")
NOTE = open(os.path.join(D, "NOTE.md")).read()
ROWS = [r for r in json.load(open(os.path.join(D, "rows.json"))) if r.get("status") == "ok"]
EXCL = {l.split()[0] for l in open(os.path.join(ROOT, "data/priors/exclude.txt")).read().splitlines()
        if l.strip() and not l.startswith("#")}


def test_excluded_pairs_are_not_in_the_resolution_experiment():
    """tools/experiment_resolution.py:41 skips a pair only when its NOTE.md first line says "rejected". It never
    reads data/priors/exclude.txt, which tools/fit_fringe.py:13 and tools/fringe_unpaired.py:15 both honour and
    which tests/test_exp0015_claims.py:44 enforces for the *previous* experiment.

    Two excluded pairs are in EXP_0016, and they are its two highest-resolution frayed subjects:
      f542c57cec — "before is a folded, text-overlaid graphic"; supplies the headline "9.0 px" row
                   (NOTE.md:26) and BOTH rows of the "> 1600 px | 2/2" detection band (NOTE.md:47).
      f9c0e56308 — "two overlapping shorts in the after photo": the mask covers TWO garments, which is exactly
                   the broken-mask failure the addendum's compactness gate was introduced to catch.

    observed: rows.json contains 12 measurements from these two excluded pairs, and dropping them moves the
              headline fit of NOTE.md:12-15 from
                  frayed 0.0048*waist + 2.16 (r 0.73, n 47)   ->   0.0063*waist + 1.01 (r 0.74, n 35)
              against an unchanged control fit 0.0039*waist + 1.05, i.e. "the floor scales too, at 80% of the
              signal's rate" (NOTE.md:15) becomes 62%, and the quoted separation of 0.0009 becomes 0.0024.
    expected: no measurement in the experiment comes from an excluded pair."""
    leaked = sorted({r["id"] for r in ROWS if r["id"].split(":")[-1] in EXCL})
    assert not leaked, f"{leaked} are in data/priors/exclude.txt but supply {sum(1 for r in ROWS if r['id'].split(':')[-1] in EXCL)} of {len(ROWS)} rows"


def test_the_headline_slope_ratio_survives_dropping_the_excluded_pairs():
    """NOTE.md:15 — "**The floor scales too**, at 80% of the signal's rate ... a separation of 0.0009 of waist
    width, which is far below the scatter" — is the whole argument for retiring depth on resolution grounds.

    observed: with the two excluded pairs removed the frayed slope is 0.0063 and the control slope 0.0039:
              the floor scales at 62% of the signal, and the separation is 0.0024 — 2.7x the quoted figure.
    expected: the conclusion does not depend on data the project has excluded."""
    def fit(sub):
        x = np.array([r["waist_px"] for r in sub], float); y = np.array([r["depth_px"] for r in sub], float)
        return np.polyfit(x, y, 1)[0]
    keep = [r for r in ROWS if r["id"].split(":")[-1] not in EXCL]
    fr = fit([r for r in keep if r["group"] == "frayed"]); ct = fit([r for r in keep if r["group"] == "control"])
    quoted = float(re.search(r"at (\d+)% of the signal", NOTE).group(1)) / 100 if re.search(r"at (\d+)% of the signal", NOTE) else 0.80
    assert abs(ct / fr - quoted) < 0.05, (
        f"note says the floor scales at {quoted:.0%} of the signal; without the excluded pairs it is "
        f"{ct / fr:.0%} (frayed slope {fr:.4f}, control slope {ct:.4f}, separation {fr - ct:.4f})")


def test_the_addendum_control_census_matches_the_runs():
    """The addendum publishes a high-resolution control census:

        | high-resolution finished hems (waist 994-1366 px) | 9 | 9 | **0** |

    Review 6 found the earlier version of this row ("0 false positives in 11 accepted control measurements") counted
    photos the runs never accepted. The deeper problem was that no script produced the artefact at all: the file it
    cited was left by an ad-hoc run and still recorded the contour-compactness gate review 6 removed, so it described
    code that no longer existed. `tools/measure_controls.py` now produces it, and this test holds the note to it."""
    C = json.load(open(os.path.join(ROOT, "reports/fringe_methods/controls_roughness.json")))
    m = re.search(r"finished hems \(waist [^|]*\) \| (\d+) \| (\d+) \| \*\*(\d+)\*\* \|", NOTE)
    assert m, "the addendum no longer publishes the high-resolution control census"
    n, measured, false_pos = (int(x) for x in m.groups())
    assert n == len(C), f"note says {n} control photos; the artefact holds {len(C)}"
    assert measured == sum(1 for r in C if r["ok"]), f"note says {measured} measured; artefact {sum(1 for r in C if r['ok'])}"
    assert false_pos == sum(1 for r in C if r.get("called_frayed")), "false-positive count does not match the artefact"
    assert all(r.get("segmentation") == "consensus" for r in C), "the table says consensus segmentation; the artefact does not"
    assert all(r.get("reason") is None for r in C), "the table says 'no gate'; the artefact records refusals"


def test_the_two_high_resolution_false_positives_have_the_roughness_the_note_quotes():
    """The addendum states: "Two of the nine initially read as frayed (**p90 4 and 8 px**)".

    observed: reports/fringe_methods/controls_highres.json — the pre-gate measurement of those nine photos —
              records rough_p90 4.0 for dbde5e4083 and 4.0 for 7b0a1ceaaf. There is no 8 px value anywhere in
              either control artefact.
    expected: the quoted values appear in the run they cite."""
    h = json.load(open(os.path.join(ROOT, "reports/fringe_methods/controls_highres.json")))
    fp = sorted(x["rough_p90"] for x in h if x["rough_p90"] > 0)
    m = re.search(r"initially read as frayed \(p90 ([0-9.]+) px each", NOTE)
    assert m, "the addendum no longer quotes the two false-positive roughness values"
    assert [float(m.group(1))] * len(fp) == fp, f"note quotes p90 {m.group(1)} each; the run recorded {fp}"


def test_the_contributor_ask_that_the_note_says_is_published_is_published():
    """NOTE.md:54-56 — "**The contributor ask becomes a number.** A whole-garment photo is useful for fray if the
    waistband spans >= ~800 px ... This is now stated in `CONTRIBUTING_PAIRS.md` and the issue form."

    observed: neither CONTRIBUTING_PAIRS.md nor .github/ISSUE_TEMPLATE/pair-submission.yml contains "800", or
              the word "waistband", or the word "resolution". The ask was never written down.
    expected: the requirement the note says is published is published."""
    missing = [p for p in ("CONTRIBUTING_PAIRS.md", ".github/ISSUE_TEMPLATE/pair-submission.yml")
               if "800" not in open(os.path.join(ROOT, p)).read()]
    assert not missing, f"NOTE.md:54-56 says the >=800 px waistband ask is stated in these files; it is not: {missing}"


import glob, hashlib
import pytest

_HAVE_SAM = os.path.exists(os.path.join(ROOT, "models", "sam_vit_b_01ec64.pth")) and __import__("importlib").util.find_spec("torch") is not None


@pytest.mark.needs("sam_checkpoint", "torch", "external_images")
def test_the_published_roughness_table_reproduces_with_the_shipped_metric():
    """NOTE.md:24-36 publishes a per-garment roughness table at native resolution, and rows.json is its record.
    Both were produced at commit 85d02a4. Commit d5debb6 then rewrote `hem_roughness` — adding the solid-column
    filter (hem_texture.py:60-63) and the compactness gate (hem_texture.py:77-80) — and neither the table nor
    rows.json was regenerated.

    Segmentation is deterministic here (segment_garment_coarse returns a bit-identical mask across runs and
    processes), so this is a pure code-vs-record comparison.

    observed: re-running the published subjects at scale 1.0 reproduces 9 of the 11 rows exactly and changes two,
              both quoted in the note:
                  web:eac3449d  NOTE.md:29 says 3.0 px   ->  shipped metric gives 2.2 px
                  web:b0576a16  NOTE.md:28 says 4.0 px   ->  shipped metric gives 5.0 px
              (Off the native row, the change also flips outcomes: pair:f9c0e56308 at scale 0.5 measured p90 3.0
              under the old code and is now REFUSED at compactness 3.35 — so the "frayed detected" column of the
              per-band table at NOTE.md:41-47 no longer holds either.)
    expected: the shipped metric reproduces the numbers the note publishes."""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import cv2
    from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse
    from denimtwin.canon.autolm import landmarks_from_mask
    from denimtwin.eval.hem_texture import hem_roughness
    want = {r["id"]: r["rough_p90_px"] for r in ROWS if r["scale"] == 1.0}
    recs = {hashlib.sha1(json.loads(l)["page_url"].encode()).hexdigest()[:10]: json.loads(l)
            for l in open(os.path.join(ROOT, "data/external/pairs.jsonl")) if l.strip()}
    paths = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "experiments/pairs/*/after_used.png"))):
        paths[f"pair:{os.path.basename(os.path.dirname(f))}"] = f
    web = os.path.join(ROOT, "data/priors/fringe_unpaired_web.json")
    if os.path.exists(web):
        for s in json.load(open(web))["samples"]:
            if s.get("file"): paths[f"web:{s['file'][:8]}"] = os.path.join(ROOT, "data/external/unpaired_images", s["file"])
    todo = {k: v for k, v in paths.items() if k in want and os.path.exists(v)}
    if len(todo) < len(want): pytest.skip(f"only {len(todo)} of {len(want)} source photos present")
    seg = SamSegmenter(); bad = {}
    for sid, p in sorted(todo.items()):
        m, sc, info = segment_garment_coarse(seg, cv2.imread(p))
        lm, conf = landmarks_from_mask(m)
        ww = abs(lm["waist_right"][0] - lm["waist_left"][0])
        got = hem_roughness(m, waist_px=ww)
        val = got["p90_px"] if got["ok"] else None
        if val is None or abs(val - want[sid]) > 0.05: bad[sid] = (want[sid], val, round(got["compactness"], 2))
    assert not bad, f"rows.json vs the shipped metric (recorded, now, compactness): {bad}"
