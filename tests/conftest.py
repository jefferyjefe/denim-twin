"""Says, in one place, what a test needs from outside the repository -- and what it means when it is absent.

Three things were tangled together before this file existed, and the tangle is why a run with no
garment photographs in it could look either red or green depending on which test you asked:

  1. A test that needs a gitignored mask and asserts `n >= 7` after finding none reports
     "0 >= 7" -- absent evidence wearing the costume of a failed algorithm.
  2. A test that needs a gitignored mask and loops over an empty glob asserting nothing reports
     PASSED -- absent evidence wearing the costume of a scientific result. This is the worse one.
  3. A test that calls `pytest.skip("no scored pair runs in this checkout")` gets it right, in prose
     that no other tool in the repository can read or count.

The fix is not to relax any assertion. Every threshold in this suite stays exactly where it was.
What changes is that a test now DECLARES its prerequisites:

    @pytest.mark.needs("pair_masks")
    def test_the_fallback_branch_is_the_one_that_actually_runs():
        ...

and the declaration decides the outcome by profile:

    DENIMTWIN_PROFILE=ci    absent -> UNAVAILABLE (reported as a skip, counted separately, and
                                     never allowed to read as a pass)
    DENIMTWIN_PROFILE=full  absent -> FAILURE. A full run is the scientific claim; it may not be
                                     made over data that is not there. The one exception is an
                                     opt-in resource (`network`), which stays UNAVAILABLE in every
                                     profile: a full verification is a claim about garment evidence
                                     and must remain completable offline.
    unset (dev)             absent -> UNAVAILABLE, same as ci, so a developer's local run behaves
                                     like CI unless they ask for more.

`tests/test_guards_are_not_optional.py` still holds the line it was written to hold -- a skip is a
guard that stopped running -- but it can now hold it against the thing that actually matters: an
UNCLASSIFIED skip, invented in prose at the point of use. A declared one is a line in
`src/denimtwin/prereqs.py` and a marker in a diff, which is what "a deliberate act" was supposed to
mean.

The network is handled the same way and then some: a check needing it must say
`@pytest.mark.needs("network")`, and because `network` is only ever available behind an explicit
DENIMTWIN_ALLOW_NETWORK=1, no verification profile can reach a live service. Below that, this file
also *blocks* outbound sockets for the duration of the session, so a newly-written test that forgets
to declare the dependency fails loudly here instead of silently passing on a maintainer's laptop and
hanging in CI. tests/test_review_fixes.py::test_openverse_query_returns_results was doing exactly
that: a live GET to api.openverse.org, inside the deterministic suite, passing.
"""
import json
import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from denimtwin import prereqs as P   # noqa: E402  (path must be set first)

PROFILE = os.environ.get("DENIMTWIN_PROFILE", "dev")
if PROFILE not in ("dev", "ci", "full"):
    raise SystemExit(f"DENIMTWIN_PROFILE={PROFILE!r} is not one of dev, ci, full")

# item nodeid -> [resource names] that were absent. Collected during setup, written at the end.
_UNAVAILABLE = {}


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "needs(*resources): external artefacts this test cannot run without. Names must exist in "
        "src/denimtwin/prereqs.py. Absent -> UNAVAILABLE under --profile ci, FAILURE under full.",
    )


