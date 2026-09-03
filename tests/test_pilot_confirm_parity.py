"""The CLI and the phone are one front door, or "the CLI is the source of truth" is a slogan.

The navigator has two ways in. Every claim a person must confirm could be confirmed from the phone,
and 164 of the 177 the production plan raises could not be typed at the CLI at all: `_claim_arg`
refused anything over 64 characters, and a claim's identity is `confirmed_` followed by the shot
plan's own sentence, up to 204. The two interfaces did not admit the same workflow, so the one that
was tested was not the one that would be used.

These tests assert the property that makes the two interchangeable rather than merely similar: the
same confirmation, made either way, folds to the same session state. Not the same HTTP status, not
the same message -- the same recorded fact, field for field, excluding only the fields that name the
route in. `claims.TRANSPORT_FIELDS` is that exemption, and it is a named constant so widening it
has to be done in the open.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import threading
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import claims as CLAIMS, spec as SPEC, webapp   # noqa: E402
from denimtwin.pilot.selftest import Bench                            # noqa: E402
from denimtwin.pilot.server import serve                              # noqa: E402
from denimtwin.pilot.store import Store                               # noqa: E402

SPEC_PATH = ROOT / "protocol" / "shotplan" / "shotplan.json"


@pytest.fixture(scope="module")
def spec():
    return SPEC.load(SPEC_PATH)


def _frame_with_claims(b, spec):
    """Capture one real frame that raises at least one human claim, and return (shot, rep)."""
    shots, _m = b.activated()
    for s in shots:
        if s["state"] != "rig" or not (s.get("requires_human") or []):
            continue
        b.add(s, 1, b.synth_for(s, 1), confirm_all=False)
        st, _ = b.store.fold()
        if CLAIMS.raised_claims(st, s["shot_id"], 1):
            return s, 1
    raise AssertionError("no rig frame raised a claim; the fixture cannot test what it exists for")


def _bench(spec, gid, tmp):
    b = Bench(tmp, spec, gid)
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    return b


def test_every_production_human_claim_is_confirmable_from_both_doors(spec):
    """Neither front door may refuse a claim the production plan can raise.

    The count is the point. 177 claims, 164 of them longer than the limit the CLI used to impose.
    """
    raised = []
    for sh in spec.shots:
        for c in (sh.get("requires_human") or []):
            raised.append("confirmed_%s" % c)
    assert len(raised) >= 150, "the production plan should raise many claims; got %d" % len(raised)
    over = [c for c in raised if len(c) > 64]
    assert over, "this test is meaningless if no production claim exceeds the old 64-char limit"

    for c in raised:
        # The CLI's own argument validator, which is the thing that used to refuse them.
        assert CLAIMS.validate_claim(c) == c
        # And the code that names it is short enough to type at either door.
        assert len(CLAIMS.claim_code(c)) < 16


def test_cli_and_phone_fold_to_the_same_confirmation(spec, tmp_path):
    """THE PARITY TEST. Same claim, two doors, one folded state."""
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)

    b_cli = _bench(spec, "DENIM_0011", str(root))
    shot, rep = _frame_with_claims(b_cli, spec)
    b_app = _bench(spec, "DENIM_0012", str(root))
    # The SAME photograph into the second garment, so both confirmations bind to the same content.
    src = b_cli.synth_for(shot, rep)
    b_app.add(shot, rep, src, confirm_all=False)

    st_cli, _ = b_cli.store.fold()
    claim = CLAIMS.raised_claims(st_cli, shot["shot_id"], rep)[0]["claim"]
    code = CLAIMS.claim_code(claim)

    # --- door one: the command line, naming the claim by its short code ------------------------
    env = dict(os.environ, PILOT_GARMENTS=str(root / "garments"))
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "pilot.py"), "--operator", "alice", "confirm",
         "DENIM_0011", "--shot", shot["shot_id"], "--rep", str(rep), "--claim-code", code,
         "--verifier", "bob", "--note", "the backdrop is empty"],
        capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr

    # --- door two: the phone, posting the same thing -------------------------------------------
    sess = webapp.Session(str(root), str(root / "garments"), SPEC_PATH,
                          ROOT / "protocol" / "charuco_board.json")
    httpd, _ = serve(webapp.build_api(sess), data_root=str(root / "garments"), port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = "http://127.0.0.1:%d/api/confirm/DENIM_0012?t=%s" % (
            httpd.server_address[1], httpd.token)
        body = json.dumps({"operator": "alice", "verifier": "bob",
                           "shot_id": shot["shot_id"], "rep": rep,
                           "claim_code": code, "note": "the backdrop is empty"}).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req, timeout=60)
        assert resp.status == 200
    finally:
        httpd.shutdown(); httpd.server_close()

    a = _confirmations(root / "garments" / "DENIM_0011")
    c = _confirmations(root / "garments" / "DENIM_0012")
    assert len(a) == len(c) == 1, (a, c)
    pa, pc = _semantic(a[0]), _semantic(c[0])
    assert pa == pc, "the two front doors recorded different facts:\n cli=%s\n app=%s" % (
        json.dumps(pa, sort_keys=True, indent=1), json.dumps(pc, sort_keys=True, indent=1))
    # And the fields that were allowed to differ actually did, so the exemption is not hiding a
    # case where both doors simply recorded nothing.
    assert a[0]["interface"] == "cli" and c[0]["interface"] == "app"
    # And the binding both doors must record is really there, in both.
    assert pa["capture_sha256"] and len(pa["capture_sha256"]) == 64


def _confirmations(gdir):
    st, problems = Store(gdir).fold()
    assert not problems, problems
    return [v for k, v in sorted(st["verifications"].items())]


#: Fields the log stamps per entry rather than the confirmation carrying: they differ between two
#: separate garments by construction and say nothing about parity.
#:
#: `capture_sha256` is NOT among them. It was, and it should not have been: it is the field that
#: says WHICH photograph was confirmed, the whole security argument for the confirmation rests on
#: it, and excluding it from the comparison meant the parity test would have passed with one door
#: recording the hash and the other recording nothing. The two garments are given the same
#: photograph precisely so it can be compared.
_PER_ENTRY = ("ts", "seq", "garment_id")


def _semantic(rec):
    return {k: v for k, v in rec.items()
            if k not in CLAIMS.TRANSPORT_FIELDS and k not in _PER_ENTRY}


@pytest.mark.parametrize("selector", ["text", "code", "index"])
def test_all_three_selectors_resolve_to_the_identical_claim(spec, tmp_path, selector):
    b = _bench(spec, "DENIM_0013", str(tmp_path))
    shot, rep = _frame_with_claims(b, spec)
    st, _ = b.store.fold()
    raised = CLAIMS.raised_claims(st, shot["shot_id"], rep)
    want = raised[0]["claim"]
    kw = {"text": {"claim": want},
          "code": {"code": raised[0]["code"]},
          "index": {"index": 1}}[selector]
    assert CLAIMS.resolve(st, shot["shot_id"], rep, **kw) == want


def test_the_plans_own_sentence_resolves_without_the_prefix(spec, tmp_path):
    """An operator reads the requirement off the screen and types the sentence, not the check id."""
    b = _bench(spec, "DENIM_0014", str(tmp_path))
    shot, rep = _frame_with_claims(b, spec)
    st, _ = b.store.fold()
    want = CLAIMS.raised_claims(st, shot["shot_id"], rep)[0]["claim"]
    assert want.startswith("confirmed_")
    assert CLAIMS.resolve(st, shot["shot_id"], rep, claim=want[len("confirmed_"):]) == want


@pytest.mark.parametrize("bad,why", [
    ("", "empty"),
    ("   ", "whitespace only"),
    ("x" * (CLAIMS.MAX_CLAIM_CHARS + 1), "oversized"),
    ("a\nb", "newline"),
    ("a\x00b", "null byte"),
    ("a\x07b", "control character"),
])
def test_malformed_claims_are_refused(bad, why):
    with pytest.raises(CLAIMS.ClaimError):
        CLAIMS.validate_claim(bad)


def test_a_claim_nobody_raised_is_refused_rather_than_recorded(spec, tmp_path):
    """The failure this replaces was silent: it recorded successfully and cleared nothing."""
    b = _bench(spec, "DENIM_0015", str(tmp_path))
    shot, rep = _frame_with_claims(b, spec)
    st, _ = b.store.fold()
    with pytest.raises(CLAIMS.ClaimError) as e:
        CLAIMS.resolve(st, shot["shot_id"], rep, claim="confirmed_something nobody asked for")
    assert "raised no claim" in str(e.value)
    # and the message lists what it could have been, which is why the refusal is usable
    assert "[1]" in str(e.value)


def test_multiline_notes_survive_and_do_not_break_the_log(spec, tmp_path):
    b = _bench(spec, "DENIM_0016", str(tmp_path))
    shot, rep = _frame_with_claims(b, spec)
    st, _ = b.store.fold()
    claim = CLAIMS.raised_claims(st, shot["shot_id"], rep)[0]["claim"]
    note = "line one\nline two\n\tindented\nunicode: é中"
    b.store.append("human_verification",
                   CLAIMS.payload(claim=claim, shot_id=shot["shot_id"], rep=rep, note=note,
                                  operator="alice", interface="cli", entry_mode="scripted"),
                   operator="alice")
    st2, problems = b.store.fold()
    assert not problems, problems
    assert st2["verifications"][(shot["shot_id"], rep, claim)]["note"] == note


def test_a_note_cannot_be_a_path_or_a_command_or_an_unbounded_blob():
    # Traversal in a note is inert -- it is never a path -- but it must survive as literal text
    # rather than being interpreted, and the oversized case must be refused rather than written.
    assert CLAIMS.validate_note("../../etc/passwd; rm -rf /") == "../../etc/passwd; rm -rf /"
    with pytest.raises(CLAIMS.ClaimError):
        CLAIMS.validate_note("x" * (CLAIMS.MAX_NOTE_CHARS + 1))
    with pytest.raises(CLAIMS.ClaimError):
        CLAIMS.validate_note("a\x00b")


def test_scripted_and_interactive_remain_distinguishable():
    class _T(object):
        def __init__(self, tty): self._t = tty
        def isatty(self): return self._t
    assert CLAIMS.cli_entry_mode(_T(True), _T(True)) == "interactive"
    assert CLAIMS.cli_entry_mode(_T(False), _T(True)) == "scripted"
    assert CLAIMS.cli_entry_mode(_T(True), _T(False)) == "scripted"


# -- the phone must not be a second set of rules -------------------------------------------------

def _serve(root):
    sess = webapp.Session(str(root), str(root / "garments"), SPEC_PATH,
                          ROOT / "protocol" / "charuco_board.json")
    httpd, _ = serve(webapp.build_api(sess), data_root=str(root / "garments"), port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _confirm_via_app(httpd, gid, body):
    import urllib.error
    url = "http://127.0.0.1:%d/api/confirm/%s?t=%s" % (httpd.server_address[1], gid, httpd.token)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_the_phone_refuses_a_claim_about_a_shot_this_garment_never_activated(spec, tmp_path):
    """The CLI refused it and this did not, so the phone could record a verification of a frame
    that does not exist for this garment -- indistinguishable afterwards from one never made."""
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    b = _bench(spec, "DENIM_0017", str(root))
    httpd = _serve(root)
    try:
        code, out = _confirm_via_app(httpd, "DENIM_0017", {
            "operator": "alice", "shot_id": "BEFORE.NOT.A.REAL.SHOT", "rep": 1,
            "claim": "confirmed_anything"})
    finally:
        httpd.shutdown(); httpd.server_close()
    assert code == 400, (code, out)
    assert "not an activated shot" in out.get("error", "")
    assert not _confirmations(root / "garments" / "DENIM_0017")


def test_the_phone_does_not_take_the_photographs_identity_from_the_client(spec, tmp_path):
    """`capture_sha256` came straight off the request and only fell back to the accepted frame when
    absent, so the one field that says WHICH photograph was confirmed was supplied by the party
    being checked."""
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    b = _bench(spec, "DENIM_0018", str(root))
    shot, rep = _frame_with_claims(b, spec)
    st, _ = b.store.fold()
    real = st["captures"][(shot["shot_id"], rep)]["sha256"]
    claim = CLAIMS.raised_claims(st, shot["shot_id"], rep)[0]["claim"]
    httpd = _serve(root)
    try:
        code, _out = _confirm_via_app(httpd, "DENIM_0018", {
            "operator": "alice", "shot_id": shot["shot_id"], "rep": rep,
            "claim_code": CLAIMS.claim_code(claim), "capture_sha256": "f" * 64})
    finally:
        httpd.shutdown(); httpd.server_close()
    assert code == 200
    rec = _confirmations(root / "garments" / "DENIM_0018")[0]
    assert rec["capture_sha256"] == real, "the client's hash was recorded as the frame's identity"


def test_a_confirmation_records_the_instance_revision_it_was_made_under(spec, tmp_path):
    """A frame expanded from one described tear means whatever that description says. Correcting
    the description afterwards must not leave the confirmation silently attached to it."""
    from denimtwin.pilot import gates as GATES
    b = _bench(spec, "DENIM_0019", str(tmp_path))
    b.store.append("annotation",
                   {"annotation_id": "TEAR.01", "feature": "n_tears", "type": "tear",
                    "location": "left leg front", "note": "x", "operator": "alice"},
                   operator="alice")
    b.store.append("feature_answers", {"answers": {"n_tears": 1}}, operator="alice")
    inst = [x for x in b.activated()[0] if x.get("annotation_id") == "TEAR.01"]
    if not inst:
        raise AssertionError(
            "no instanced shot activates for n_tears in the committed plan, so this guard has "
            "stopped guarding anything")
    sh = inst[0]
    b.add(sh, 1, b.synth_for(sh, 1), confirm_all=False)
    st, _ = b.store.fold()
    raised = CLAIMS.raised_claims(st, sh["shot_id"], 1)
    if not raised:
        raise AssertionError(
            "that instanced frame raises no human claim in the committed plan, so there is "
            "nothing here to confirm and this guard has stopped guarding anything")
    claim = raised[0]["claim"]
    bind = CLAIMS.binding(st, spec, sh["shot_id"], 1)
    assert bind.get("annotation_id") == "TEAR.01"
    assert bind.get("annotation_revision") is not None
    b.store.append("human_verification",
                   CLAIMS.payload(claim=claim, shot_id=sh["shot_id"], rep=1, operator="alice",
                                  bind=bind, interface="cli", entry_mode="scripted"),
                   operator="alice")
    st2, _ = b.store.fold()
    rec, why = GATES._verification_for(st2, sh["shot_id"], 1, claim)
    assert rec is not None and why is None, why

    # Now correct the description. The confirmation was made about the old one.
    b.store.append("annotation",
                   {"annotation_id": "TEAR.01", "feature": "n_tears", "type": "tear",
                    "location": "RIGHT leg front", "note": "x", "operator": "alice"},
                   operator="alice")
    st3, _ = b.store.fold()
    rec3, why3 = GATES._verification_for(st3, sh["shot_id"], 1, claim)
    assert rec3 is None and "re-described" in (why3 or ""), why3


def test_the_cli_accepts_a_production_claim_typed_out_in_full(spec, tmp_path):
    """THE ORIGINAL DEFECT, driven through the real command line.

    `_claim_arg` refused anything over 64 characters and the production plan's claims run to 204,
    so the CLI could not confirm 164 of the 177 claims the plan raises. This runs `pilot.py confirm`
    as a subprocess with the whole sentence, which is what an operator copying it off the screen
    does.
    """
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    b = _bench(spec, "DENIM_0020", str(root))
    shot, rep = _frame_with_claims(b, spec)
    st, _ = b.store.fold()
    claim = max((r["claim"] for r in CLAIMS.raised_claims(st, shot["shot_id"], rep)), key=len)
    assert len(claim) > 64, "this test needs a claim longer than the old limit; got %d" % len(claim)

    env = dict(os.environ, PILOT_GARMENTS=str(root / "garments"))
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "pilot.py"), "--operator", "alice", "confirm",
         "DENIM_0020", claim, "--shot", shot["shot_id"], "--rep", str(rep)],
        capture_output=True, text=True, env=env)
    assert r.returncode == 0, "the CLI refused a claim the production plan raises:\n%s%s" % (
        r.stdout, r.stderr)
    recs = _confirmations(root / "garments" / "DENIM_0020")
    assert len(recs) == 1 and recs[0]["claim"] == claim


def test_every_session_claim_the_gates_look_for_can_be_named_at_both_doors():
    """A claim the gate requires and the front doors refuse is a gate that cannot be opened.

    `claims.resolve` refuses a session claim it does not recognise -- which is the right refusal,
    because recording a verification of a claim nobody asked for is the silent failure this replaces.
    That makes this list load-bearing: `cut_out_of_model_acknowledged` is looked up by name in
    `gates.c_cut_spec`, and leaving it out made the one cut the geometry cannot model impossible to
    authorise from either interface.
    """
    import re as _re
    src = (ROOT / "src" / "denimtwin" / "pilot" / "gates.py").read_text()
    looked_up = set(_re.findall(r'claim == "([a-z_]+)"', src))
    assert looked_up, "no session claims found in gates.py; the pattern has drifted"
    missing = looked_up - set(CLAIMS.SESSION_CLAIMS)
    assert not missing, (
        "gates.py looks these up by name and claims.SESSION_CLAIMS does not list them, so neither "
        "front door will record them: %s" % sorted(missing))
    for name in CLAIMS.SESSION_CLAIMS:
        assert CLAIMS.resolve({"qa": {}, "captures": {}}, None, None, claim=name) == name


def test_the_phone_screen_is_given_a_way_to_confirm_the_claims_it_shows(spec, tmp_path):
    """The capture screen listed the claims read-only, and then stopped listing them.

    `plan.next_action` treats a frame whose outcome is HUMAN_VERIFICATION_REQUIRED as taken and
    moves on, so the claims it raised never came back on screen: the operator worked to the end of
    the plan and met all 187 of them at once at the gate, as `captures.required_complete`, with no
    route in the app to answer any of them. Meanwhile the CLI refused the same claims for being
    over 64 characters. Between the two front doors there was no way to complete them at all.
    """
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    b = _bench(spec, "DENIM_0023", str(root))
    sess = webapp.Session(str(root), str(root / "garments"), SPEC_PATH,
                          ROOT / "protocol" / "charuco_board.json")

    # Photograph what the app says to photograph next, confirming nothing -- which is what an
    # operator does when the screen offers no way to confirm.
    captured = set()
    for _ in range(3):
        nxt = sess.snapshot("DENIM_0023").get("next")
        assert nxt, "the app offered no next action"
        live = [x for x in b.activated()[0] if x["shot_id"] == nxt["shot_id"]]
        b.add(live[0], nxt["rep"], b.synth_for(live[0], nxt["rep"]), confirm_all=False)
        captured.add((nxt["shot_id"], nxt["rep"]))

    snap = sess.snapshot("DENIM_0023")
    # The next action has MOVED ON past every one of those frames -- which is the whole problem,
    # and is asserted rather than commented. This line used to end `or True`, which deleted the
    # claim the comment above it makes.
    assert snap["next"] is not None
    assert (snap["next"]["shot_id"], snap["next"]["rep"]) not in captured, (
        "the app is still offering a frame it already has, so this test is not exercising the "
        "case it exists for")
    # ...so the outstanding claims must be surfaced somewhere that is not the frame on screen.
    rows = snap["pending_claims"]
    assert rows, "no outstanding claim was surfaced anywhere in the session view"
    assert snap["n_pending_claims"] >= len(rows)
    for c in rows:
        assert c["code"] and len(c["code"]) < 16
        assert c["shot_id"] and c["rep"] >= 1
        assert c["claim"]

    # And each one can be confirmed with nothing but what the row carries.
    httpd = _serve(root)
    try:
        code, out = _confirm_via_app(httpd, "DENIM_0023", {
            "operator": "alice", "shot_id": rows[0]["shot_id"], "rep": rows[0]["rep"],
            "claim_code": rows[0]["code"]})
    finally:
        httpd.shutdown(); httpd.server_close()
    assert code == 200, out
    after = sess.snapshot("DENIM_0023")
    assert after["n_pending_claims"] == snap["n_pending_claims"] - 1



@pytest.mark.parametrize("door", ["cli", "app"])
def test_a_confirmation_without_an_explicit_rep_still_clears_the_claim(spec, tmp_path, door):
    """Resolving against repeat 1 and STORING `None` wrote the verification under a key the gate
    never reads. It recorded successfully, printed success, and cleared nothing."""
    from denimtwin.pilot import gates as GATES
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    gid = "DENIM_0024" if door == "cli" else "DENIM_0025"
    b = _bench(spec, gid, str(root))
    shot, rep = _frame_with_claims(b, spec)
    assert rep == 1
    st, _ = b.store.fold()
    claim = CLAIMS.raised_claims(st, shot["shot_id"], 1)[0]["claim"]
    code = CLAIMS.claim_code(claim)

    if door == "cli":
        env = dict(os.environ, PILOT_GARMENTS=str(root / "garments"))
        r = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "pilot.py"), "--operator", "alice", "confirm",
             gid, "--shot", shot["shot_id"], "--claim-code", code],
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
    else:
        httpd = _serve(root)
        try:
            code_, out = _confirm_via_app(httpd, gid, {
                "operator": "alice", "shot_id": shot["shot_id"], "claim_code": code})
        finally:
            httpd.shutdown(); httpd.server_close()
        assert code_ == 200, out

    st2, _ = Store(root / "garments" / gid).fold()
    assert (shot["shot_id"], 1, claim) in st2["verifications"], sorted(st2["verifications"])
    rec, why = GATES._verification_for(st2, shot["shot_id"], 1, claim)
    assert rec is not None and why is None, why


def test_the_cli_lists_the_same_outstanding_claims_the_phone_shows(spec, tmp_path):
    """Parity on the QUEUE, not only on the record. If only one door can find the outstanding
    claims, only one door can finish the session."""
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    b = _bench(spec, "DENIM_0026", str(root))
    for _ in range(3):
        shots = b.activated()[0]
        sh = [x for x in shots if x["state"] == "rig"][_]
        b.add(sh, 1, b.synth_for(sh, 1), confirm_all=False)

    sess = webapp.Session(str(root), str(root / "garments"), SPEC_PATH,
                          ROOT / "protocol" / "charuco_board.json")
    from_app = {(c["shot_id"], c["rep"], c["claim"])
                for c in sess.snapshot("DENIM_0026")["pending_claims"]}
    assert from_app

    env = dict(os.environ, PILOT_GARMENTS=str(root / "garments"))
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "pilot.py"), "claims",
                        "DENIM_0026", "--pending"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    for shot_id, rep, claim in from_app:
        assert CLAIMS.claim_code(claim) in r.stdout, (
            "the CLI's list omits %s, which the phone shows" % claim)
    assert "--claim-code" in r.stdout, "the listing does not say how to confirm one"


def test_a_refusal_is_recorded_as_a_refusal_at_both_doors(spec, tmp_path):
    """`bool(value)` made every non-empty string an approval.

    The web door passes the request's JSON straight in, so an operator who looked at the frame and
    typed "no, the backdrop is NOT empty" into the value field had their refusal stored as
    `value: true` — and `_verification_for`, which is careful to refuse anything that `is not True`,
    never saw the refusal at all.
    """
    from denimtwin.pilot import gates as GATES
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    b = _bench(spec, "DENIM_0027", str(root))
    shot, rep = _frame_with_claims(b, spec)
    st, _ = b.store.fold()
    claim = CLAIMS.raised_claims(st, shot["shot_id"], rep)[0]["claim"]
    code = CLAIMS.claim_code(claim)

    httpd = _serve(root)
    try:
        # a refusal dressed as a string must be refused outright, not coerced
        bad, out = _confirm_via_app(httpd, "DENIM_0027", {
            "operator": "alice", "shot_id": shot["shot_id"], "rep": rep,
            "claim_code": code, "value": "no, the backdrop is NOT empty"})
        assert bad == 400, (bad, out)
        assert not _confirmations(root / "garments" / "DENIM_0027")

        # and a real refusal is recorded as one, and does not clear the claim
        ok, out2 = _confirm_via_app(httpd, "DENIM_0027", {
            "operator": "alice", "shot_id": shot["shot_id"], "rep": rep,
            "claim_code": code, "value": False, "note": "there is a ruler in shot"})
        assert ok == 200, out2
    finally:
        httpd.shutdown(); httpd.server_close()

    st2, _ = Store(root / "garments" / "DENIM_0027").fold()
    rec = st2["verifications"][(shot["shot_id"], rep, claim)]
    assert rec["value"] is False
    got, why = GATES._verification_for(st2, shot["shot_id"], rep, claim)
    assert got is None and "NOT verified" in why


@pytest.mark.parametrize("bad", [1, 0, "true", "yes", None, [], {}])
def test_a_value_that_is_not_a_boolean_is_refused_rather_than_coerced(bad):
    with pytest.raises(CLAIMS.ClaimError):
        CLAIMS.payload(claim="confirmed_x", shot_id="S", rep=1, value=bad, operator="alice")


def test_a_claim_index_that_is_a_boolean_is_refused(spec, tmp_path):
    """`int(True)` is 1, so a JSON `true` posted as claim_index confirmed the frame's first claim."""
    b = _bench(spec, "DENIM_0028", str(tmp_path))
    shot, rep = _frame_with_claims(b, spec)
    st, _ = b.store.fold()
    with pytest.raises(CLAIMS.ClaimError):
        CLAIMS.resolve(st, shot["shot_id"], rep, index=True)
    assert CLAIMS.resolve(st, shot["shot_id"], rep, index=1)


