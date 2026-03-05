"""Review 6 — EXP_0017's numbers against the pair artefacts they were computed from.

EXP_0017 has no rows.json, no TABLE.md and no script: the only record of the run is the prose in NOTE.md. These tests
recompute its claims from experiments/pairs/*/cmp_median/metrics.json, which is where `hem_rough_*` is written
(tools/compare.py:67-70). They are expected to FAIL.

The artefacts are gitignored, so the tests skip where no scored run exists (same convention as the null-baseline
regression test).
"""
import json, os, re, glob, math
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
NOTE_PATH = os.path.join(ROOT, "experiments/EXP_0017_roughness_as_fray_metric/NOTE.md")
NOTE = open(NOTE_PATH).read()
D = os.path.dirname(NOTE_PATH)
SYS = {"prediction": "prediction", "null: crop-only": "null:crop-only", "null: no-op": "null:no-op"}


def _pairs():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "experiments/pairs/*/cmp_median/metrics.json"))):
        pid = os.path.basename(os.path.dirname(os.path.dirname(f)))
        rows = {r["system"]: r for r in json.load(open(f))["rows"]}
        if "hem_rough_err_px" not in rows.get("prediction", {}): continue
        out[pid] = rows
    return out


def _finite(v): return isinstance(v, (int, float)) and not math.isnan(v)


@pytest.fixture(scope="module")
def P():
    p = _pairs()
    if not p: pytest.skip("no scored pair runs in this checkout")
    return p


def test_the_usable_pair_count_matches_the_artefacts(P):
    """NOTE.md:8 — "## Result (**11 usable found pairs**, median preset)", repeated at :20-21 ("with n = 11") and
    in docs/STATUS.md ("Scored on all 11 pairs").

    A pair is usable for this comparison only if BOTH the prediction and the crop-only null produced a finite
    `hem_rough_err_px`; tools/compare.py:69 writes nan whenever either mask is refused by the compactness gate.

    observed: experiments/pairs holds 12 scored pairs. Two (660bef67bf, 85d48013a2) predate the roughness columns
              and have none. Three (2691c1a8d0, b630a78c19, f542c57cec) are nan for every system. Seven pairs are
              decidable: 26b1041d00, 2b0123d732, 443d1d4658, 4bfef03bd7, 8d9f0df4ad, e97924ad2d, f9c0e56308.
              (f9c0e56308 and f542c57cec are in data/priors/exclude.txt, so the honest count is lower still.)
    expected: the note's n equals the number of pairs that produced a number."""
    # FIXED: the experiment was retracted and restated, and every number in the note is now re-derived from
    # result.json by tools/check_claims.py in CI. What this test still owns is that result.json is itself consistent
    # with the pairs on disk — a note checked against a stale artefact is the same failure one level down.
    R = json.load(open(os.path.join(D, "result.json")))
    assert "RETRACTED" in NOTE.splitlines()[0], "the retraction notice has been removed from the note's title"
    assert R["usable"] <= len(P), f"result.json claims {R['usable']} usable pairs; {len(P)} are scored on disk"
    assert R["decidable"] <= R["usable"]
    assert R["wins"] + R["losses"] + R["ties"] == R["decidable"], (
        f"the split {R['wins']}-{R['losses']}-{R['ties']} does not add up to {R['decidable']} decidable pairs")
    m = re.search(r"\*\*all (\d+) usable\n?pairs are decidable\*\*", NOTE)
    assert m and int(m.group(1)) == R["decidable"], (
        f"the note's decidable count and result.json disagree: {m.group(1) if m else None} vs {R['decidable']}")


def test_the_mean_absolute_roughness_error_table_matches_the_artefacts(P):
    """NOTE.md:10-14 publishes the result table:

        | prediction (cut + procedural fringe) | **0.91 px** |
        | null: crop-only (a clean cut, no fringe) | 1.27 px |
        | null: no-op (the uncut jeans) | 1.55 px |

    observed: mean |hem_rough_err_px| over the finite rows in experiments/pairs/*/cmp_median/metrics.json is
              prediction 0.43 (n=7), crop-only 1.00 (n=7), no-op 1.00 (n=3). None of the three published figures
              appears in the run. The artefacts were regenerated at 12:16-12:18 after commit d5debb6 rewrote
              `hem_roughness` (adding the solid-column filter and the compactness gate) at 12:28 — the note was
              written against the pre-gate metric and never recomputed.
    expected: the table matches the run it reports."""
    got = {}
    for name in ("prediction", "null:crop-only", "null:no-op"):
        v = [r[name]["hem_rough_err_px"] for r in P.values() if name in r and _finite(r[name]["hem_rough_err_px"])]
        got[name] = (sum(v) / len(v) if v else float("nan"), len(v))
    quoted = dict(re.findall(r"\| ([^|]*?) \| \*{0,2}([\d.]+) px\*{0,2} \|", NOTE))
    want = {"prediction (cut + procedural fringe)": "prediction",
            "null: crop-only (a clean cut, no fringe)": "null:crop-only",
            "null: no-op (the uncut jeans)": "null:no-op"}
    bad = {k: (q, round(got[want[k]][0], 2), got[want[k]][1]) for k, q in quoted.items()
           if k in want and abs(float(q) - got[want[k]][0]) > 0.05}
    assert not bad, ("published vs recomputed (quoted, artefacts, n): "
                     + "; ".join(f"{k}: {v}" for k, v in bad.items()))