def pytest_runtest_setup(item):
    marks = list(item.iter_markers(name="needs"))
    if not marks:
        return
    names = [n for m in marks for n in m.args]
    unknown = [n for n in names if n not in P.RESOURCES]
    if unknown:
        # A typo'd resource name must not silently become "always available".
        pytest.fail(f"unknown resource(s) in @pytest.mark.needs: {unknown}. "
                    f"Declare them in src/denimtwin/prereqs.py or fix the spelling.")
    absent = P.missing(names)
    if not absent:
        return
    _UNAVAILABLE[item.nodeid] = absent
    detail = "\n    ".join(f"{n}: {P.RESOURCES[n].what}\n      satisfy with: {P.RESOURCES[n].how}"
                           for n in absent)
    # An opt-in resource -- today that means `network` -- is never escalated to a failure, in any
    # profile. --profile full is a claim about real GARMENT evidence, not about connectivity, and a
    # scientific verification that cannot be completed offline would be a worse artefact than one
    # that can. Requiring it here would also mean a full run silently reaching out to a third party,
    # which is the behaviour the socket block below exists to prevent.
    blocking = [n for n in absent if P.RESOURCES[n].kind != "optin"]
    if PROFILE == "full" and blocking:
        pytest.fail(
            f"UNAVAILABLE[{','.join(blocking)}] -- a --profile full run is a scientific claim and "
            f"cannot be made without the evidence it rests on. This is NOT an algorithm failure; "
            f"the code under test did not execute.\n    {detail}",
            pytrace=False)
    pytest.skip(f"UNAVAILABLE[{','.join(absent)}] {P.RESOURCES[absent[0]].absent_means}")


# ---------------------------------------------------------------- outbound network
_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex


def _is_local(address):
    """Loopback and unix sockets are not "the network" -- pytest-xdist and multiprocessing use them."""
    if not isinstance(address, tuple) or not address:
        return True                       # AF_UNIX address is a str/bytes path
    host = address[0]
    return host in ("127.0.0.1", "::1", "localhost", "", "0.0.0.0", "::")


def _blocked(self, address, *a, **k):
    if _is_local(address):
        return _REAL_CONNECT(self, address, *a, **k)
    raise RuntimeError(
        f"outbound network call to {address!r} from inside the test suite. Verification is offline "
        f"by design: it must not fetch anything, least of all the all-rights-reserved photographs "
        f"this project is not licensed to redistribute. If this test genuinely needs a live service, "
        f"mark it @pytest.mark.needs('network') -- it will then be reported UNAVAILABLE rather than "
        f"run, unless a human sets DENIMTWIN_ALLOW_NETWORK=1 deliberately.")


def _blocked_ex(self, address, *a, **k):
    if _is_local(address):
        return _REAL_CONNECT_EX(self, address, *a, **k)
    _blocked(self, address)


def pytest_sessionstart(session):
    if not P.available("network"):
        socket.socket.connect = _blocked
        socket.socket.connect_ex = _blocked_ex


def pytest_sessionfinish(session, exitstatus):
    socket.socket.connect = _REAL_CONNECT
    socket.socket.connect_ex = _REAL_CONNECT_EX

    # Only when asked. tools/verify.py sets this after running the WHOLE suite; an ad-hoc
    # `pytest tests/test_wash.py` must not overwrite the committed counts with a partial run.
    dest = os.environ.get("DENIMTWIN_SUITE_JSON")
    if not dest:
        return
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    if tr is None:
        return
    n = lambda k: len(tr.stats.get(k, []))   # noqa: E731
    by_resource = {}
    for res in (r for names in _UNAVAILABLE.values() for r in names):
        by_resource[res] = by_resource.get(res, 0) + 1
    skipped = n("skipped")
    unavailable = len(_UNAVAILABLE)
    # Split out the ones a full run is entitled to refuse over. `network` is deliberately not among
    # them; see the comment in pytest_runtest_setup.
    blocking_unavailable = sum(
        1 for names in _UNAVAILABLE.values()
        if any(P.RESOURCES[r].kind != "optin" for r in names))
    payload = {
        "profile": PROFILE,
        "failed": n("failed"), "passed": n("passed"),
        "skipped": skipped, "xfailed": n("xfailed"), "error": n("error"),
        # An UNAVAILABLE is a declared, machine-readable "we did not have the evidence". An
        # unclassified skip is a test that opted out in prose. Only the second kind is a hole, and
        # test_guards_are_not_optional.py holds the line there.
        "unavailable": unavailable,
        "unavailable_blocking": blocking_unavailable,
        "unclassified_skips": skipped - unavailable,
        "unavailable_by_resource": dict(sorted(by_resource.items())),
        "unavailable_tests": sorted(_UNAVAILABLE),
    }
    p = Path(dest)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=1) + "\n")
