"""Which physical thing a repeat is a photograph of.

Six shots in the production plan use `min_reps` to mean the other leg, the other outseam, the other
hem position. Nothing bound a repeat to its subject, so two photographs of one leg satisfied both
repeats and the other leg's original hem was never taken -- and there is no going back for it after
the cut. The shot plan did ask a person to confirm it, and asked the SAME sentence for every repeat
("this frame shows the garment-LEFT hem / the garment-RIGHT hem"), which is true of either
photograph and therefore separates neither.

These tests pin the three things that make the binding enforceable: the production plan is fully
readable by this module, a declared subject that is not the one the plan requires is refused at
ingest, and the gate closes when two repeats claim the same subject or when one records none.
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import gates as GATES, qa as QA, spec as SPEC     # noqa: E402
from denimtwin.pilot import subjects as SUBJ                           # noqa: E402
from denimtwin.pilot.selftest import Bench, _mini_spec                 # noqa: E402


@pytest.fixture(scope="module")
def spec():
    return SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")


def test_every_rep_semantics_string_in_the_production_plan_has_a_reading(spec):
    """FAIL CLOSED ON NEW TEXT.

    The mapping is a closed table over the plan's own frozen sentences, not a pattern match with a
    default. This test is what makes that safe: add "the garment-LEFT pocket / the garment-RIGHT
    pocket" to the plan and either the prefix rule reads it or this fails -- rather than the
    distinction quietly ceasing to be enforced.
    """
    unreadable = []
    seen = 0
    for sh in spec.shots:
        for t in (sh.get("rep_semantics") or []):
            seen += 1
            try:
                SUBJ.subject_of(t)
            except SUBJ.UnknownSemantics:
                unreadable.append((sh["shot_id"], t))
    assert seen >= 20, "the plan should carry many rep_semantics entries; found %d" % seen
    assert not unreadable, unreadable


def test_the_sides_the_plan_names_bind_to_the_two_legs(spec):
    got = {}
    for sh in spec.shots:
        for i, t in enumerate((sh.get("rep_semantics") or []), 1):
            got.setdefault(SUBJ.subject_of(t), set()).add(t)
    assert SUBJ.LEG_L in got and SUBJ.LEG_R in got, got.keys()
    assert all("garment-LEFT" in t for t in got[SUBJ.LEG_L])
    assert all("garment-RIGHT" in t for t in got[SUBJ.LEG_R])


def test_a_subject_the_module_has_never_seen_raises_rather_than_defaulting():
    with pytest.raises(SUBJ.UnknownSemantics):
        SUBJ.subject_of("the third leg")
    with pytest.raises(SUBJ.UnknownSemantics):
        SUBJ.subject_of("")


def _side_shot(spec):
    for sh in spec.shots:
        sem = sh.get("rep_semantics") or []
        if len(sem) >= 2 and SUBJ.subject_of(sem[0]) != SUBJ.subject_of(sem[1]):
            return sh
    raise AssertionError("no shot in the plan distinguishes subjects between repeats")


def test_the_claim_a_person_confirms_names_ONE_subject(spec):
    """The plan's own claim listed every subject the shot has, so it was true of either
    photograph."""
    sh = _side_shot(spec)
    c1, c2 = SUBJ.claim_for(sh, 1), SUBJ.claim_for(sh, 2)
    assert c1 != c2
    sem = sh["rep_semantics"]
    assert sem[0] in c1 and sem[1] not in c1
    assert sem[1] in c2 and sem[0] not in c2


def test_the_generic_claim_is_replaced_not_duplicated(spec):
    """Two claims about one fact, one of which cannot be false, is a person confirming the same
    thing twice and a gate reporting more evidence than it has."""
    sh = _side_shot(spec)
    generic = [c for c in (sh.get("requires_human") or [])
               if SUBJ.is_generic_subject_claim(c)]
    assert generic, "this test assumes the plan still carries the generic claim"
    tmp = Path(tempfile.mkdtemp(prefix="subjclaim_"))
    b = Bench(tmp, spec, "DENIM_9801")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    live = [x for x in b.activated()[0] if x["shot_id"] == sh["shot_id"]]
    if not live:
        raise AssertionError(
            "the committed plan no longer activates that shot under the default answers, so "
            "this guard has stopped guarding anything. A skip here would hide that.")
    b.add(live[0], 1, b.synth_for(live[0], 1), confirm_all=False)
    st, _ = b.store.fold()
    ids = [c["check_id"] for c in st["qa"][(sh["shot_id"], 1)]["checks"]]
    assert not any(SUBJ.is_generic_subject_claim(i) for i in ids), ids
    assert any(SUBJ.claim_for(live[0], 1) in i for i in ids), ids


def test_declaring_the_wrong_subject_for_a_repeat_is_refused(spec):
    sh = _side_shot(spec)
    r1 = SUBJ.required(sh, 1)
    r2 = SUBJ.required(sh, 2)
    assert SUBJ.capture_fields(sh, 1, declared=r1["subject_id"])["subject_id"] == r1["subject_id"]
    with pytest.raises(SUBJ.WrongSubject):
        SUBJ.capture_fields(sh, 1, declared=r2["subject_id"])
    with pytest.raises(SUBJ.WrongSubject):
        SUBJ.capture_fields(sh, 1, declared="THE_OTHER_TROUSERS")


def test_an_instanced_frame_takes_its_subject_from_the_annotation_it_is_of():
    shot = {"shot_id": "BEFORE.ANOM.TEAR.I01", "state": "before", "annotation_id": "TEAR.01"}
    assert SUBJ.capture_fields(shot, 1)["subject_id"] == "FEATURE.TEAR.01"


@pytest.fixture(scope="module")
def bound_session(spec):
    """A small real session containing a subject-distinguishing shot, both repeats taken."""
    tmp = Path(tempfile.mkdtemp(prefix="subjgate_"))
    b = Bench(tmp, spec, "DENIM_9802")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sh = _side_shot(spec)
    live = [x for x in b.activated()[0] if x["shot_id"] == sh["shot_id"]]
    if not live:
        raise AssertionError(
            "the committed plan no longer activates that shot under the default answers, so "
            "this guard has stopped guarding anything. A skip here would hide that.")
    s = live[0]
    for rep in (1, 2):
        b.add(s, rep, b.synth_for(s, rep, relay=rep))
    return {"bench": b, "shot": s, "spec": spec}


def test_the_gate_accepts_repeats_bound_to_the_subjects_the_plan_requires(bound_session):
    b = bound_session["bench"]
    conds = b.blocked_conditions("ready_to_cut", check_files=False)
    assert "captures.subjects_bound" not in conds, conds


def _mutate_last_capture(b, spec, **fields):
    """Replay this session with one capture's subject fields changed."""
    from denimtwin.pilot.selftest import _rebuild
    entries = b.entries()
    out, done = [], False
    for e in reversed(entries):
        if not done and e.get("kind") == "capture":
            p = dict(e["payload"])
            p.update(fields)
            e = dict(e, payload=p)
            done = True
        out.append(e)
    assert done, "no capture to mutate"
    dest = Path(tempfile.mkdtemp(prefix="subjmut_"))
    return _rebuild(list(reversed(out)), b.gid, dest)