def test_a_frame_that_raises_one_claim_twice_can_still_be_confirmed(spec, tmp_path):
    """A shot naming the same requirement twice raised the claim twice, `resolve` then found two
    matches for its code, and refused at BOTH doors — a duplicated line in the shot plan made a
    claim impossible to confirm."""
    b = _bench(spec, "DENIM_0029", str(tmp_path))
    shot, rep = _frame_with_claims(b, spec)
    st, _ = b.store.fold()
    q = dict(st["qa"][(shot["shot_id"], rep)])
    dup = [c for c in q["checks"] if c.get("outcome") == "HUMAN_VERIFICATION_REQUIRED"][0]
    q["checks"] = list(q["checks"]) + [dict(dup)]
    st["qa"][(shot["shot_id"], rep)] = q
    raised = CLAIMS.raised_claims(st, shot["shot_id"], rep)
    codes = [r["code"] for r in raised]
    assert len(codes) == len(set(codes)), "the same claim was offered twice"
    assert CLAIMS.resolve(st, shot["shot_id"], rep, code=raised[0]["code"]) == raised[0]["claim"]


def test_both_doors_can_reach_the_claims_that_authorise_the_cut(spec, tmp_path):
    """The three session claims the cut gate reads were reachable from the CLI and from nowhere on
    the phone — the door the operator is actually holding on cut day."""
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    b = _bench(spec, "DENIM_0030", str(root))
    sess = webapp.Session(str(root), str(root / "garments"), SPEC_PATH,
                          ROOT / "protocol" / "charuco_board.json")
    rows = sess.snapshot("DENIM_0030")["session_claims"]
    names = {r["claim"] for r in rows}
    assert names == set(CLAIMS.SESSION_CLAIMS), names
    for r in rows:
        assert r["code"] and not r["recorded"]
    assert any(r["needs_measurements"] for r in rows), "cut_marks_verified needs its two readings"

    # and the CLI's queue lists them too, so the two queues match
    env = dict(os.environ, PILOT_GARMENTS=str(root / "garments"))
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "pilot.py"), "claims",
                          "DENIM_0030"], capture_output=True, text=True, env=env).stdout
    for name in CLAIMS.SESSION_CLAIMS:
        assert name in out, "the CLI's list omits %s" % name


