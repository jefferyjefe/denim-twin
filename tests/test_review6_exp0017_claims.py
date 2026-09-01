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


# The four tests below that take the `P` fixture read experiments/pairs/*/cmp_median/metrics.json,
# which is gitignored. The fixture used to pytest.skip("no scored pair runs in this checkout") --
# correct, but in prose that no tool could read or count. Declared instead: under --profile ci they
# report UNAVAILABLE[pair_cmp_metrics] with the command that fixes it, and under --profile full they
# FAIL, because a scientific pass may not be issued over scoring output that is not there.
#
# The marker is PER-TEST, not a module-level pytestmark. It was module-level for one revision, and
# that silently disabled the two tests at the bottom of this file -- which read only committed
# documents and reports and are perfectly checkable in a clean clone. One of them is the
# cross-document guard that had been passing vacuously (all three regexes returning None, so
# len({None}) == 1) and was just rewritten to bite; a module-level marker would have shipped that
# rewrite un-exercised in CI, which is the same class of mistake wearing the new mechanism's clothes.
NEEDS_SCORED_PAIRS = pytest.mark.needs("pair_cmp_metrics")


@pytest.fixture(scope="module")
def P():
    p = _pairs()
    assert p, ("no scored pair runs found even though the prerequisite reports them present; "
               "experiments/pairs/*/cmp_median/metrics.json exists but carries no usable rows")
    return p


@NEEDS_SCORED_PAIRS
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


@NEEDS_SCORED_PAIRS
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


@NEEDS_SCORED_PAIRS
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


@NEEDS_SCORED_PAIRS
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


SPLIT = r"(?<!\d)(\d)\s*-\s*(\d)\s*-\s*(\d)(?!\d)"   # a win-loss-tie split; single digits, so dates never match


def test_the_three_documents_quote_the_same_result():
    """The same EXP_0017 comparison was published in three places with three different results:

        experiments/EXP_0017_roughness_as_fray_metric/NOTE.md:16,19  "6 ... worse on 3, tied on 2", "p = 0.51"
        docs/STATUS.md:32                                            "beats crop-only 6-3-2 ... p=0.51"
        README.md:65-66                                              "beats crop-only on it 5-1-2 (p=0.22, EXP_0017)"

    All three documents have since been restated, and the guard that was here did not survive the restatement --
    worse, it did not notice. It built `{doc: re.search(...) and m.groups()}` and asserted `len(set(...)) == 1`.
    When every pattern stopped matching the dict became `{None, None, None}`, the set became `{None}`, and the
    cross-document consistency check passed having compared nothing at all. A regex that stops matching is now a
    failure that names the document that drifted, and the patterns below are bound to the current text.

    What the documents say now, and why the comparison had to be re-aimed rather than re-pointed:

      * EXP_0017 was retracted twice. Its NOTE.md and README.md both publish the *retraction's* headline -- 6 of
        the 7 real hems measure exactly zero, at 241-389 px of waistband -- and that is the number all the
        current-position documents are supposed to state identically. It is checked in (a).
      * README.md no longer publishes a win/loss/tie split for this comparison at all; the score was withdrawn.
        Demanding that it quote one would be demanding it re-publish a retracted result, so (b) instead binds the
        NOTE's split to result.json and requires that any split README ever quotes again agree with it.
      * docs/STATUS.md is EXEMPT from (a) and (b), and the exemption is not a hole. It is a step log and says so
        in its own banner ("Entries are left as written because this file is a step log; the current position is
        in README.md, docs/BACKLOG.md and EXP_0034"), so repo policy is that its 6-3-2, 4-1-2 and 1-3-3 entries
        are the historical record and corrections go in banners, never by editing the record. Rewriting them to
        match today's number would destroy the evidence that the drift happened. (c) therefore checks the only
        thing that can honestly be asked of an archive: that it still declares itself one, and that every entry
        carrying a superseded split is marked superseded, so an archived number cannot be read as current.
    """
    README = open(os.path.join(ROOT, "README.md")).read()
    STATUS = open(os.path.join(ROOT, "docs/STATUS.md")).read()

    # (a) the retraction's headline, in the two documents that publish the current position.
    CURRENT = {"README.md": README, "EXP_0017/NOTE.md": NOTE}

    def quoted(pat, what):
        got = {}
        for name, text in CURRENT.items():
            m = re.search(pat, text)
            assert m, (f"{name} no longer states {what}: {pat!r} does not match. Either the document drifted or "
                       f"this guard did; do not delete the pattern without re-aiming it at the new wording.")
            got[name] = m.groups()
        assert len(set(got.values())) == 1, f"one result, several published values for {what}: {got}"
        return next(iter(got.values()))

    n_zero, n_pairs = quoted(r"\*\*(\d+) of the (\d+) [^*]*exactly zero\*\*",
                             "how many real hems measure exactly zero")
    assert 0 < int(n_zero) <= int(n_pairs), (n_zero, n_pairs)
    quoted(r"(\d+)\s*[-\u2013]\s*(\d+) px of\s+waistband",
           "the waistband resolution those hems were measured at")

    # (b) the win/loss/tie split: the note's must be result.json's, and README must not contradict it.
    R = json.load(open(os.path.join(D, "result.json")))
    split = [R["wins"], R["losses"], R["ties"]]
    m = re.search(r"beats crop-only on \*\*(\d+)\*\* pairs, loses on \*\*(\d+)\*\*, ties on \*\*(\d+)\*\*", NOTE)
    assert m, "EXP_0017/NOTE.md no longer states the sign-test split"
    assert [int(x) for x in m.groups()] == split, f"note says {m.groups()}; result.json says {split}"
    bad = [g for g in re.findall(SPLIT, README) if [int(x) for x in g] != split]
    assert not bad, (f"README.md quotes a win-loss-tie split that is not result.json's {split}: {bad}. "
                     "The EXP_0017 score is retracted; if README publishes one again it must be the artefact's.")
    # and the note's own superseded splits stay inside its retraction banners, never in its body
    body = "\n".join(l for l in NOTE.splitlines() if not l.lstrip().startswith(">"))
    assert not re.search(SPLIT, body), (
        "a bare win-loss-tie split appears in EXP_0017/NOTE.md outside its retraction banner: "
        f"{re.findall(SPLIT, body)}")

    # (c) docs/STATUS.md, exempt but not unchecked -- see the docstring for why it is not rewritten.
    assert "this file is a step log" in STATUS, (
        "docs/STATUS.md no longer declares itself a step log; that declaration is the whole basis on which "
        "its superseded EXP_0017 numbers are exempt from the comparison above")
    unmarked = [b.splitlines()[0][:80] for b in re.split(r"\n(?=- )", STATUS)
                if "EXP_0017" in b and re.search(SPLIT, b)
                and not re.search(r"retract|supersed|void|at the time|corrected", b, re.I)]
    assert not unmarked, ("docs/STATUS.md entries quote an EXP_0017 win-loss-tie split without marking it "
                          f"superseded, so it reads as the current result: {unmarked}")
