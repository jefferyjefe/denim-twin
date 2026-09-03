"""Every self-test scenario as a pytest case, so CI holds the line the selftest draws.

`tools/pilot.py selftest` exists for the operator: one command that says whether the system still
behaves. This file exists for CI, and it is deliberately the same scenarios rather than a parallel
set -- two suites asserting nearly the same thing is how one of them quietly stops matching the
code.

These need only numpy and OpenCV, both of which requirements-ci.txt installs, and they synthesise
their own images. So they run in the hermetic profile: no photograph, no checkpoint, no network.
"""
import sys
import shutil
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import selftest as ST   # noqa: E402
from denimtwin.pilot import spec as SPEC     # noqa: E402


@pytest.fixture(scope="module")
def results():
    s = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    tmp = Path(tempfile.mkdtemp(prefix="pilot_pytest_"))
    try:
        yield {r.name: r for r in ST.scenarios(s, tmp)}
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


SCENARIOS = [
    'fresh garment is not ready to cut',
    'unanswered questionnaire blocks the plan',
    'missing measurements block the cut',
    "a single reading does not satisfy 'two independent readings'",
    'readings outside tolerance block the cut',
    'a different photograph never lands on an existing one',
    'an interrupted upload can be retried safely',
    'a torn manifest line is detected and quarantined',
    'editing the log to fix a number breaks the hash chain',
    'a capture with no rig hash is not attributable',
    'a board printed at the wrong scale blocks the cut',
    'skipping calibration readings blocks the cut',
    'a hem series with no measured leg opening blocks, not vanishes',
    'one photograph cannot be two independent relays',
    'the same lay photographed twice is not a relay',
    'a frame with no calibration board never passes',
    'checks a photograph cannot settle ask a person',
    'a manifest entry whose photograph is gone blocks',
    'swapping the file under a manifest entry is detected',
    'a session opened under a different plan is detected',
    'no cut specification and no second person blocks',
    'a second-person measurement outside tolerance blocks',
    'hem coverage gaps are found and named',
    'the committable manifest has no absolute path and no location',
    'a log copied from another garment does not satisfy this one',
    'an appended verdict that names no photograph cannot clear a rejection',
    "a capture entry pointing at another shot's photograph is refused",
    'truncating the end of the log is detected',
    'a capture recorded with no hash is not a photograph',
    'a JSON scalar in the log is a finding, not a crash',
    "a second person's REFUSAL blocks the cut",
    'the latest cut verification wins, not the first one found',
    'a non-finite measurement cannot disable the tolerance',
    'one person cannot be their own second person',
    'a human confirmation does not carry over to a different photograph',
    'verifications recorded before a photograph do not pre-clear it',
    'four concurrent writers do not break the chain',
    'a measurement read in inches blocks even though its readings agree',
    'a garment with three tears is asked for three tear photographs',
    'a required shot that would expand to no frames blocks by name',
    'a photograph taken before the rig was frozen is not attributable to it',
    'captures split across two rig configurations block unless the change is recorded',
    'the board-square measurement refuses one square spanned',
    'the board-square measurement refuses a fractional count',
    'the board-square measurement refuses more squares than the board has',
    "a forged verdict that IMPROVES on the checker's is inert",
    "a frame's only verdict must follow from the checks stored beside it",
    'one photograph cannot satisfy two shots without a declared reuse',
    'a photograph swapped with its size and mtime restored is still detected',
    'repairing a torn tail does not delete an interior entry',
    'a reuse declaration with no re-run checks is refused',
    'a verdict backed by invented checks does not become the operative one',
    'a payload that cannot identify anything is a finding, not a crash',
    'a fabricated mean does not size the hem series or place the cut',
    'a cut verification that names nobody does not verify',
    "a capture that mislabels its own state does not count as that shot's evidence",
    'a verification naming a photograph that does not exist yet does not clear it',
    'a later verdict on the same photograph cannot improve an earlier one',
    'a capture path that leaves the garment directory is refused',
    'every state in the specification is required by some gate',
    "two offcuts from the same leg are not the protocol's pair",
    'an offcut condition the protocol does not define is refused',
    'the post-wash gate requires the wash to have been recorded',
    'the wash plan cannot be rewritten after the wash to match what happened',
    'a source that is not a photograph is refused rather than hanging',
    'a frame that satisfies the numbers and shows nothing does not pass',
    "replacing an earlier repeat invalidates the later one's relay verdict",
    'a wash plan written after the wash is not a plan',
    'a deviation that names only a field does not excuse whatever happened',
    'an offcut wash condition assigned after the wash decides nothing',
    'an answer changed to delete required frames blocks until it is explained',
    'a macro whose cloth is out of focus is refused even when its rule is sharp',
    'a motion clip can pass',
    'five photographs of one lay are not five independent re-lays',
    'a deleted entry stays visible however much is appended after it',
    'a forged verdict cannot survive the photograph it describes',
    'deleting the whole log is not the same as never having had one',
    'a fold running during an upload does not read as tampering',
    'a read gives up on the lock rather than on itself',
    'a forgery consistent within the garment directory is caught from outside it',
    'the frame that proves the jeans were not there cannot be the jeans',
    'the actual wash is written once, like the plan',
    'a cut the geometry cannot model needs someone to say they meant it',
    'a rig frame no automatic check can judge asks a person',
    'an edited shot plan can be acknowledged instead of stranding the session',
    'a corrected measurement invalidates the cut line derived from it',
    'a cut-day confirmation made before the cut line existed does not carry',
    're-computing the cut line invalidates the approval given to the old one',
    'the cut gate refuses a garment that has already been cut',
    'three tears require three photographs, each naming which tear',
    'a feature found later does not re-label the photographs already taken',
    'a replaced measurement needs a named reason; the baseline cannot be written after the cut',
    'a photograph of the uncut garment cannot arrive after the cut',
    'damage the wash caused does not require a photograph from before the wash',
    'a photograph filed against the wrong instance is refused',
    'no planned frame keeps the instance placeholder in its id',
    'a post-wash reading does not overwrite the pre-cut one',
    'a post-wash reading does not re-plan the photographs already taken',
    'the wash gate refuses a cut whose result nobody wrote down',
    'the finalize gate refuses a garment nobody re-measured after washing',
    'A COMPLETE SESSION OPENS THE WASH GATE (positive control)',
    'A COMPLETE SESSION OPENS THE FINALIZE GATE (positive control)',
    'A COMPLETE SESSION OPENS THE GATE (positive control)',
]


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario(results, name):
    r = results.get(name)
    assert r is not None, (
        "scenario %r is no longer produced by selftest.scenarios(). A scenario that disappears "
        "takes its assertion with it, so this list is checked rather than iterated." % name)
    assert r.ok, "%s\n  expected: %s\n  observed: %s" % (name, r.expectation, r.detail)