def test_two_repeats_claiming_the_same_subject_close_the_gate(bound_session):
    b, spec = bound_session["bench"], bound_session["spec"]
    first = SUBJ.required(bound_session["shot"], 1)
    st = _mutate_last_capture(b, spec, subject_id=first["subject_id"],
                              subject_aspect=first["aspect"])
    v = GATES.evaluate("ready_to_cut", spec, st, garment_dir=st.dir, check_files=False)
    assert "captures.subjects_bound" in {x.condition for x in v.blocks}


def test_a_repeat_that_records_no_subject_closes_the_gate(bound_session):
    """Omitting the field was the cheapest way past a check that only looked at frames carrying
    one."""
    b, spec = bound_session["bench"], bound_session["spec"]
    st = _mutate_last_capture(b, spec, subject_id=None, subject_aspect=None)
    v = GATES.evaluate("ready_to_cut", spec, st, garment_dir=st.dir, check_files=False)
    assert "captures.subjects_bound" in {x.condition for x in v.blocks}


def test_a_repeat_filed_against_the_other_leg_closes_the_gate(bound_session):
    b, spec = bound_session["bench"], bound_session["spec"]
    st = _mutate_last_capture(b, spec, subject_id="OFFCUT.L", subject_aspect="nonsense")
    v = GATES.evaluate("ready_to_cut", spec, st, garment_dir=st.dir, check_files=False)
    assert "captures.subjects_bound" in {x.condition for x in v.blocks}


