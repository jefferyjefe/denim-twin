"""An approval that arrives in the same command as the photograph is not an approval.

`gates._verification_for` is this system's single statement of when a confirmation counts: an
explicit yes, from a named person, naming this file's sha256, recorded after it, not stale against
a re-described instance. `qa.check_capture` takes an `operator_assertions` dict, and both front
doors fill it from whatever the ingest request carried -- `--confirm X` on the command line, the
phone's comma-separated `confirm` field. A PASS written from that dict bypasses every one of those
five properties at once.

That was closed for the claims a shot SPELLS OUT -- the `confirmed_<sentence>` family raised by
`qa.human_claims` -- and four checks that ask exactly the same kind of question were left behind:

    ruler_visible        is the rule in frame, in the garment's plane, and readable
    garment_side         is the front (or back) the face that is up
    anatomical_region    at macro range, is this the region the plan says it is
    camera_repositioned  did the phone actually come off the mount before this repeat

Every one is a question no measurement can settle -- that is why each exists -- and every one went
straight to PASS on `assertions.get(...) is True`. Reproduced on the committed plan: eighty shots
raise `ruler_visible` and `anatomical_region` together, and

    pilot.py add <G> BEFORE.HEM.LEFT.CONSTRUCTION.MACRO <any decodable file> \\
        --confirm ruler_visible --confirm region_confirmed

turned both from HUMAN_VERIFICATION_REQUIRED to PASS in the command that delivered the file, with
no `human_verification` entry anywhere in the log, nothing bound to the photograph's hash, and --
because `operator` may be absent on the API path -- attributable to nobody.

A REFUSAL still counts. Saying "this frame does not show it" needs no ceremony and forces another
photograph, which is the safe direction.
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import qa as QA, spec as SPEC          # noqa: E402

#: The assertion key each check reads, and the check id it produces. Written out rather than
#: derived, so that renaming a key silently is a failure here.
SELF_SIGNABLE = [
    ("ruler_visible", "ruler_visible"),
    ("side_confirmed", "garment_side"),
    ("region_confirmed", "anatomical_region"),
    ("camera_repositioned", "camera_repositioned"),
]


@pytest.fixture(scope="module")
def spec():
    return SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")


@pytest.fixture(scope="module")
def frame(tmp_path_factory):
    import cv2
    d = tmp_path_factory.mktemp("frames")
    img = np.random.default_rng(0).integers(0, 255, (2000, 2000, 3)).astype("uint8")
    p = d / "frame.png"
    cv2.imwrite(str(p), img)
    return p, img


def _shot_raising(spec, check_id):
    """A real shot from the committed plan whose checks include `check_id`."""
    for s in spec.shots:
        if check_id == "ruler_visible" and (s.get("scale_reference") in ("ruler", "both")):
            return s
        if check_id == "garment_side" and s.get("garment_side") in ("front", "back"):
            return s
        if check_id == "anatomical_region" and s.get("region_id") and s.get("camera_angle") in (
                "macro_perpendicular", "side_profile", "oblique_30", "oblique_45", "handheld_free"):
            return s
        if check_id == "camera_repositioned" and s.get("reposition_camera_between_reps"):
            return s
    return None


def _run(spec, shot, frame, assertions, rep=1):
    p, img = frame
    quality = QA.merged_quality(spec.doc["quality_defaults"], shot)
    checks, _na = QA.check_capture(p, shot, quality, rep=rep, board=None, board_spec=None,
                                   image=img, compare_to=[], operator_assertions=assertions)
    return {c.check_id: c for c in checks}


@pytest.mark.parametrize("key,check_id", SELF_SIGNABLE)
def test_an_approval_delivered_with_the_photograph_does_not_pass_the_check(spec, frame, key,
                                                                          check_id):
    shot = _shot_raising(spec, check_id)
    # Not a skip. A committed plan that raises none of these is a plan where this guard has
    # silently stopped guarding anything, and that is a failure, not an absence.
    assert shot is not None, (
        "no shot in the committed plan raises %r, so this test would prove nothing" % check_id)
    rep = 2 if check_id == "camera_repositioned" else 1

    without = _run(spec, shot, frame, {"operator": "alice"}, rep=rep)
    assert check_id in without, (
        "%s does not raise %r at all, so this test is not exercising it" % (shot["shot_id"], check_id))
    assert without[check_id].outcome == QA.HUMAN, (
        "%r is not a human question in the first place; this test is aimed at the wrong check"
        % check_id)

    signed = _run(spec, shot, frame, {"operator": "alice", key: True}, rep=rep)
    assert signed[check_id].outcome != QA.PASS, (
        "`--confirm %s` turned %r into a PASS in the same command that delivered the photograph. "
        "Nobody had seen the frame, no human_verification entry exists, and nothing is bound to "
        "the file's hash -- which is every property gates._verification_for requires, bypassed by "
        "a flag." % (key, check_id))
    assert signed[check_id].outcome == QA.HUMAN, (
        "%r became %s rather than staying an unanswered human question"
        % (check_id, signed[check_id].outcome))
    assert "same command" in signed[check_id].detail, (
        "the check does not say WHY it refused the approval, so the operator will retry the same "
        "flag: %r" % signed[check_id].detail)
    assert signed[check_id].fix, "a refused approval must name what to do instead"


@pytest.mark.parametrize("key,check_id", SELF_SIGNABLE)
def test_a_refusal_delivered_with_the_photograph_still_counts(spec, frame, key, check_id):
    """Saying 'this frame does not show it' needs no ceremony and forces another photograph."""
    shot = _shot_raising(spec, check_id)
    assert shot is not None
    rep = 2 if check_id == "camera_repositioned" else 1
    refused = _run(spec, shot, frame, {"operator": "alice", key: False}, rep=rep)
    assert refused[check_id].outcome in (QA.RETAKE, QA.HUMAN), (
        "a REFUSAL arriving with the photograph produced %s. The safe direction must stay open: "
        "reporting that a frame does not show what it must is not an approval and needs no "
        "ceremony." % refused[check_id].outcome)
    assert refused[check_id].outcome != QA.PASS


def test_the_named_signer_is_carried_into_the_refusal(spec, frame):
    """Who tried to sign it in the same breath is part of the record, as it is for the claims."""
    shot = _shot_raising(spec, "ruler_visible")
    signed = _run(spec, shot, frame, {"operator": "mallory", "ruler_visible": True})
    assert "mallory" in signed["ruler_visible"].detail, (
        "the refusal does not name who supplied the self-signature: %r"
        % signed["ruler_visible"].detail)


def test_no_check_in_the_module_still_passes_on_a_bare_assertion():
    """The rule has to be structural, or the next check added re-opens the hole.

    Every place that reads `assertions.get(<key>) is True` and appends a PASS is this defect. The
    fixed sites go through one helper; a new `Check(..., PASS, ...)` written directly under such a
    branch is what this looks for.
    """
    import inspect
    import re
    src = inspect.getsource(QA.check_capture)
    lines = src.splitlines()
    offenders = []
    for i, line in enumerate(lines):
        m = re.search(r"assertions\.get\(['\"]([a-z_]+)['\"]\)\s+is\s+True", line)
        if not m:
            continue
        # Look at the next few lines for a PASS check appended under this branch.
        window = "\n".join(lines[i + 1:i + 6])
        if re.search(r"Check\(\s*['\"][a-z_]+['\"]\s*,\s*PASS", window):
            offenders.append("%s (line +%d)" % (m.group(1), i + 1))
    assert not offenders, (
        "these branches turn an assertion delivered with the photograph straight into a PASS: %s. "
        "An approval is an explicit later act over immutable evidence, not a flag on the ingest "
        "command. Route it through the same helper the other four use." % ", ".join(offenders))


def test_the_relay_confirmation_is_not_taken_from_the_ingest_request():
    """The requirement the whole repeatability arm exists for, self-signable by a flag.

    `relay_verdict` never returns PASS on geometry alone: a displacement and a decorrelated
    interior are consistent with a re-lay and do not prove the operator lifted the cloth rather
    than dragging it, so the operator's confirmation is the last step. `check_capture` read that
    step out of `assertions["relay_confirmed"]`, which is filled from the ingest request -- so
    `--confirm relay_confirmed` supplied it in the command that delivered the photograph.

    `gates.c_relays` re-derives the same verdict with `operator_confirmed=False`. The two paths
    disagreed about whether the operator's word counts, and the ingest one was the lenient one.
    """
    import inspect
    import re
    src = inspect.getsource(QA.check_capture)
    m = re.search(r"relay_verdict\((?:[^()]|\([^()]*\))*\)", src, re.S)
    assert m, "check_capture no longer calls relay_verdict; this guard is aimed at nothing"
    call = m.group(0)
    assert "operator_confirmed=False" in call.replace(" ", "").replace("\n", "").replace(
        "operator_confirmed=False", "operator_confirmed=False"), call
    assert "assertions" not in call, (
        "check_capture passes an ingest-time assertion into relay_verdict as the operator's "
        "confirmation: %s" % call)


def test_no_ingest_assertion_reaches_a_pass_by_any_route():
    """The structural guard, widened past the shape the first version of it looked for.

    The first version matched `assertions.get(X) is True` followed by `Check(..., PASS)`. The relay
    site was `bool(assertions.get('relay_confirmed'))` handed to a function that returns PASS, and
    it went straight through. A guard that only recognises the shape of the bug already found is
    the same defect one level up.
    """
    import inspect
    import re
    src = inspect.getsource(QA.check_capture)
    # Every read of the ingest assertions, minus the ones that are legitimate: `operator` is
    # attribution, and a read whose True branch does NOT reach a PASS is fine.
    reads = re.findall(r"assertions(?:\.get\(|\[)['\"]([a-z_]+)['\"]", src)
    allowed = {"operator"}
    suspicious = sorted(set(reads) - allowed)
    for key in suspicious:
        # Locate the statement and prove no PASS is reachable from it within its own branch.
        for m in re.finditer(r"^([ \t]*)(?:if|elif).*assertions(?:\.get\(|\[)['\"]%s['\"].*$"
                             % re.escape(key), src, re.M):
            indent = len(m.group(1))
            rest = src[m.end():].splitlines()
            body = []
            for line in rest:
                if line.strip() and (len(line) - len(line.lstrip())) <= indent:
                    break
                body.append(line)
            joined = "\n".join(body)
            assert not re.search(r",\s*PASS\s*,", joined), (
                "a branch reading the ingest assertion %r reaches a PASS:\n%s"
                % (key, joined[:400]))