def test_the_web_door_records_what_it_can_actually_attest(spec, tmp_path):
    """A POST from a phone and a POST from a script are the same bytes. Recording `app` read as
    though a person had been observed."""
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    b = _bench(spec, "DENIM_0031", str(root))
    shot, rep = _frame_with_claims(b, spec)
    st, _ = b.store.fold()
    code = CLAIMS.raised_claims(st, shot["shot_id"], rep)[0]["code"]
    httpd = _serve(root)
    try:
        ok, _o = _confirm_via_app(httpd, "DENIM_0031", {
            "operator": "alice", "shot_id": shot["shot_id"], "rep": rep, "claim_code": code})
    finally:
        httpd.shutdown(); httpd.server_close()
    assert ok == 200
    rec = _confirmations(root / "garments" / "DENIM_0031")[0]
    assert rec["entry_mode"] == "app:unattested"
    assert "unattested" in (CLAIMS.payload.__doc__ or ""), (
        "payload() no longer documents what an unattested entry_mode means, and the phone "
        "writes one on every confirmation")


# -- an approval that arrives with the photograph ------------------------------------------------

def _subject_shot(b):
    for s in b.activated()[0]:
        sem = s.get("rep_semantics") or []
        if len(sem) >= 2:
            return s
    return None


def test_an_approval_that_arrives_with_the_file_does_not_clear_the_claim(spec):
    """`--confirm "<the claim's own sentence>"` and the phone's comma-separated `confirm` field
    both accept a whole claim. One non-interactive command could therefore file a photograph and
    sign off its own subject claim in the same breath -- before anyone could have looked at the
    frame, with no human_verification record anywhere in the log, and attributable to nobody when
    no operator was given. The gate then reported a confirmation that was never made."""
    from denimtwin.pilot import qa as QA
    tmp = Path(tempfile.mkdtemp(prefix="ingest_selfclear_"))
    b = Bench(tmp, spec, "DENIM_9701")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sh = _subject_shot(b)
    assert sh is not None, "no activated shot raises a per-repeat subject claim"
    claims = QA.human_claims(sh, 1)
    assert claims, "the shot raises no human claim, so this proves nothing"

    img = b.synth_for(sh, 1, relay=1)
    checks, _na = QA.check_capture(
        Path(img), sh, QA.merged_quality(spec.doc["quality_defaults"], sh), rep=1,
        operator_assertions={claims[0]: True})          # deliberately naming nobody
    got = [c for c in checks if c.check_id == "confirmed_%s" % claims[0]]
    assert got, [c.check_id for c in checks]
    assert got[0].outcome == QA.HUMAN, (
        "an approval delivered with the file recorded %s for a claim nobody had seen the frame "
        "for" % got[0].outcome)