def test_re_describing_an_instance_after_its_frames_were_accepted_closes_the_gate(spec, tmp_path):
    """The id still matches and the meaning has changed, which is the silent version.

    `captures.instance_identity` compared the annotation id alone. Correcting TEAR.01's location
    from "left leg" to "right leg" left every accepted photograph of it matching on id while being
    a photograph of something else, and nothing anywhere could see it.
    """
    b = Bench(tmp_path, spec, "DENIM_9803")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    b.store.append("annotation",
                   {"annotation_id": "TEAR.01", "feature": "n_tears", "type": "tear",
                    "location": "left leg front, 12 cm above the hem", "operator": "alice"},
                   operator="alice")
    b.store.append("feature_answers", {"answers": {"n_tears": 1}}, operator="alice")
    inst = [x for x in b.activated()[0] if x.get("annotation_id") == "TEAR.01"]
    if not inst:
        raise AssertionError(
            "no instanced shot activates for n_tears in the committed plan, so this guard has "
            "stopped guarding anything")
    sh = inst[0]
    b.add(sh, 1, b.synth_for(sh, 1))
    assert "captures.instance_identity" not in b.blocked_conditions("ready_to_cut",
                                                                   check_files=False)
    b.store.append("annotation",
                   {"annotation_id": "TEAR.01", "feature": "n_tears", "type": "tear",
                    "location": "RIGHT leg back, at the knee", "operator": "alice"},
                   operator="alice")
    conds = b.blocked_conditions("ready_to_cut", check_files=False)
    assert "captures.instance_identity" in conds, conds


def test_an_instanced_frame_that_records_no_description_is_refused(spec, tmp_path):
    """Omitting the field was the cheapest way past a check that only looked at captures carrying
    it -- the same hole the annotation_id arm already refuses by name."""
    from denimtwin.pilot.selftest import _rebuild
    b = Bench(tmp_path, spec, "DENIM_9804")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    b.store.append("annotation",
                   {"annotation_id": "TEAR.01", "feature": "n_tears", "type": "tear",
                    "location": "left leg front, 12 cm above the hem", "operator": "alice"},
                   operator="alice")
    b.store.append("feature_answers", {"answers": {"n_tears": 1}}, operator="alice")
    inst = [x for x in b.activated()[0] if x.get("annotation_id") == "TEAR.01"]
    if not inst:
        raise AssertionError(
            "no instanced shot activates for n_tears in the committed plan, so this guard has "
            "stopped guarding anything")
    b.add(inst[0], 1, b.synth_for(inst[0], 1))
    assert "captures.instance_identity" not in b.blocked_conditions("ready_to_cut",
                                                                    check_files=False)
    entries, out, done = b.entries(), [], False
    for e in reversed(entries):
        if not done and e.get("kind") == "capture" and e["payload"].get("annotation_id"):
            e = dict(e, payload=dict(e["payload"], annotation_location=None))
            done = True
        out.append(e)
    assert done
    st = _rebuild(list(reversed(out)), b.gid, tmp_path / "mut")
    v = GATES.evaluate("ready_to_cut", spec, st, garment_dir=st.dir, check_files=False)
    assert "captures.instance_identity" in {x.condition for x in v.blocks}


