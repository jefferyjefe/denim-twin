"""The HTTP API driven the way a phone drives it, because nothing else was driving it.

`/api/upload` could not accept a single photograph -- a name was used six lines before the
function-local import that bound it, so every upload of a readable image raised UnboundLocalError
and 500'd AFTER the file had been ingested and the capture entry written. It went unnoticed because
the UI tests read state and never posted a frame, and the CLI has its own path. A front end nobody
exercises is a front end that does not work.

So these tests speak real multipart to a real server, and then feed it the malformed input a
hostile client (or a confused phone) would send.
"""
import io
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import spec as SPEC, webapp          # noqa: E402
from denimtwin.pilot.selftest import Bench                # noqa: E402
from denimtwin.pilot.server import serve                  # noqa: E402


@pytest.fixture(scope="module")
def api():
    tmp = tempfile.mkdtemp(prefix="pilot_api_")
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    b = Bench(tmp, spec, "DENIM_0003")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sess = webapp.Session(tmp, os.path.join(tmp, "garments"),
                          ROOT / "protocol" / "shotplan" / "shotplan.json",
                          ROOT / "protocol" / "charuco_board.json")
    httpd, _ = serve(webapp.build_api(sess), data_root=os.path.join(tmp, "garments"), port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield {"bench": b, "port": httpd.server_address[1], "token": httpd.token,
               "tmp": tmp, "shots": b.activated()[0]}
    finally:
        httpd.shutdown()
        httpd.server_close()


def _req(api, path, data=None, ctype=None):
    url = "http://127.0.0.1:%d%s%st=%s" % (api["port"], path,
                                           "&" if "?" in path else "?", api["token"])
    r = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if ctype:
        r.add_header("Content-Type", ctype)
    try:
        resp = urllib.request.urlopen(r, timeout=60)
        return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _json(api, path, obj):
    return _req(api, path, json.dumps(obj).encode(), "application/json")


def _multipart(fields, filepath):
    bnd = "----pilot" + uuid.uuid4().hex
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                   % (bnd, k, v)).encode())
    out.write(('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\n'
               'Content-Type: image/png\r\n\r\n' % (bnd, os.path.basename(filepath))).encode())
    out.write(open(filepath, "rb").read())
    out.write(b"\r\n")
    out.write(("--%s--\r\n" % bnd).encode())
    return out.getvalue(), "multipart/form-data; boundary=%s" % bnd


def test_a_phone_can_upload_a_photograph_and_gets_a_verdict(api):
    b, sh = api["bench"], api["shots"][0]
    body, ct = _multipart({"garment": "DENIM_0003", "shot_id": sh["shot_id"], "rep": "1",
                           "operator": "jh",
                           "confirm": "ruler_visible,side_confirmed,region_confirmed"},
                          str(b.synth_for(sh, 1)))
    status, raw = _req(api, "/api/upload", body, ct)
    assert status == 200, raw[:300]
    j = json.loads(raw)
    assert j.get("ok") is True
    assert j["outcome"] in ("PASS", "RETAKE_REQUIRED", "UNAVAILABLE_CHECK",
                            "HUMAN_VERIFICATION_REQUIRED")
    assert _req(api, "/photo?p=DENIM_0003/" + j["path"])[0] == 200


def test_an_unreadable_upload_is_refused_rather_than_crashing(api):
    junk = os.path.join(api["tmp"], "junk.jpg")
    with open(junk, "w") as f:
        f.write("this is not a photograph")
    sh = api["shots"][1]
    body, ct = _multipart({"garment": "DENIM_0003", "shot_id": sh["shot_id"], "rep": "1",
                           "operator": "jh"}, junk)
    status, raw = _req(api, "/api/upload", body, ct)
    assert status == 200, raw[:300]
    assert json.loads(raw)["outcome"] == "RETAKE_REQUIRED"


def test_feature_answers_are_coerced_to_their_declared_type(api):
    """A count arriving as "2.0" used to be stored verbatim, and then int() raised inside
    instance_count -- which the planner swallowed as zero instances, so posting a string SILENTLY
    DELETED the photographs that count required."""
    status, raw = _json(api, "/api/features/DENIM_0003",
                        {"answers": {"n_tears": "2.0"}, "operator": "jh"})
    assert status == 200, raw[:200]
    assert json.loads(raw)["answers"]["n_tears"] == 2
    assert isinstance(json.loads(raw)["answers"]["n_tears"], int)