def test_a_refusal_that_arrives_with_the_file_still_forces_a_re_take(spec):
    """The fix above must not become "ignore what the operator said". Saying "this frame does not
    show it" needs no ceremony and still forces another photograph."""
    from denimtwin.pilot import qa as QA
    tmp = Path(tempfile.mkdtemp(prefix="ingest_refusal_"))
    b = Bench(tmp, spec, "DENIM_9702")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sh = _subject_shot(b)
    assert sh is not None
    claim = QA.human_claims(sh, 1)[0]
    checks, _na = QA.check_capture(
        Path(b.synth_for(sh, 1, relay=1)), sh,
        QA.merged_quality(spec.doc["quality_defaults"], sh), rep=1,
        operator_assertions={"operator": "alice", claim: False})
    got = [c for c in checks if c.check_id == "confirmed_%s" % claim]
    assert got and got[0].outcome == QA.RETAKE, got and got[0].outcome


def test_the_gate_does_not_take_a_stored_pass_in_place_of_a_confirmation(spec):
    """captures.required_complete used to `continue` past any claim whose stored check said PASS.
    That is exactly the record the ingest self-signature wrote, so the one outcome a person could
    produce without ever seeing the photograph was also the one the gate never questioned.

    The record is built here the way the OLD code built it -- one capture, one qa_result, the
    claim's check stored PASS -- because that is the log a session run before this fix would have
    left behind, and it is still on disk when the gate reads it. It cannot be built by appending a
    second qa_result: fold() keeps the WORST verdict bound to a capture, deliberately, so a later
    PASS cannot overwrite an earlier HUMAN. That defence is why this hunk is the second lock and
    not the first, and it is also why the test has to write the first record rather than a later
    one.
    """
    from denimtwin.pilot import gates as GATES, qa as QA, subjects as SUBJ
    from denimtwin.pilot.manifest import ingest_photo, read_exif, exif_timestamp
    from denimtwin.pilot import qa_primitives as Q

    tmp = Path(tempfile.mkdtemp(prefix="stored_pass_"))
    b = Bench(tmp, spec, "DENIM_9703")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sh = _subject_shot(b)
    assert sh is not None
    cid = QA.human_claim_ids(sh, 1)[0]

    src = Path(b.synth_for(sh, 1, relay=1))
    dest, sha, _already = ingest_photo(src, b.dir / "images" / sh["state"], sh["shot_id"], 1)
    exif = read_exif(dest)
    img = Q.decode_any(dest)
    subject = SUBJ.capture_fields(sh, 1)
    b.store.append("capture",
                   {"shot_id": sh["shot_id"], "rep": 1, "path": str(dest.relative_to(b.dir)),
                    "sha256": sha, "exif": exif, "exif_ts": exif_timestamp(exif) or time.time(),
                    "width": img.shape[1], "height": img.shape[0],
                    "dhash": Q.dhash_bits(img).hex(), "state": sh["state"],
                    "region_id": sh.get("region_id"),
                    "subject_id": subject["subject_id"],
                    "subject_aspect": subject["subject_aspect"]},
                   operator="alice", setup_hash=b.setup_hash)
    st, _ = b.store.fold()
    board, bspec = b.board
    checks, na = QA.check_capture(
        dest, sh, QA.merged_quality(spec.doc["quality_defaults"], sh), rep=1, board=board,
        board_spec=bspec, image=img,
        compare_to=QA.compare_set(st, b.dir, sh["shot_id"], 1, sh, self_sha=sha,
                                  self_ts=None, board=board, board_spec=bspec),
        operator_assertions={"operator": "alice", "ruler_visible": True, "side_confirmed": True,
                             "region_confirmed": True, "relay_confirmed": True,
                             "camera_repositioned": True})
    rows = [dict(c.as_dict(), outcome=QA.PASS) if c.check_id == cid else c.as_dict()
            for c in checks]
    assert [r for r in rows if r["check_id"] == cid][0]["outcome"] == QA.PASS
    b.store.append("qa_result",
                   {"shot_id": sh["shot_id"], "rep": 1,
                    "outcome": QA.roll_up([type("C", (), {"outcome": r["outcome"]})()
                                           for r in rows]),
                    "shot_class": QA.shot_class(sh), "capture_sha256": sha,
                    "checks": rows, "not_applicable": na},
                   operator="alice")

    # Everything else about the frame answered honestly, so what is left is the one claim.
    b.resolve_humans()
    st2, _ = b.store.fold()
    assert (sh["shot_id"], 1, cid) not in st2["verifications"], \
        "the fixture confirmed the very claim it is meant to leave unconfirmed"

    v = GATES.evaluate("ready_to_cut", spec, b.store, garment_dir=b.dir, check_files=False)
    blocked = [x for x in v.blocks if x.condition == "captures.required_complete"]
    assert blocked, "captures.required_complete did not block at all"
    mine = [u for u in (blocked[0].evidence.get("unresolved") or [])
            if u.startswith("%s r1:" % sh["shot_id"])]
    assert mine, (
        "the frame whose only outstanding claim was recorded PASS at ingest was not listed as "
        "unresolved at all: %r" % (blocked[0].evidence.get("unresolved") or [])[:3])
    assert cid in mine[0], (
        "the frame is unresolved for some other reason; this claim was waved through: %s"
        % mine[0][:300])