def test_every_scenario_is_listed(results):
    """The parametrised list above must not fall behind the selftest.

    A scenario added to selftest.py but not here would run for the operator and not in CI, which is
    the same class of gap as a guard that stopped running.
    """
    missing = sorted(set(results) - set(SCENARIOS))
    assert not missing, "selftest has scenarios this file does not assert: %s" % missing


def test_the_readme_quotes_the_number_of_scenarios_there_actually_are():
    """The README said 78 while the suite ran 85, and gave two different breakdowns of it
    ("sixty-five of them", "most of the sixty-three") in consecutive sentences. A count in prose
    that nothing checks is a count that drifts; this binds it to the list above, which
    test_every_scenario_is_listed already binds to the scenarios themselves."""
    import re
    readme = (ROOT / "README.md").read_text()
    m = re.search(r"selftest\s+# (\d+) scenarios", readme)
    assert m, "the README no longer states how many selftest scenarios there are"
    assert int(m.group(1)) == len(SCENARIOS), (
        "README says %s scenarios, the suite has %d" % (m.group(1), len(SCENARIOS)))


def test_the_real_plan_controls_exist_and_cannot_be_quietly_dropped():
    """The strongest evidence in the suite lives behind a switch CI does not throw.

    `ST.scenarios(spec, tmp)` -- what the fixture above calls, and what CI runs -- omits
    `want_full`, so the real-plan positive controls for all three gates and the sixteen
    single-fault negative controls run only under `tools/pilot.py selftest --full`, which takes
    over an hour and writes several gigabytes. That is a deliberate trade (CI cannot afford it) and
    it is exactly the shape of gap this file exists to close, so at minimum the controls must be
    impossible to delete without a failure here, and the names must be stated where a reader can
    check them against the run.

    This does NOT run them. It asserts they are still there to run. `docs/PILOT_OWNER_DECISIONS.md`
    records that a `--full` pass is required before a real cut and that CI does not provide one.
    """
    import inspect
    src = inspect.getsource(ST.full_plan_scenarios)
    for name in ("REAL PLAN: a complete session opens the CUT gate (positive control)",
                 "REAL PLAN: a complete session opens the WASH gate (positive control)",
                 "REAL PLAN: a complete session opens the FINALIZE gate (positive control)",
                 "REAL PLAN: the whole lifecycle was reached from the physical facts alone",
                 "REAL PLAN: the unmutated session blocks only on what disabling file checks "
                 "forces"):
        assert name in src, "the real-plan control %r is gone from full_plan_scenarios" % name

    faults = ST._fault_matrix()
    assert len(faults) >= 16, "the single-fault matrix has shrunk to %d cases" % len(faults)
    gates_covered = {f[2] for f in faults}
    assert gates_covered == {"ready_to_cut", "ready_to_wash", "ready_to_finalize"}, gates_covered
    conditions = {f[3] for f in faults}
    for must in ("captures.required_complete", "measurements.complete",
                 "measurements.revisions_explained", "cut.not_already_performed",
                 "cut.performed_recorded", "offcuts.assigned", "captures.instance_identity",
                 "annotations.identify_instances", "captures.subjects_bound",
                 "captures.state_order"):
        assert must in conditions, "no single-fault control closes %s any more" % must
    # Every case names a baseline, and only the two that exist.
    assert {f[1] for f in faults} == {"pre", "full"}, sorted({f[1] for f in faults})


def test_selftest_full_is_reachable_from_the_command_line():
    """`--full` is the only way to run the above, so the switch itself is load-bearing."""
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "pilot.py"), "selftest", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "--full" in r.stdout