@pytest.mark.parametrize("path,body", [
    ("/api/features/DENIM_0003", {"answers": {"n_tears": "many"}, "operator": "jh"}),
    ("/api/features/DENIM_0003", {"answers": {"not_a_feature": True}, "operator": "jh"}),
    ("/api/confirm/DENIM_0003", {"claim": "x", "rep": "two", "operator": "jh"}),
    ("/api/confirm/DENIM_0003", {"claim": "cut_marks_verified", "operator": "jh",
                                 "verifier": "bob", "measured_inseam_cm": "NaN",
                                 "measured_outseam_cm": "NaN"}),
    ("/api/setup/DENIM_0003", {"setup": {"a": 1}, "checks": [{"check": "lighting_test"}],
                               "operator": "jh"}),
    ("/api/setup/DENIM_0003", {"setup": {"a": 1},
                               "checks": [{"check": "made_up", "outcome": "PASS"}],
                               "operator": "jh"}),
    ("/api/measure/DENIM_0003", {"name": "waist_cm", "readings": ["abc", "82"], "operator": "jh"}),
    ("/api/measure/DENIM_0003", {"name": "waist_cm", "readings": [82.0], "operator": "jh"}),
])
def test_malformed_input_is_refused_at_the_boundary(api, path, body):
    status, raw = _json(api, path, body)
    assert status == 400, "accepted %r -> %s %s" % (body, status, raw[:200])


def test_the_log_still_folds_and_the_gate_still_runs_after_all_of_that(api):
    """The point of refusing at the boundary. A repeat index of "two" was written straight into the
    append-only log, and then every later fold() raised on int() -- permanently bricking a garment
    whose evidence was intact, so the gate could not be run at all."""
    state, problems = api["bench"].store.fold()
    assert not problems, problems[:3]
    status, raw = _req(api, "/api/gate/DENIM_0003/ready_to_cut")
    assert status == 200
    assert "ready" in json.loads(raw)


def test_a_non_ascii_token_is_rejected_without_killing_the_thread(api):
    """hmac.compare_digest refuses a non-ASCII str and raises, and the call happened before any
    authorisation decision -- so one query parameter from an unauthenticated client killed a
    handler thread."""
    url = "http://127.0.0.1:%d/api/garments?t=%%C3%%A9" % api["port"]
    try:
        code = urllib.request.urlopen(url, timeout=20).status
    except urllib.error.HTTPError as e:
        code = e.code
    assert code == 401
    assert _req(api, "/api/garments")[0] == 200, "the server stopped answering"


def test_state_changing_routes_need_the_token(api):
    for path in ("/api/features/DENIM_0003", "/api/confirm/DENIM_0003",
                 "/api/measure/DENIM_0003", "/api/setup/DENIM_0003"):
        url = "http://127.0.0.1:%d%s" % (api["port"], path)
        r = urllib.request.Request(url, data=b"{}", method="POST")
        r.add_header("Content-Type", "application/json")
        try:
            code = urllib.request.urlopen(r, timeout=20).status
        except urllib.error.HTTPError as e:
            code = e.code
        assert code == 401, "%s was reachable without the session token" % path


def test_a_write_without_a_name_on_it_is_refused(api):
    """The record is only worth what the attribution is worth.

    The shipped UI sent operator='' and the server took it, so a session driven from the phone --
    the front door the operator actually uses -- recorded the rig freeze, every calibration reading,
    every measurement, every photograph and every assertion against nobody.
    """
    path = "/api/features/DENIM_0003"
    code, raw = _json(api, path, {"answers": {}})
    assert code == 400 and b"operator" in raw, raw
    code, raw = _json(api, path, {"answers": {}, "operator": "   "})
    assert code == 400, "whitespace is not a name"
    code, raw = _json(api, path, {"answers": {}, "operator": "jeffery"})
    assert code == 200, raw