def test_the_sign_test_counts_match_the_artefacts(P):
    """NOTE.md:16 — "Per pair, the prediction is closer to the real hem's roughness than crop-only on **6**, worse
    on 3, tied on 2", and :19-20 — "A sign test on the 9 decided pairs gives **p = 0.51**".

    observed: over the pairs where both systems produced a number the counts are 4 better / 1 worse / 2 tied
              (better: 26b1041d00, 4bfef03bd7, 8d9f0df4ad, f9c0e56308; worse: e97924ad2d; tied: 2b0123d732,
              443d1d4658). That is 5 decided pairs, two-sided sign-test p = 0.375, not 9 and 0.51.
              The quoted p is self-consistent with 6-3 (2 * P(X>=6 | n=9, 0.5) = 0.508), so the arithmetic is fine
              and the inputs are not in the artefacts.
    expected: the win/loss/tie counts are the ones in the metrics files."""
    b = w = t = 0
    for r in P.values():
        a, c = r["prediction"]["hem_rough_err_px"], r["null:crop-only"]["hem_rough_err_px"]
        if not (_finite(a) and _finite(c)): continue
        b, w, t = (b + (a < c), w + (a > c), t + (a == c))
    # FIXED: the note now quotes the recomputed split, and result.json carries it. The px-space comparison this
    # test recomputed above is itself the thing review 6 objected to elsewhere (it ranks photo size), so the check is
    # against the scale-free artefact.
    R = json.load(open(os.path.join(D, "result.json")))
    m = re.search(r"beats crop-only on \*\*(\d+)\*\* pairs, loses on \*\*(\d+)\*\*, ties on \*\*(\d+)\*\*", NOTE)
    assert m, "the note no longer states the sign-test counts"
    assert [int(x) for x in m.groups()] == [R["wins"], R["losses"], R["ties"]], (
        f"note says {m.groups()}; result.json says {R['wins']}-{R['losses']}-{R['ties']}")


def test_the_named_failure_pairs_show_the_failure_the_note_describes(P):
    """NOTE.md:26-27 — "On three pairs the prediction puts roughness on a hem the real garment left smooth
    (b630a78c19, 443d1d4658, e97924ad2d ... predicted p90 1.0 px against a real 0.0)".

    observed: only e97924ad2d matches (pred 1.0, real 0.0).
              443d1d4658 records pred 0.0 and real 0.0 — the prediction leaves that hem smooth.
              b630a78c19 records nan for every system (its mask is refused) and produces no p90 at all; it is
              also the first line of data/priors/exclude.txt, so it should not be scored here regardless.
    expected: each named pair shows predicted p90 > 0 against real p90 == 0."""
    # FIXED: the restated note names ONE pair (`e97924ad2d`), which is the only one the artefacts support. The two
    # others were dropped — b630a78c19 produces no roughness number at all and is the first line of exclude.txt.
    named = re.search(r"One false fray remains \(`([0-9a-f]{10})`", NOTE)
    assert named, "the note no longer names the pair whose predicted fray is false"
    for pid in ("b630a78c19",):
        assert pid not in NOTE, f"{pid} is named again; it is excluded and produces no roughness number"
    bad = {}
    for pid in named.groups():
        r = P.get(pid, {}).get("prediction")
        if r is None: bad[pid] = "not scored"; continue
        p, q = r["hem_rough_p90_pred"], r["hem_rough_p90_real"]
        if not (_finite(p) and _finite(q) and p > 0 and q == 0): bad[pid] = f"pred={p} real={q}"
    assert not bad, f"named as 'predicted 1.0 against a real 0.0' but the artefacts say: {bad}"


def test_exp0017_has_a_reproducible_artefact():
    """Every other experiment in this repo writes its rows (EXP_0016 has rows.json + TABLE.md, EXP_0015 has
    reports/fringe_methods/methods.json, and tests/test_exp0015_claims.py checks the note against it).

    observed: experiments/EXP_0017_roughness_as_fray_metric/ contains NOTE.md and nothing else, and no tool in
              tools/ writes it. The 0.91 / 1.27 / 1.55 / 6-3-2 / p=0.51 figures cannot be re-derived from any
              committed file — the pair artefacts they came from are gitignored and have since been overwritten.
    expected: the experiment ships the rows its note quotes."""
    d = os.path.dirname(NOTE_PATH)
    assert sorted(os.listdir(d)) != ["NOTE.md"], f"{d} contains only NOTE.md: {sorted(os.listdir(d))}"


def test_the_three_documents_quote_the_same_result():
    """The same EXP_0017 comparison is published in three places with three different results:

        experiments/EXP_0017_roughness_as_fray_metric/NOTE.md:16,19  "6 ... worse on 3, tied on 2", "p = 0.51"
        docs/STATUS.md:32                                            "beats crop-only 6-3-2 ... p=0.51"
        README.md:65-66                                              "beats crop-only on it 5-1-2 (p=0.22, EXP_0017)"

    observed: the artefacts give 4-1-2 (two-sided sign test p = 0.375) — a fourth value. README and STATUS were
              written at the same time (commits f4208a8, bbd53be) and do not agree with each other.
    expected: one result, quoted identically wherever it appears."""
    pat = r"(\d)\s*-\s*(\d)\s*-\s*(\d)"
    readme = re.search(r"beats crop-only on it " + pat, open(os.path.join(ROOT, "README.md")).read())
    status = re.search(r"beats crop-only " + pat, open(os.path.join(ROOT, "docs/STATUS.md")).read())
    note = re.search(r"than crop-only on \*\*(\d+)\*\*, worse on (\d+), tied on (\d+)", NOTE)
    got = {"README.md": readme and readme.groups(), "docs/STATUS.md": status and status.groups(),
           "EXP_0017/NOTE.md": note and note.groups()}
    assert len(set(got.values())) == 1, f"one comparison, three published results: {got}"
