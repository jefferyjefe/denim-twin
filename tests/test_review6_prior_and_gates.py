"""Review 6 — the review-5 response: what the fringe prior still publishes, and where the new gates were put.

All tests here are expected to FAIL.
"""
import ast, importlib.util, json, os, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from denimtwin.prior import predict_depth_rel, aliases_for

PRIOR = json.load(open(os.path.join(ROOT, "data/priors/fringe.json")))


def test_the_after_cut_prior_is_not_five_cuffed_garments_rule_forced_to_zero():
    """tools/predict.py:140-141 turns the prior into the number the user reads:
        rel, n_eff, sd_rel = predict_depth_rel(pr, a.state, None); depth_px = rel * ww
    and predict.py:204 prints `fringe depth: **{depth_mm} mm** (80% interval ...) from prior[after_cut] n=5`.

    prior.predict_depth_rel (prior.py:9-10) conditions on `kind` only. Every after_cut row in
    data/priors/fringe.json is a RULE output, not a measurement (fit_fringe.py:37-41):
        26b1041d00 cuffed -> 0.0   "finished hem -> 0 by rule"
        2b0123d732 cuffed -> 0.0   "finished hem -> 0 by rule"   (measured 0.0069)
        443d1d4658 cuffed -> 0.0   "finished hem -> 0 by rule"   (measured 0.0056)
        8d9f0df4ad cuffed -> 0.0   "finished hem -> 0 by rule"   (measured 0.0044)
        e97924ad2d raw    -> 0.010 "unwashed raw cut -> capped at 0.01*waist by rule"

    So the after_cut prediction for a RAW cut edge is the mean of four cuffed garments' rule-zeros and one capped
    raw cut. tests/test_prior_provenance.py:18-24 checks the rows record their rule; nothing checks that the
    lookup stops pooling them.

    observed: predict_depth_rel(prior, "after_cut") -> (0.002, n=5, sd=0.004) — five rows, zero measurements,
              a mean 5x below the only raw-cut row it contains.
    expected: the lookup for a raw cut does not average in garments whose depth was set to 0 by a rule for having
              a finished hem."""
    rel, n, sd = predict_depth_rel(PRIOR, "after_cut", None)
    pooled = [r for r in PRIOR["pairs"] if r["kind"] == "after_cut"]
    ruled = [r["pair"] for r in pooled if r.get("rule_applied")]
    # FIXED (review 6, finding 6): the rows are still in the file — they record what the rule decided, and deleting
    # them would hide that — but the LOOKUP no longer pools them. The check is on what the prediction reads.
    assert n == len(pooled) - len(ruled), (
        f"predict_depth_rel('after_cut') pooled {n} rows; {len(ruled)} of the {len(pooled)} in the file are rule "
        f"outputs, so it should pool {len(pooled) - len(ruled)}")
    if n == 0:
        assert rel == 0.0, "with nothing measured the prior must not invent a depth"


def test_the_small_sample_flag_can_still_fire():
    """tools/predict.py:151 — `if n_eff < 5: FLAGS.append("fringe prior has only n={n_eff} samples: the depth
    below is not yet evidence-backed")` — is the only count-based caveat left in the product path.

    observed: the prior as it now stands returns n_eff = 5 for after_cut and n_eff = 6 for after_wash, so the
              flag never fires for either state — while 5 of the 5 after_cut rows and 5 of the 6 after_wash
              samples are respectively rule outputs and web-channel samples with no wash-count evidence.
              The count was made to pass by pooling, not by measuring.
    expected: at least one reachable state still trips the guard, or the guard is removed as dead."""
    n = {s: predict_depth_rel(PRIOR, s, None)[1] for s in ("after_cut", "after_wash")}
    assert min(n.values()) < 5, f"predict.py:151's n<5 flag is unreachable: n_eff = {n}"


def test_aliases_for_matches_the_same_photograph_across_url_variants():
    """prior.py:17-38 — "Exclude by *image*, not by page" — keys on the exact `images[].url` string
    (prior.py:34: `by_img[i["url"]].add(pid)`).

    Every CDN in this project's own data serves the same file under varying URLs: the nine control candidates in
    data/external/control_candidates.jsonl are Shopify URLs carrying `?v=<timestamp>` cache-busters, and Shopify
    additionally serves `_2048x2048` / `_1024x1024` size suffixes for the same asset. Two records that quote the
    same photograph with different `?v=` values are, to `aliases_for`, two different photographs — which is the
    exact leak review 5 finding 4 was raised to close (the TEST submission re-using a tutorial's after-wash photo).

    observed: page A cites .../shorts.jpg?v=1770320870 and page B cites .../shorts.jpg?v=1770320999 — the same
              image — and aliases_for("<A>") returns only {A}. Same for a `_1024x1024` size suffix.
    expected: both variants resolve to one photograph, so excluding A also excludes B."""
    import hashlib, tempfile
    base = "https://cdn.shopify.com/s/files/1/0322/0537/files/312137628.jpg"
    recs = [{"page_url": "https://shop.example/a", "images": [{"url": base + "?v=1770320870", "role": "after_wash"}]},
            {"page_url": "https://shop.example/b", "images": [{"url": base + "?v=1770320999", "role": "after_wash"}]},
            {"page_url": "https://shop.example/c", "images": [{"url": base.replace(".jpg", "_1024x1024.jpg"), "role": "after_wash"}]}]
    pid = lambda r: hashlib.sha1(r["page_url"].encode()).hexdigest()[:10]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write("\n".join(json.dumps(r) for r in recs)); path = f.name
    try:
        got = aliases_for(pid(recs[0]), path)
    finally:
        os.unlink(path)
    assert got == {pid(r) for r in recs}, (
        f"three records quoting one photograph; excluding the first drops {sorted(got)} instead of "
        f"{sorted(pid(r) for r in recs)}")