def test_a_borrowed_frame_is_refused_for_a_repeat_it_is_not_the_subject_of(spec):
    """`reuse` is the third writer of capture records and the only one that did not derive the
    subject through `subjects.capture_fields` -- it copied the SOURCE's. Borrowing the left-hem
    frame for the repeat the plan reserves for the right hem exited 0, printed "recorded", counted
    as that repeat's photograph in captures.required_complete, and left captures.subjects_bound
    blocking the cut gate for the rest of the session. Fail-closed, so never a false READY -- but
    the operator learned of it at the gate rather than at the command that did it, and the log is
    append-only, so the record stays.
    """
    import json
    import os
    import subprocess

    tmp = Path(tempfile.mkdtemp(prefix="reuse_subject_"))
    b = Bench(tmp, spec, "DENIM_9807")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sh = None
    for s in b.activated()[0]:
        sem = s.get("rep_semantics") or []
        if len(sem) >= 2 and SUBJ.subject_of(sem[0]) != SUBJ.subject_of(sem[1]):
            sh = s
            break
    # Not a skip. The plan is committed, so a tree where no shot separates its repeats by subject
    # is a tree where this guard has silently stopped guarding anything.
    assert sh is not None, (
        "no activated shot in the committed plan distinguishes its repeats by subject, so this "
        "test would prove nothing")

    env = dict(os.environ, PILOT_GARMENTS=str(tmp / "garments"))
    py = str(Path(sys.executable))

    def cli(*args):
        return subprocess.run([py, str(ROOT / "tools" / "pilot.py"), "--operator", "test"]
                              + [str(a) for a in args],
                              capture_output=True, text=True, env=env, cwd=str(ROOT))

    r = cli("add", b.gid, sh["shot_id"], str(b.synth_for(sh, 1, relay=1)), "--rep", 1)
    assert "r1 ->" in r.stdout, r.stdout + r.stderr

    args = ["reuse", b.gid, sh["shot_id"], sh["shot_id"], "--source-rep", 1, "--rep", 2,
            "--reason", "one frame standing in for the other repeat"]
    for c in QA.human_claims(sh, 2):
        args += ["--confirm", c]
    for c in ("ruler_visible", "side_confirmed", "region_confirmed", "relay_confirmed",
              "camera_repositioned"):
        args += ["--confirm", c]
    r = cli(*args)

    want = SUBJ.required(sh, 2)["subject_id"]
    assert r.returncode != 0, (
        "reuse recorded a photograph of %s against the repeat the plan reserves for %s:\n%s"
        % (SUBJ.required(sh, 1)["subject_id"], want, r.stdout))
    assert want in (r.stdout + r.stderr), (r.stdout + r.stderr)[-600:]

    entries = [json.loads(x) for x in
               (b.dir / "pilot" / "manifest.jsonl").read_text().splitlines()]
    caps = [e["payload"] for e in entries if e.get("kind") == "capture"]
    assert not [c for c in caps if c["shot_id"] == sh["shot_id"] and c["rep"] == 2], (
        "the command refused and wrote the record anyway")

    from denimtwin.pilot.store import Store
    v = GATES.evaluate("ready_to_cut", spec, Store(b.dir), garment_dir=b.dir, check_files=False)
    assert "captures.subjects_bound" not in {x.condition for x in v.blocks}, \
        [x.what for x in v.blocks if x.condition == "captures.subjects_bound"]


def test_a_borrowed_frame_whose_claims_are_confirmed_afterwards_is_accepted(spec):
    """`reuse` records a declaration carrying the outcome of re-running the borrowing shot's checks
    on the borrowed frame. For any shot that raises a human claim that outcome is
    HUMAN_VERIFICATION_REQUIRED -- 162 of the 295 shots in the committed plan carry
    `requires_human` -- and `captures.reuse_legitimate` used to demand a frozen PASS.

    A reuse_declaration cannot be superseded: the fold accumulates them into an append-only list,
    and the confirmation arrives later as a different entry kind. So one `pilot.py reuse` on such a
    shot closed ready_to_cut, ready_to_wash AND ready_to_finalize for the rest of the garment's
    life, with nothing the operator could do about it. The claims are now re-derived from the plan
    and answered through the same `_verification_for` every other claim goes through.
    """
    import json
    import os
    import subprocess

    from denimtwin.pilot import claims as CLAIMS
    from denimtwin.pilot.store import Store

    tmp = Path(tempfile.mkdtemp(prefix="reuse_claims_"))
    b = Bench(tmp, spec, "DENIM_9808")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sh = None
    for s in b.activated()[0]:
        if int(s.get("min_reps") or 1) >= 2 and (s.get("requires_human") or []) \
                and not (s.get("rep_semantics") or []):
            sh = s
            break
    assert sh is not None, (
        "no activated shot in the committed plan repeats one view and raises a human claim, so "
        "this guard has stopped guarding anything")

    env = dict(os.environ, PILOT_GARMENTS=str(tmp / "garments"))
    py = str(Path(sys.executable))

    def cli(*args):
        return subprocess.run([py, str(ROOT / "tools" / "pilot.py"), "--operator", "test"]
                              + [str(a) for a in args],
                              capture_output=True, text=True, env=env, cwd=str(ROOT))

    r = cli("add", b.gid, sh["shot_id"], str(b.synth_for(sh, 1, relay=1)), "--rep", 1)
    assert "r1 ->" in r.stdout, r.stdout + r.stderr

    r = cli("reuse", b.gid, sh["shot_id"], sh["shot_id"], "--source-rep", 1, "--rep", 2,
            "--reason", "one frame standing in for the other repeat",
            "--confirm", "relay_confirmed", "--confirm", "camera_repositioned")
    assert "recorded." in r.stdout, r.stdout + r.stderr

    st, _ = Store(b.dir).fold()
    decl = [d for d in st["reuse"] if d["shot_id"] == sh["shot_id"]]
    assert decl, "the reuse was not recorded at all"
    assert decl[0]["outcome"] == QA.HUMAN, (
        "this test needs a declaration recorded with claims outstanding; got %s"
        % decl[0]["outcome"])

    # With the claims outstanding, the gate blocks -- and says which claims.
    v = GATES.evaluate("ready_to_cut", spec, Store(b.dir), garment_dir=b.dir, check_files=False)
    blocking = [x for x in v.blocks if x.condition == "captures.reuse_legitimate"]
    assert blocking, "a borrowed frame with unanswered claims was accepted"

    # Answer them the way the tool says to, and it is accepted.
    for cid in QA.human_claim_ids(sh, 2):
        code = CLAIMS.claim_code(cid)
        rr = cli("confirm", b.gid, "--claim-code", code, "--shot", sh["shot_id"], "--rep", 2)
        assert rr.returncode == 0, (code, rr.stdout + rr.stderr)

    v2 = GATES.evaluate("ready_to_cut", spec, Store(b.dir), garment_dir=b.dir, check_files=False)
    still = [x for x in v2.blocks if x.condition == "captures.reuse_legitimate"]
    assert not still, (
        "the claims were confirmed against the photograph and the reuse is still refused, which "
        "is a dead end in an append-only log: %s" % [x.what for x in still])


