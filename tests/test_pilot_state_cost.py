"""The working screen is not the pre-cut audit.

`GET /api/state` is the one projection the phone renders and it is re-fetched after every
photograph and every confirmation. The cut gate's file conditions re-derive each recorded verdict
from the photograph itself -- a decode and a full pixel re-check per frame -- which gates.py
describes as work "the gate runs once, before something irreversible, and can afford". Running it
on the working screen made that screen cost O(captures): measured at 135 ms per already-captured
frame, so 8.2 s at 48 frames and ~28 s once the 197-frame ready_to_cut arm is complete, after every
single photograph.

The fix must not be a cache. A remembered verdict on a phone is a green banner for evidence it
never saw. So: the working screen does not run the file checks at all, and says so as a BLOCK --
unknown is not permission -- and the full check stays exactly as strict, on the route the block's
own fix text already names.
"""
import json
import os
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ.get("DENIM_SRC", str(ROOT / "src")))

from denimtwin.pilot import server as SRV, spec as SPEC, webapp     # noqa: E402
from denimtwin.pilot import qa as QA                                # noqa: E402
from denimtwin.pilot.selftest import Bench                          # noqa: E402

#: Enough frames that an O(n) re-check is unmistakably separated from an O(1) one. Small enough
#: that the fixture is not itself the slow thing.
N_FRAMES = 6


@pytest.fixture(scope="module")
def live():
    tmp = tempfile.mkdtemp(prefix="pilot_state_cost_")
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    b = Bench(tmp, spec, "DENIM_0031")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    added = 0
    for sh in b.activated()[0]:
        if added >= N_FRAMES:
            break
        if sh["state"] != "before" or sh["necessity"] not in ("required", "conditional"):
            continue
        b.add(sh, 1, b.synth_for(sh, 1))
        added += 1
    assert added == N_FRAMES, "the fixture accepted %d frames, so this proves nothing" % added
    sess = webapp.Session(tmp, os.path.join(tmp, "garments"),
                          ROOT / "protocol" / "shotplan" / "shotplan.json",
                          ROOT / "protocol" / "charuco_board.json")
    httpd, _ = SRV.serve(webapp.build_api(sess), data_root=os.path.join(tmp, "garments"), port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield {"port": httpd.server_address[1], "token": httpd.token, "n": added}
    finally:
        httpd.shutdown(); httpd.server_close()


def _get(live, path, timeout=300):
    url = "http://127.0.0.1:%d%s%st=%s" % (live["port"], path,
                                           "&" if "?" in path else "?", live["token"])
    r = urllib.request.urlopen(url, timeout=timeout)
    assert r.status == 200
    return json.loads(r.read())


class _Counter(object):
    """Counts the per-photograph re-check, whichever route it is reached from."""

    def __init__(self):
        self.n = 0
        self._real = QA.check_capture

    def __enter__(self):
        def spy(*a, **k):
            self.n += 1
            return self._real(*a, **k)
        QA.check_capture = spy
        return self

    def __exit__(self, *exc):
        QA.check_capture = self._real
        return False


def test_the_working_screen_does_not_re_check_every_photograph(live):
    """The cost of the screen must not grow with the number of frames already taken."""
    with _Counter() as c:
        _get(live, "/api/state/DENIM_0031")
    assert c.n == 0, (
        "GET /api/state re-ran the per-photograph pixel check %d times for %d accepted frames. "
        "That is the pre-cut audit, on the screen the operator refreshes after every shot."
        % (c.n, live["n"]))


def test_the_working_screen_refuses_rather_than_assuming_the_files_are_intact(live):
    """Not running the check is not passing it. Both file conditions must appear as BLOCKS."""
    g = _get(live, "/api/state/DENIM_0031")["gate"]
    assert g["ready"] is False
    blocking = {b["condition"] for b in g["blocks"]}
    satisfied = {s["condition"] for s in g["satisfied"]}
    for cond in ("captures.files_intact", "captures.verdicts_reproduce"):
        assert cond in blocking, "%s is not blocking the cheap projection: %s" % (cond, blocking)
        assert cond not in satisfied, "%s was reported SATISFIED without being run" % cond


def test_the_full_gate_is_still_reachable_and_still_re_checks_every_photograph(live):
    """The strictness is not removed, only moved off the hot path. This is the route the block's
    own fix text names, and it must still do the whole job."""
    with _Counter() as c:
        v = _get(live, "/api/gate/DENIM_0031/ready_to_cut")
    assert c.n >= live["n"], (
        "the full gate re-checked only %d of %d accepted photographs" % (c.n, live["n"]))
    assert v["ready"] is False          # the session is 6 frames into a 197-frame arm
    conds = {b["condition"] for b in v["blocks"]} | {s["condition"] for s in v["satisfied"]}
    assert "captures.verdicts_reproduce" in conds


def test_the_full_check_is_still_available_from_api_state_on_request(live):
    """The opt-in exists, so nothing that needs the audited gate has lost it."""
    with _Counter() as c:
        g = _get(live, "/api/state/DENIM_0031?files=1")["gate"]
    assert c.n >= live["n"]
    assert g["ready"] is False
