"""What the machine running the capture app is allowed to hold at once, and who decides it.

`MAX_UPLOAD_BYTES` caps ONE upload at 200 MB. `max_connections` caps concurrent connections at 32.
Nothing counted bytes IN FLIGHT, so the server permitted, by construction, thirty-two uploads
holding their read buffers at once -- 6.4 GB of resident memory that nothing refused. Measured
against the real server over real sockets: six concurrent 200 MiB uploads all returned 200 OK with
`refused_connections=0` and 1.80 GiB resident.

The number that closes it is not the software's to pick. Every way of choosing it -- an aggregate
byte budget, a smaller upload cap, a limit on concurrent uploads distinct from connections, a
request deadline -- is a number about a machine on a bench that this repository does not describe,
and inventing one would put a threshold into the capture path that no measurement supports. It is
decision `D5` in docs/PILOT_OWNER_DECISIONS.md and it stays open.

What IS the software's to do is everything around the number:

  * ACCOUNTING. Bytes reserved before the body is read, released when the request ends however it
    ends. A budget nothing decrements is a budget that refuses everything after the first failure.
  * REFUSAL. Over budget is 503, which is the refusal the server already knows how to give, and a
    refused upload is a missing photograph, which makes the gate refuse. It cannot become a false
    READY in either direction.
  * REJECTION OF THE CONFIGURATION ITSELF, at the point where exposure would occur. Absent,
    malformed, or unsafe -- a budget smaller than one permitted upload is a server that can never
    accept a photograph at all -- must be refused where it matters, which is where the app is bound
    to a network interface an operator's phone can reach.

Loopback is deliberately left as it was. `serve` without `--lan` binds 127.0.0.1, which is the
posture every test and the self-test use, and forcing a decision there would make the decision a
tax on development rather than a gate before exposure.
"""
import os
import sys
import threading
import time

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from denimtwin.pilot import server as SRV      # noqa: E402

ENV = "PILOT_MAX_INFLIGHT_UPLOAD_BYTES"


# ---------------------------------------------------------------- the configuration
def test_an_absent_budget_is_absent_not_unlimited_and_not_a_guess():
    assert SRV.parse_inflight_budget(None) is None
    assert SRV.parse_inflight_budget("") is None
    assert SRV.parse_inflight_budget("   ") is None


@pytest.mark.parametrize("raw", ["nonsense", "12mb", "1e9", "-1", "0", "1.5", " 12 34 "])
def test_a_malformed_or_nonpositive_budget_is_refused(raw):
    with pytest.raises(ValueError) as e:
        SRV.parse_inflight_budget(raw)
    assert str(e.value), "the refusal has to say what to do instead"


def test_a_budget_smaller_than_one_permitted_upload_is_refused():
    """A server that can never accept the largest thing the protocol expects is not safer."""
    with pytest.raises(ValueError) as e:
        SRV.parse_inflight_budget(str(SRV.MAX_UPLOAD_BYTES - 1))
    assert "MAX_UPLOAD_BYTES" in str(e.value) or "single upload" in str(e.value)
    # Exactly one upload's worth is the smallest defensible budget and is accepted.
    assert SRV.parse_inflight_budget(str(SRV.MAX_UPLOAD_BYTES)) == SRV.MAX_UPLOAD_BYTES