def test_a_mistyped_session_claim_code_is_not_answered_with_a_message_about_photographs(spec):
    """Confirming a cut-day claim takes no --shot, so the per-frame listing is empty by
    construction and every failure fell through to a sentence about photographs: "no photograph has
    been accepted for None repeat None ... ingest the frame first". The operator is sent to
    `pilot.py add` for a claim that has nothing to do with any photograph."""
    tmp = Path(tempfile.mkdtemp(prefix="session_claim_msg_"))
    b = Bench(tmp, spec, "DENIM_9704")
    b.open_session()
    state, _ = b.store.fold()

    for bad in ("H0000000000", "not_a_claim_at_all"):
        try:
            CLAIMS.resolve(state, None, 1, claim=bad)
        except CLAIMS.ClaimError as e:
            msg = str(e)
        else:
            raise AssertionError("%r resolved to something" % bad)
        assert "None repeat None" not in msg, msg
        assert "pilot.py add" not in msg, (
            "a mistyped session claim sends the operator to ingest a photograph: %s" % msg)
        assert "belong to the session" in msg, msg
        for name in sorted(CLAIMS.SESSION_CLAIMS)[:1]:
            assert name in msg, "the message does not list the claims that would have worked"

    # And a real session claim still resolves, by name and by code.
    name = sorted(CLAIMS.SESSION_CLAIMS)[0]
    assert CLAIMS.resolve(state, None, 1, claim=name) == name
    assert CLAIMS.resolve(state, None, 1, code=CLAIMS.claim_code(name)) == name