def test_a_declared_subject_is_checked_on_an_instanced_frame_too(spec):
    """`capture_fields` returned early for an instanced shot, before the `declared` check ran.

    So on those frames the operator's --subject was neither honoured nor refused nor even checked
    for being a subject at all: naming the wrong thing, or a string that means nothing, was
    accepted and silently replaced by the plan's answer. That is precisely what the function's own
    docstring says it must never do -- "silently overwriting it with the plan's answer would record
    agreement that was never given".
    """
    tmp = Path(tempfile.mkdtemp(prefix="declared_instanced_"))
    b = Bench(tmp, spec, "DENIM_9831")
    b.open_session(); b.answer_features(overrides={"n_tears": 1}); b.measure()
    b.store.append("annotation",
                   {"annotation_id": "TEAR.01", "feature": "n_tears", "type": "tear",
                    "location": "left knee", "note": "x"}, operator="alice")
    sh = None
    for s in b.activated()[0]:
        if s.get("annotation_id") and not (s.get("rep_semantics") or []):
            sh = s
            break
    assert sh is not None, "no instanced shot without rep_semantics activates in the committed plan"

    # Undeclared still binds to the instance, as before.
    assert SUBJ.capture_fields(sh, 1)["subject_id"] == SUBJ.instance_subject(sh["annotation_id"])

    # A string that is not a subject at all is refused, not dropped.
    with pytest.raises(SUBJ.WrongSubject):
        SUBJ.capture_fields(sh, 1, declared="NOT_A_SUBJECT")

    # A real subject that is not this frame's is refused, not silently overwritten.
    with pytest.raises(SUBJ.WrongSubject):
        SUBJ.capture_fields(sh, 1, declared=SUBJ.LEG_R)

    # Declaring the right one is accepted.
    ok = SUBJ.capture_fields(sh, 1, declared=SUBJ.instance_subject(sh["annotation_id"]))
    assert ok["subject_id"] == SUBJ.instance_subject(sh["annotation_id"])