# FIXED (EXP_0021): the blocklist this helper used to parse out of tools/fringe_unpaired.py is gone. Both channels
# now call one implementation, denimtwin/evidence.py, and the tests below drive that instead of a re-implementation.
sys.path.insert(0, os.path.join(ROOT, "src"))
from denimtwin.evidence import single_wash_evidence, hem_frayed


def test_the_one_wash_gate_refuses_a_photo_whose_wash_count_is_unknown():
    """tools/fringe_unpaired.py:25-29 — "the thesis is ONE wash on a RAW cut edge: a photo after several washes ...
    must not enter the prior (review 5, finding 10)" — is implemented as a BLOCKLIST of six phrases. Anything the
    list does not name is admitted, so the default for an unknown wash count is ACCEPT.

    observed, on notes taken from data/external/pairs.jsonl and ordinary tutorial phrasing:
        "UPDATE photo 'after some washing and wearing': ... heavy fray"   -> admitted  (a real record, f542c57cec)
        "Finished shorts after washing (text: wash and let the fray happen)" -> admitted (9aef865c14)
        "Finished shorts flat lay (after washer/dryer per text)"          -> admitted  (4bfef03bd7, count unknown)
        "washed it twice before photographing"                            -> admitted
        "after a couple of washings"                                      -> admitted
    and, in the other direction, a legitimate single-wash note is refused:
        "After ONE wash. Later washes deepen the fray."                   -> REFUSED (matches "washes")
    expected: the gate admits a photo only when the record evidences exactly one wash."""
    drop = lambda note: not single_wash_evidence(note)[0]
    admitted = [n for n in ("UPDATE photo 'after some washing and wearing': whole shorts flat on patterned rug, heavy fray",
                            "Finished shorts after washing (text: wash and let the fray happen)",
                            "Finished shorts flat lay (after washer/dryer per text)",
                            "washed it twice before photographing",
                            "after a couple of washings") if not drop(n)]
    false_drop = [n for n in ("After ONE wash. Later washes deepen the fray.",) if drop(n)]
    assert not admitted and not false_drop, (
        f"admitted with an unevidenced wash count: {admitted}; refused although it states one wash: {false_drop}")


def test_the_hem_finish_gate_is_not_satisfied_by_a_note_that_says_the_hem_did_not_fray():
    """tools/fringe_unpaired.py:31-32 — `if finish != "frayed" and "fray" not in note: ... refuse`. The substring
    test has no polarity, so a note stating the opposite of the required evidence satisfies it.

    observed: "the hem did not fray at all after the wash", "no fraying on this pair", "I hemmed it so it would
              not fray" all contain "fray" and are therefore accepted as evidence of a frayed hem.
    expected: a note that denies fraying is not evidence of fraying."""
    accept = lambda note, finish=None: hem_frayed(note, finish)[0]
    bad = [n for n in ("the hem did not fray at all after the wash",
                       "no fraying on this pair",
                       "I hemmed it so it would not fray") if accept(n)]
    assert not bad, f"notes denying fray are accepted as evidence of a frayed hem: {bad}"


def test_the_one_wash_gate_covers_the_channel_that_actually_supplies_the_prior():
    """Review 5 finding 10 added the one-wash gate to tools/fringe_unpaired.py — the pairs-manifest channel.
    data/priors/fringe.json shows that channel currently contributes nothing: all five unpaired samples carry
    "channel": "web", i.e. they come from tools/ingest_unpaired.py, whose validate() (ingest_unpaired.py:29-40)
    requires only that `state_evidence` mention a wash in one of thirteen languages — no wash-count test at all.

    Those five are 5 of the 6 after-wash samples the prior averages, and their evidence is:
        "Wash & dry them once then they should be ready to be worn!"      (one wash — fine)  x2
        "Wash and dry."                                                    (count unknown)   x2
        "- Wash the cutoffs The washing machine frays the hems a little"   (count unknown)
        "al lavarlos en la lavadora se deshilachan las partes ..."          (count unknown)
        "Skolj sedan av shortsen och tvatta dem i tvattmaskinen ..."        (count unknown)

    observed: ingest_unpaired.validate() accepts a record whose state_evidence says "washed and dried them several
              times"; the gate was added to the channel supplying one sample and not to the one supplying five.
    expected: both channels enforce the same one-wash rule."""
    spec = importlib.util.spec_from_file_location("ingest_unpaired", os.path.join(ROOT, "tools", "ingest_unpaired.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    rec = {"page_url": "https://x/y", "image_url": "https://x/a.jpg", "license_or_terms": "CC BY 4.0",
           "state_evidence": "I washed and dried them several times until the fray looked right.",
           "hem_finish": "frayed"}
    assert m.validate(rec) is not None, (
        "ingest_unpaired.validate() accepts a multi-wash record: the web channel, which supplies 5 of the 6 "
        "after-wash samples in data/priors/fringe.json, has no wash-count gate")
