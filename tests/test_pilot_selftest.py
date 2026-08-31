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
    'a verdict that disagrees with its own checks is refused',
    'one photograph cannot satisfy two shots without a declared reuse',
    'a photograph swapped with its size and mtime restored is still detected',
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