def test_every_shot_that_asks_the_generic_subject_question_also_names_its_repeats(spec):
    """`human_claims` drops the plan's generic subject claim and puts the per-repeat one in its
    place. `subjects.claim_for` returns None when the shot carries no `rep_semantics`, so a shot
    shaped that way would have a required confirmation removed with nothing substituted.

    No shot in the committed plan is shaped that way. This is what says so, out loud, so a plan
    edit that introduces one fails here rather than quietly asking a person one question fewer.
    (The code also keeps the generic claim in that case rather than dropping it -- but a plan the
    code does not recognise should be caught in the plan, not absorbed at runtime.)
    """
    offenders = []
    for s in spec.doc["shots"]:
        generic = [c for c in (s.get("requires_human") or [])
                   if SUBJ.is_generic_subject_claim(c)]
        if generic and not (s.get("rep_semantics") or []):
            offenders.append(s["shot_id"])
    assert not offenders, (
        "these shots ask the generic 'which subject is this' question but do not name what each "
        "repeat is of, so there is no per-repeat claim to replace it with: %r" % offenders[:6])

    marked = [s["shot_id"] for s in spec.doc["shots"]
              if any(SUBJ.is_generic_subject_claim(c) for c in (s.get("requires_human") or []))]
    assert marked, "no shot in the plan carries the generic subject claim, so this proves nothing"


def test_a_borrowed_frame_is_filed_as_the_subject_the_target_repeat_is_for(spec):
    """`captures.subjects_bound` compares the PAIR (subject_id, subject_aspect) against what the
    plan says the repeat is. `reuse` compares only the id -- deliberately, because two shots that
    are both of the left hem word their repeats differently and refusing on the wording would
    refuse the legitimate borrow this command exists for -- but it then copied the SOURCE's aspect
    into the record, so a permitted reuse produced a capture the gate called the wrong subject.
    A borrow the command allows and the gate then refuses is a dead end in an append-only log.
    """
    import os
    import subprocess

    from denimtwin.pilot.store import Store

    tmp = Path(tempfile.mkdtemp(prefix="reuse_aspect_"))
    b = Bench(tmp, spec, "DENIM_9841")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sh = None
    for s in b.activated()[0]:
        if len(s.get("rep_semantics") or []) >= 2:
            sh = s
            break
    assert sh is not None, "no activated shot names what each of its repeats is of"

    env = dict(os.environ, PILOT_GARMENTS=str(tmp / "garments"))
    py = str(Path(sys.executable))

    def cli(*args):
        return subprocess.run([py, str(ROOT / "tools" / "pilot.py"), "--operator", "test"]
                              + [str(a) for a in args],
                              capture_output=True, text=True, env=env, cwd=str(ROOT))

    # Both repeats of this shot are different subjects, so borrow ACROSS shots instead: find a
    # second shot whose repeat 1 is the same subject as this one's repeat 1.
    want = SUBJ.required(sh, 1)["subject_id"]
    other = None
    for s in b.activated()[0]:
        if s["shot_id"] == sh["shot_id"]:
            continue
        r = None
        try:
            r = SUBJ.required(s, 1)
        except SUBJ.UnknownSemantics:
            continue
        if r and r["subject_id"] == want and r["aspect"] != SUBJ.required(sh, 1)["aspect"]:
            other = s
            break
    assert other is not None, (
        "no second activated shot is of %s with different wording, so the case this guards "
        "against does not arise in the committed plan" % want)

    assert "r1 ->" in cli("add", b.gid, sh["shot_id"], str(b.synth_for(sh, 1, relay=1)),
                          "--rep", 1).stdout

    r = cli("reuse", b.gid, sh["shot_id"], other["shot_id"], "--source-rep", 1, "--rep", 1,
            "--reason", "the same physical thing, framed for both shots",
            "--confirm", "relay_confirmed", "--confirm", "camera_repositioned")
    assert "recorded." in r.stdout, (
        "the borrow was refused, so the recorded subject cannot be checked:\n%s"
        % (r.stdout + r.stderr)[-800:])

    st, _ = Store(b.dir).fold()
    cap = st["captures"][(other["shot_id"], 1)]
    req = SUBJ.required(other, 1)
    got = (cap.get("subject_id"), cap.get("subject_aspect") or "")
    want_pair = (req["subject_id"], req["aspect"] or "")
    assert got == want_pair, (
        "the borrowed frame was filed as %r and the plan says that repeat is %r -- which is the "
        "pair captures.subjects_bound compares" % (got, want_pair))
    v = GATES.evaluate("ready_to_cut", spec, Store(b.dir), garment_dir=b.dir, check_files=False)
    assert "captures.subjects_bound" not in {x.condition for x in v.blocks}, \
        [x.what for x in v.blocks if x.condition == "captures.subjects_bound"]