def test_the_budget_is_read_from_the_environment_not_from_a_default(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    assert SRV.configured_inflight_budget() is None
    monkeypatch.setenv(ENV, str(SRV.MAX_UPLOAD_BYTES * 3))
    assert SRV.configured_inflight_budget() == SRV.MAX_UPLOAD_BYTES * 3


def test_no_default_ceiling_is_written_into_the_source():
    """The one thing this module must not do is answer D5 on the owner's behalf."""
    assert SRV.DEFAULT_INFLIGHT_UPLOAD_BYTES is None, (
        "a default aggregate ceiling has appeared in server.py. That number is decision D5 in "
        "docs/PILOT_OWNER_DECISIONS.md; it is a fact about a machine on a bench that this "
        "repository does not describe, and a default here is a threshold nobody measured sitting "
        "in the capture path")


# ---------------------------------------------------------------- the accounting
def test_a_budget_admits_up_to_its_limit_and_refuses_the_next():
    b = SRV.InFlightBudget(300)
    assert b.reserve(100) and b.reserve(100) and b.reserve(100)
    assert not b.reserve(1), "the budget admitted a byte past its own limit"
    assert b.in_flight == 300


def test_releasing_returns_the_capacity():
    b = SRV.InFlightBudget(300)
    b.reserve(200)
    assert not b.reserve(200)
    b.release(200)
    assert b.reserve(200), "capacity was not returned, so one refusal closes the server forever"
    assert b.in_flight == 200


def test_an_unset_budget_admits_everything_and_still_accounts():
    """Absent is absent. The counter still runs so the state is observable."""
    b = SRV.InFlightBudget(None)
    assert b.reserve(10 ** 12)
    assert b.in_flight == 10 ** 12
    b.release(10 ** 12)
    assert b.in_flight == 0


def test_release_never_drives_the_counter_below_zero():
    """A double release is a bug that would otherwise mint capacity out of nothing."""
    b = SRV.InFlightBudget(300)
    b.reserve(100)
    b.release(100)
    b.release(100)
    assert b.in_flight == 0
    assert b.reserve(300), "a double release inflated the budget"
    assert not b.reserve(1)


def test_the_accounting_is_correct_under_real_threads():
    b = SRV.InFlightBudget(10 * 100)
    admitted, refused = [], []
    barrier = threading.Barrier(40)

    def worker():
        barrier.wait()
        if b.reserve(100):
            admitted.append(1)
            b.release(100)
        else:
            refused.append(1)

    ts = [threading.Thread(target=worker) for _ in range(40)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(admitted) + len(refused) == 40
    assert b.in_flight == 0, "every reservation must be released however the request ended"
    # Some are admitted (the limit is real) and the counter is sound. How many depends on timing;
    # asserting an exact split would be asserting a scheduler.
    assert admitted, "the budget refused every one of forty 100-byte uploads against a 1000 limit"


# ---------------------------------------------------------------- the exposure point
def test_binding_to_a_network_interface_without_a_budget_is_refused(monkeypatch):
    """`--lan` is where the phone can reach it, and where an unbounded hold becomes exposure."""
    monkeypatch.delenv(ENV, raising=False)
    with pytest.raises(SRV.UnsafeExposure) as e:
        SRV.serve(api=None, data_root=ROOT, lan=True, port=0)
    msg = str(e.value)
    assert ENV in msg, "the refusal does not name the setting that would satisfy it"
    assert "PILOT_OWNER_DECISIONS" in msg, (
        "the refusal does not point at the decision it is waiting on, so the operator cannot tell "
        "an unmade decision from a bug")


def test_loopback_still_serves_with_no_budget_configured(monkeypatch):
    """Every test and the self-test bind loopback. The decision gates exposure, not development."""
    monkeypatch.delenv(ENV, raising=False)
    httpd, url = SRV.serve(api=None, data_root=ROOT, port=0)
    try:
        assert url.startswith("http://127.0.0.1:")
        assert httpd.inflight.limit is None
    finally:
        httpd.server_close()


def test_a_configured_budget_reaches_the_running_server(monkeypatch):
    # Bound to loopback deliberately: `lan=True` asks the host for its LAN address, which the
    # suite's own socket guard refuses, and the thing under test here is the plumbing from the
    # environment to the running server, not which interface it bound.
    monkeypatch.setenv(ENV, str(SRV.MAX_UPLOAD_BYTES * 2))
    httpd, _url = SRV.serve(api=None, data_root=ROOT, port=0)
    try:
        assert httpd.inflight.limit == SRV.MAX_UPLOAD_BYTES * 2
    finally:
        httpd.server_close()


def test_a_malformed_budget_is_refused_on_loopback_too(monkeypatch):
    """Absent is a decision nobody made. Malformed is a mistake, and it is a mistake everywhere."""
    monkeypatch.setenv(ENV, "not-a-number")
    with pytest.raises(ValueError):
        SRV.serve(api=None, data_root=ROOT, port=0)


# ---------------------------------------------------------------- over real sockets
def test_a_concurrent_upload_past_the_budget_is_refused_by_the_real_server(tmp_path, monkeypatch):
    """The accounting is only worth anything if it fires on the path a phone actually takes."""
    import http.client
    import json as _json

    # A budget of exactly one permitted upload: the second concurrent one must be refused. The
    # number is the smallest defensible one the parser allows, chosen HERE for a test rather than
    # written into the module -- the module still has no default.
    monkeypatch.setenv(ENV, str(SRV.MAX_UPLOAD_BYTES))

    class _Api(object):
        def dispatch(self, method, path, q, body):
            return 200, {"ok": True}

    httpd, _url = SRV.serve(api=_Api(), data_root=str(tmp_path), port=0)
    httpd.require_token = False
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        # Declare a body that consumes the whole budget once the 2x parse ratio is applied, and
        # never send it: the reservation is taken before the read, which is the property under
        # test. The socket timeout keeps the handler from waiting forever.
        declared = SRV.MAX_UPLOAD_BYTES // SRV._PARSE_PEAK_RATIO
        holder = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        holder.putrequest("POST", "/api/upload")
        holder.putheader("Content-Type", "multipart/form-data; boundary=zz")
        holder.putheader("Content-Length", str(declared))
        holder.endheaders()
        holder.send(b"--zz\r\n")            # a trickle, so the handler is inside the read

        deadline = time.time() + 5
        while httpd.inflight.in_flight == 0 and time.time() < deadline:
            time.sleep(0.02)
        assert httpd.inflight.in_flight > 0, (
            "the first upload was not accounted for at all, so nothing below tests a budget")

        second = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        second.request("POST", "/api/upload", body=b"--zz--\r\n",
                       headers={"Content-Type": "multipart/form-data; boundary=zz",
                                "Content-Length": str(declared)})
        r = second.getresponse()
        payload = r.read()
        assert r.status == 503, (
            "a second concurrent upload was admitted past the aggregate budget: %s %s"
            % (r.status, payload[:300]))
        assert b"not been recorded" in payload, (
            "the refusal does not tell the operator their photograph is not stored: %s"
            % payload[:300])
        # And it is a REFUSAL, not a record: nothing was ingested.
        assert _json.loads(payload.decode())["error"]
        second.close()

        holder.close()
        # The capacity comes back once the held request ends, or one refusal closes the door.
        deadline = time.time() + 5
        while httpd.inflight.in_flight > 0 and time.time() < deadline:
            time.sleep(0.02)
        assert httpd.inflight.in_flight == 0, (
            "the aborted upload never released its reservation, so the server would refuse every "
            "photograph from here on")
    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=5)
