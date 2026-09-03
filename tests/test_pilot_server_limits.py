"""The capture server under exhaustion, malformed input and concurrent writes.

The handler timeout and the connection ceiling were added without a test that exercises either, and
"we added a limit" is not the same claim as "the limit fires, and the slot comes back afterwards".
The failure that matters here is not a breach -- this is a local instrument on loopback -- it is the
capture interface going unavailable in the middle of a session that cannot be paused, or an
append-only log acquiring a break that makes every gate refuse for the rest of the garment's life.

Everything binds to 127.0.0.1 on an ephemeral port, which is what `tests/test_pilot_api.py` already
does; nothing here opens external network access.
"""
import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import server as SRV, spec as SPEC, webapp    # noqa: E402
from denimtwin.pilot.selftest import Bench                          # noqa: E402
from denimtwin.pilot.store import Store                             # noqa: E402


@pytest.fixture(scope="module")
def live():
    tmp = tempfile.mkdtemp(prefix="pilot_limits_")
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    b = Bench(tmp, spec, "DENIM_0021")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    # One real accepted photograph, so the immutability test below has something to try to
    # replace. A skipped check is not a passed check.
    _sh = [x for x in b.activated()[0] if x["state"] == "before"][0]
    b.add(_sh, 1, b.synth_for(_sh, 1))
    sess = webapp.Session(tmp, os.path.join(tmp, "garments"),
                          ROOT / "protocol" / "shotplan" / "shotplan.json",
                          ROOT / "protocol" / "charuco_board.json")
    httpd, _ = SRV.serve(webapp.build_api(sess), data_root=os.path.join(tmp, "garments"), port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield {"httpd": httpd, "port": httpd.server_address[1], "token": httpd.token,
               "tmp": tmp, "bench": b, "shot_id": _sh["shot_id"]}
    finally:
        httpd.shutdown(); httpd.server_close()


def _get(live, path, timeout=20):
    url = "http://127.0.0.1:%d%s%st=%s" % (live["port"], path,
                                           "&" if "?" in path else "?", live["token"])
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _post(live, path, obj, timeout=20, ctype="application/json", raw=None):
    url = "http://127.0.0.1:%d%s%st=%s" % (live["port"], path,
                                           "&" if "?" in path else "?", live["token"])
    data = raw if raw is not None else json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", ctype)
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# -- the token ---------------------------------------------------------------------------------

def test_no_route_is_reachable_without_the_token(live):
    for path in ("/api/garments", "/api/state/DENIM_0021", "/"):
        url = "http://127.0.0.1:%d%s" % (live["port"], path)
        try:
            r = urllib.request.urlopen(url, timeout=20)
            code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        assert code == 401, "%s answered %s without a token" % (path, code)


@pytest.mark.parametrize("tok", ["", "wrong", "x" * 4000, "tokén"])
def test_a_bad_token_is_refused_and_does_not_raise(live, tok):
    """compare_digest raises TypeError on a non-ASCII str, and the call happened before the check
    that would have rejected it."""
    url = "http://127.0.0.1:%d/api/index?t=%s" % (live["port"], urllib.parse.quote(tok))
    try:
        code = urllib.request.urlopen(url, timeout=20).status
    except urllib.error.HTTPError as e:
        code = e.code
    assert code == 401


def test_the_token_is_compared_in_constant_time():
    src = (ROOT / "src" / "denimtwin" / "pilot" / "server.py").read_text()
    assert "hmac.compare_digest" in src
    assert "== self.server.token" not in src


# -- sizes and malformed input ------------------------------------------------------------------

def test_a_body_over_the_json_limit_is_refused(live):
    """Refused on the DECLARED length, before the bytes are read.

    Driven over a raw socket because that is the point: the server answers 413 and closes without
    draining two megabytes, so a client that is still sending sees a broken pipe rather than a
    response. Refusing early is the correct behaviour and it is what makes the limit a limit
    instead of a note written after the allocation.
    """
    n = SRV.MAX_BODY_BYTES + 4096
    s = socket.create_connection(("127.0.0.1", live["port"]), timeout=30)
    try:
        s.sendall(b"POST /api/confirm/DENIM_0021?t=" + live["token"].encode() + b" HTTP/1.1\r\n"
                  b"Host: x\r\nContent-Type: application/json\r\n"
                  b"Content-Length: " + str(n).encode() + b"\r\nConnection: close\r\n\r\n")
        try:
            s.sendall(b"a" * n)
        except OSError:
            pass                      # the server hung up on us, which is the refusal
        head = b""
        s.settimeout(30)
        try:
            while b"\r\n\r\n" not in head:
                chunk = s.recv(4096)
                if not chunk:
                    break
                head += chunk
        except (socket.timeout, OSError):
            pass
    finally:
        s.close()
    assert b" 413 " in head, head[:300]


def test_a_content_length_that_is_not_a_number_is_refused(live):
    s = socket.create_connection(("127.0.0.1", live["port"]), timeout=20)
    try:
        s.sendall(b"POST /api/confirm/DENIM_0021?t=" + live["token"].encode() + b" HTTP/1.1\r\n"
                  b"Host: x\r\nContent-Type: application/json\r\n"
                  b"Content-Length: banana\r\nConnection: close\r\n\r\n")
        head = s.recv(200)
    finally:
        s.close()
    assert b" 400 " in head, head


def test_a_content_length_larger_than_the_body_times_out_rather_than_hanging_forever(live):
    """Headers then silence. The connection must be dropped by the handler timeout."""
    t0 = time.time()
    s = socket.create_connection(("127.0.0.1", live["port"]), timeout=SRV._Handler.timeout + 40)
    try:
        s.sendall(b"POST /api/confirm/DENIM_0021?t=" + live["token"].encode() + b" HTTP/1.1\r\n"
                  b"Host: x\r\nContent-Type: application/json\r\n"
                  b"Content-Length: 5000\r\n\r\n" + b"{")
        s.settimeout(SRV._Handler.timeout + 30)
        got = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            got += chunk
        took = time.time() - t0
    except socket.timeout:
        pytest.fail("the connection was neither answered nor dropped within the handler timeout")
    finally:
        s.close()
    # Either an error response or a clean close; what must not happen is an indefinite hold. The
    # try/except above is the real guard -- reaching this line means the loop ended -- and this
    # says so in a way that fails if the connection is instead held open to the very edge of the
    # window. `assert True` used to stand here, which reads like an assertion and is not one.
    assert took < SRV._Handler.timeout + 25, (
        "the connection was held for %.1f s against a handler timeout of %d s"
        % (took, SRV._Handler.timeout))


@pytest.mark.parametrize("body,ctype", [
    (b"not json at all", "application/json"),
    (b"", "application/json"),
    (b"[1,2,3]", "application/json"),
    (b"--nope\r\nGarbage\r\n", "multipart/form-data; boundary=nope"),
    (b"--b\r\nContent-Disposition: form-data; name=\"file\"\r\n\r\ntrunc",
     "multipart/form-data; boundary=b"),
    (b"whatever", "multipart/form-data"),
])
def test_malformed_bodies_produce_an_error_not_a_traceback(live, body, ctype):
    code, out = _post(live, "/api/upload", None, raw=body, ctype=ctype)
    assert code in (400, 404, 409, 413, 415, 422), (code, out[:200])
    assert b"Traceback" not in out
    # AND IT REACHED THE UPLOAD HANDLER. These used to POST to `/api/upload/<GARMENT>`, which is
    # not a route -- `/api/upload` reads its garment id from a multipart FIELD -- so every one of
    # these bodies was rejected as unparseable JSON before any handler ran, and the test proved
    # only that a 404-shaped path returns an error.
    assert b"not acceptable JSON" not in out, (
        "the request never reached the upload handler: %s" % out[:200])


def test_a_filename_that_tries_to_traverse_cannot_escape_the_garment_tree(live, tmp_path):
    escaped = tmp_path / "escaped.png"
    boundary = "zz"
    body = (
        "--zz\r\nContent-Disposition: form-data; name=\"garment\"\r\n\r\nDENIM_0021\r\n"
        "--zz\r\nContent-Disposition: form-data; name=\"shot_id\"\r\n\r\n" + live["shot_id"] +
        "\r\n--zz\r\nContent-Disposition: form-data; name=\"operator\"\r\n\r\nalice\r\n"
        "--zz\r\nContent-Disposition: form-data; name=\"file\"; "
        "filename=\"../../../../../.." + str(escaped) + "\"\r\n"
        "Content-Type: image/png\r\n\r\nnot-a-png\r\n--zz--\r\n").encode()
    code, out = _post(live, "/api/upload", None, raw=body,
                      ctype="multipart/form-data; boundary=" + boundary)
    # Reaching the handler is half the test. These three tests named the multipart field
    # "garment_id" while the handler reads "garment", so the upload was refused for want of a
    # garment before any of this ran and the traversal was never attempted.
    body_json = json.loads(out)
    assert "path" in body_json, (
        "the upload never reached the ingest step, so nothing tried to traverse: %s" % out[:300])
    assert not body_json["path"].startswith("/") and ".." not in body_json["path"], (
        "the file was filed at %r" % body_json["path"])
    # The traversal target is named uniquely per run, so this cannot pass because some earlier
    # process happened to leave the path clear.
    assert not escaped.exists(), "a filename escaped the garment tree to %s" % escaped
    assert code == 200, (code, out[:200])


# -- connection saturation ----------------------------------------------------------------------

def test_the_connection_ceiling_refuses_rather_than_hanging_and_gives_the_slots_back(live):
    """Saturate, confirm the refusal is a clean 503, then confirm the server still works.

    A ceiling that leaked a slot per refusal would look identical on the first test and would have
    the instrument dead by the end of a session.
    """
    httpd = live["httpd"]
    before = httpd.refused_connections
    held = []
    try:
        for _ in range(httpd.max_connections + 8):
            s = socket.create_connection(("127.0.0.1", live["port"]), timeout=20)
            held.append(s)
            # Open, headers not sent: the connection occupies a slot without completing a request.
            try:
                s.sendall(b"GET /api/garments?t=" + live["token"].encode() + b" HTTP/1.1\r\nHost: x\r\n")
            except OSError:
                pass
        refused = 0
        for s in held:
            try:
                s.settimeout(5)
                data = s.recv(64)
                if b"503" in data:
                    refused += 1
            except (socket.timeout, OSError):
                pass
        assert httpd.refused_connections > before, (
            "opening %d connections against a ceiling of %d refused none"
            % (len(held), httpd.max_connections))
        assert refused > 0, "the refusal was not a 503 the client can see"
    finally:
        for s in held:
            try:
                s.close()
            except OSError:
                pass
    # And the slots come back: the server answers normally afterwards.
    for _ in range(3):
        code, _b = _get(live, "/api/garments")
        if code == 200:
            break
    assert code == 200, "the ceiling leaked its slots; the instrument is dead after a burst"


def test_a_handler_exception_releases_its_slot(live):
    """`shutdown_request` releases in a `finally`, so a raising handler cannot consume the ceiling."""
    httpd = live["httpd"]
    seen = set()
    for _ in range(httpd.max_connections + 4):
        c, out = _post(live, "/api/upload", None, raw=b"junk",
                       ctype="multipart/form-data; boundary=nothing")
        seen.add(c)
        assert b"not acceptable JSON" not in out, (
            "the request never reached the upload handler: %s" % out[:200])
    assert seen == {400}, seen
    code, _b = _get(live, "/api/garments")
    assert code == 200, "the ceiling was consumed by failed requests"


# -- the log under concurrency and interruption ---------------------------------------------------

def test_concurrent_appends_to_one_session_keep_the_chain_intact(tmp_path):
    """The web app is a ThreadingHTTPServer: two photographs arriving together from one phone were
    enough to break the chain permanently, and the failure accused the operator of tampering."""
    g = tmp_path / "garments" / "DENIM_0022"
    g.mkdir(parents=True)
    st = Store(g)
    st.append("session_opened", {"spec_version": "1", "spec_hash": "x"})
    errors = []

    def writer(i):
        try:
            s = Store(g)
            for j in range(12):
                s.append("note", {"who": i, "n": j}, operator="t%d" % i)
        except Exception as e:                                   # noqa: BLE001
            errors.append(e)

    ts = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errors, errors
    state, problems = Store(g).fold()
    assert not problems, problems
    assert state["n_entries"] == 1 + 8 * 12
    assert len(state["notes"]) == 8 * 12


def test_a_torn_final_line_is_repaired_and_an_interior_break_is_not_hidden(tmp_path):
    g = tmp_path / "garments" / "DENIM_0023"
    g.mkdir(parents=True)
    st = Store(g)
    for i in range(4):
        st.append("note", {"n": i}, operator="alice")
    mpath = g / "pilot" / "manifest.jsonl"

    # A crash mid-append leaves an incomplete final line. It is not an entry, and appending after it
    # would chain onto nothing and make the damage permanent.
    with open(mpath, "a") as f:
        f.write('{"schema":1,"seq":4,"kind":"note","payl')
    st2 = Store(g)
    st2.append("note", {"n": "after the crash"}, operator="alice")
    state, problems = st2.fold()
    assert not problems, problems
    assert state["notes"][-1]["n"] == "after the crash"
    assert (g / "pilot" / "manifest.jsonl.torn").exists(), "the torn bytes were not kept"

    # An INTERIOR line damaged by something else is left exactly where it is, for the gate to block
    # on. A repair that deleted it would silently remove a real measurement.
    lines = mpath.read_text().splitlines()
    lines[1] = lines[1].replace('"n": 1', '"n": 999') if '"n": 1' in lines[1] else lines[1][:-5]
    mpath.write_text("\n".join(lines) + "\n")
    _state, problems2 = Store(g).fold()
    assert problems2, "an edited interior entry verified clean"


def test_an_accepted_photograph_cannot_be_replaced_through_the_server(live):
    """Evidence that has been accepted is immutable; the route may not overwrite it in place."""
    gdir = Path(live["tmp"]) / "garments" / "DENIM_0021"
    shot_id = live["shot_id"]
    imgs = list(gdir.rglob("*.png"))
    assert imgs, "the fixture accepted no photograph, so this proves nothing"
    before = imgs[0].read_bytes()
    _c, out = _post(
        live, "/api/upload", None,
        raw=("--q\r\nContent-Disposition: form-data; name=\"operator\"\r\n\r\nmallory\r\n"
             "--q\r\nContent-Disposition: form-data; name=\"garment\"\r\n\r\nDENIM_0021\r\n"
             "--q\r\nContent-Disposition: form-data; name=\"shot_id\"\r\n\r\n%s\r\n"
             "--q\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n\r\n"
             "REPLACED\r\n--q--\r\n" % (shot_id, imgs[0].name)).encode(),
        ctype="multipart/form-data; boundary=q")
    assert b"not acceptable JSON" not in out, (
        "the request never reached the upload handler: %s" % out[:200])
    assert b"needs the garment" not in out and b"no such garment" not in out, (
        "the upload was refused before the ingest step, so nothing tried to replace anything: %s"
        % out[:300])
    assert imgs[0].read_bytes() == before


# -- once-only records under concurrency ----------------------------------------------------------

@pytest.fixture()
def wash_live(tmp_path):
    """A server of its own, so the wash written here cannot disturb the module-scoped session."""
    root = str(tmp_path)
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    b = Bench(root, spec, "DENIM_0031")
    b.open_session()
    sess = webapp.Session(root, os.path.join(root, "garments"),
                          ROOT / "protocol" / "shotplan" / "shotplan.json",
                          ROOT / "protocol" / "charuco_board.json")
    httpd, _ = SRV.serve(webapp.build_api(sess), data_root=os.path.join(root, "garments"), port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield {"httpd": httpd, "port": httpd.server_address[1], "token": httpd.token,
               "tmp": root, "gid": "DENIM_0031"}
    finally:
        httpd.shutdown(); httpd.server_close()


# The self-test bench's own wash record, copied rather than re-invented: these are fixture values
# for a synthetic garment, and this test is about concurrency, not about what a wash should be.
_WASH = {"machine": "Miele W1", "location": "flat", "cycle": "cottons 30",
         "water_temp_c": 30.0, "spin_rpm": 1200.0, "detergent": "Persil",
         "detergent_ml": 35.0, "filler_load": "3 towels", "start_time": "10:00",
         "end_time": "11:30", "dryer_method": "line", "dryer_setting": "n/a",
         "dryer_minutes": 0.0, "conditioning_start": "11:30", "conditioning_end": "13:30",
         "garment_in_load": "DENIM_0031 + offcut L"}


def test_the_actual_wash_is_recorded_once_even_when_eight_requests_arrive_together(wash_live):
    """The handler folded the log, saw the slot empty and appended -- two steps, and this is a
    ThreadingHTTPServer. Eight concurrent requests all folded before any of them wrote, so all
    eight passed the once-only check and all eight appended. fold() keeps the first, so seven
    phones were told {"ok": true} for settings the log had discarded, and the deviation those seven
    would have recorded against the plan was gone with them."""
    gid = wash_live["gid"]
    code, _ = _post(wash_live, "/api/wash/%s" % gid, {"wash": _WASH, "operator": "alice"})
    assert code == 200, "the planned wash would not record, so the race below proves nothing"

    actual = dict(_WASH, water_temp_c=60)          # a real deviation: 40 planned, 60 achieved
    results, lock = [], threading.Lock()

    def fire(_i):
        c, o = _post(wash_live, "/api/wash/%s" % gid, {"wash": actual, "operator": "alice",
                                                       "actual": True})
        with lock:
            results.append((c, o))

    ts = [threading.Thread(target=fire, args=(i,)) for i in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    accepted = [c for c, _ in results if c == 200]
    assert len(results) == 8, results
    assert len(accepted) == 1, (
        "%d of 8 concurrent requests were told the actual wash was saved; the log keeps one"
        % len(accepted))
    for c, o in results:
        if c != 200:
            assert c == 409, (c, o[:200])

    store = Store(Path(wash_live["tmp"]) / "garments" / gid)
    st, problems = store.fold()
    assert not problems, problems
    assert st["wash_actual"], "no actual wash survived at all"
    assert st["wash_actual"]["water_temp_c"] == 60
    raw, _rp = store.manifest.read(verify=False)
    written = [e for e in raw if e["kind"] == "wash_actual"]
    assert len(written) == 1, (
        "%d wash_actual entries reached the log. fold() hides all but the first, so the gates were "
        "never fooled -- but the log is the evidence, and a reader cannot tell which of them the "
        "operator meant" % len(written))


def test_a_second_actual_wash_is_refused_when_it_arrives_on_its_own(wash_live):
    """The sequential path, so the concurrent test above is not the only thing holding this."""
    gid = wash_live["gid"]
    assert _post(wash_live, "/api/wash/%s" % gid, {"wash": _WASH, "operator": "a"})[0] == 200
    assert _post(wash_live, "/api/wash/%s" % gid,
                 {"wash": dict(_WASH, water_temp_c=60), "operator": "a", "actual": True})[0] == 200
    code, out = _post(wash_live, "/api/wash/%s" % gid,
                      {"wash": dict(_WASH, water_temp_c=30), "operator": "a", "actual": True})
    assert code == 409, (code, out[:200])
    st, _ = Store(Path(wash_live["tmp"]) / "garments" / gid).fold()
    assert st["wash_actual"]["water_temp_c"] == 60, "the second recording overwrote the first"


def test_a_guarded_append_is_decided_under_the_same_lock_that_serialises_the_write(tmp_path):
    """The store primitive on its own: sixteen threads racing one conditional append."""
    from denimtwin.pilot.store import Rejected
    g = tmp_path / "garments" / "DENIM_0032"
    g.mkdir(parents=True)
    Store(g).append("session_opened", {"spec_version": "1", "spec_hash": "x"})
    wins, losses = [], []
    lock = threading.Lock()

    def writer(i):
        s = Store(g)
        try:
            s.append_guarded("wash_planned", dict(_WASH, spin_rpm=1000 + i), operator="t%d" % i,
                             guard=lambda st: "already recorded" if st["wash_planned"] else None)
            with lock:
                wins.append(i)
        except Rejected:
            with lock:
                losses.append(i)

    ts = [threading.Thread(target=writer, args=(i,)) for i in range(16)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(wins) == 1, "%d of 16 guarded appends were accepted" % len(wins)
    assert len(losses) == 15
    state, problems = Store(g).fold()
    assert not problems, problems
    assert state["n_entries"] == 2, (
        "%d entries; a rejected guarded append must write nothing at all" % state["n_entries"])


@pytest.fixture()
def cut_live(tmp_path):
    """A measured garment on its own server, so a cut specification can actually be computed."""
    root = str(tmp_path)
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    b = Bench(root, spec, "DENIM_0041")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sess = webapp.Session(root, os.path.join(root, "garments"),
                          ROOT / "protocol" / "shotplan" / "shotplan.json",
                          ROOT / "protocol" / "charuco_board.json")
    httpd, _ = SRV.serve(webapp.build_api(sess), data_root=os.path.join(root, "garments"), port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield {"httpd": httpd, "port": httpd.server_address[1], "token": httpd.token,
               "tmp": root, "gid": "DENIM_0041"}
    finally:
        httpd.shutdown(); httpd.server_close()


def test_a_cut_packet_is_always_the_line_the_log_kept(cut_live):
    """A cut specification is revisable on purpose, so this is not a once-only record and fold()
    keeps the last. The defect was in the answer: the route returned the caller's OWN computation
    and a printable packet built from it, with no entry number, while the log kept whichever
    request happened to land last. Two phones posting together each received a packet, each was
    told ok, and an operator marks denim from the packet in front of them. The gate would still
    have caught it -- a later cut_spec invalidates an earlier mark verification by seq, and the
    second person's measurements are checked against the log's spec -- but only after someone had
    drawn on the garment."""
    gid = cut_live["gid"]
    results, lock = [], threading.Lock()

    def fire(i):
        c, o = _post(cut_live, "/api/cutspec/%s" % gid,
                     {"target_inseam_cm": 60.0 + i, "operator": "alice"})
        with lock:
            results.append((c, json.loads(o)))

    ts = [threading.Thread(target=fire, args=(i,)) for i in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    ok = [o for c, o in results if c == 200]
    assert len(ok) == 8, [c for c, _ in results]

    store = Store(Path(cut_live["tmp"]) / "garments" / gid)
    raw, problems = store.manifest.read(verify=False)
    assert not problems, problems
    by_seq = {e["seq"]: e for e in raw if e["kind"] == "cut_spec"}
    assert len(by_seq) == 8, "expected eight revisions in the log, found %d" % len(by_seq)

    for o in ok:
        seq = (o.get("cut_spec") or {}).get("seq")
        assert seq in by_seq, (
            "a client was handed a cut specification the log does not hold (seq=%r). Before this "
            "was fixed there was no seq at all: the answer was the request's own arithmetic."
            % seq)
        kept = by_seq[seq]["payload"]
        assert o["cut_spec"]["target_inseam_cm"] == kept["target_inseam_cm"]
        assert str(kept["target_inseam_cm"]) in "\n".join(o["packet"]) or \
            ("%.1f" % kept["target_inseam_cm"]) in "\n".join(o["packet"]), (
            "the packet does not name the target of the specification it was returned with")

    final, _ = store.fold()
    assert final["cut_spec"]["seq"] == max(by_seq), "fold() no longer keeps the last revision"


def test_a_superseded_cut_specification_says_so(cut_live):
    """Sequentially, so nothing here depends on how the threads above interleaved."""
    gid = cut_live["gid"]
    c1, o1 = _post(cut_live, "/api/cutspec/%s" % gid, {"target_inseam_cm": 60.0, "operator": "a"})
    assert c1 == 200 and not json.loads(o1).get("superseded"), o1[:200]
    c2, o2 = _post(cut_live, "/api/cutspec/%s" % gid, {"target_inseam_cm": 62.0, "operator": "a"})
    assert c2 == 200
    second = json.loads(o2)
    assert second["cut_spec"]["target_inseam_cm"] == 62.0
    assert not second.get("superseded"), "nothing superseded it; it is the line the log kept"
    assert second["cut_spec"]["seq"] > json.loads(o1)["cut_spec"]["seq"]


def test_the_accept_queue_is_at_least_as_deep_as_the_connection_ceiling():
    """The ceiling has to be the thing that refuses.

    PilotServer sets max_connections = 32 and answers a 33rd with a 503 that says the capture app
    is busy. socketserver's listen backlog defaults to 5, though, so connections six and beyond
    were reset by the OS before process_request ran: the phone saw a connection reset, which looks
    exactly like the capture app having died in the middle of a session, and the visible refusal
    the class documents never happened. It showed up here as two of eight concurrent cutspec posts
    failing to connect at all while the server was busy folding a log.

    This is asserted on the configuration rather than by racing sockets because whether a shallow
    backlog actually drops a connection depends on how fast the accept loop drains it -- the bug
    reproduces under load and hides when idle, which is the wrong way round for a regression test.
    """
    assert SRV.PilotServer.request_queue_size >= SRV.PilotServer.max_connections, (
        "the accept queue (%d) is shallower than the connection ceiling (%d), so the OS refuses "
        "before the server can" % (SRV.PilotServer.request_queue_size,
                                   SRV.PilotServer.max_connections))


def test_no_route_drops_the_connection_when_asked_about_a_garment_that_is_not_there(live):
    """Ten of the eleven routes reached for a directory that was not there and let the KeyError
    out of the handler. The base handler turns that into a closed connection, so the phone saw
    "the server closed the connection" -- which is also what it sees when the capture app has died
    mid-session. The CLI has answered this in a sentence from the start: "no such garment: %s".

    The routes are enumerated from the api object rather than listed here, so a route added later
    is covered without anyone remembering to add it.
    """
    sess = webapp.Session(live["tmp"], os.path.join(live["tmp"], "garments"),
                          ROOT / "protocol" / "shotplan" / "shotplan.json",
                          ROOT / "protocol" / "charuco_board.json")
    routes = [(m, rx.pattern) for m, rx, _fn in webapp.build_api(sess)._routes
              if "DENIM" in rx.pattern]
    assert len(routes) >= 10, "only %d routes take a garment id; this test has stopped covering " \
                              "what it was written for" % len(routes)

    dropped, answered = [], []
    for meth, pat in routes:
        path = (pat.replace("^", "").replace("$", "")
                   .replace("(DENIM_[0-9]{4})", "DENIM_9999")
                   .replace("([a-z_]+)", "ready_to_cut"))
        body = {"operator": "alice"} if meth == "POST" else None
        try:
            # _post/_get turn an HTTP error into a status; a DROPPED connection is not an HTTP
            # error and comes out of urllib as an exception, which is the failure under test.
            code, out = (_post(live, path, body) if meth == "POST" else _get(live, path))
        except Exception as e:                                   # noqa: BLE001
            dropped.append((meth, path, "%s: %s" % (type(e).__name__, e)))
            continue
        answered.append((meth, path, code))
        assert code < 500, "%s %s answered %s: %s" % (meth, path, code, out[:120])
        json.loads(out)          # a sentence the phone can render, not a stack trace

    assert not dropped, "these routes dropped the connection rather than answering: %r" % dropped
    assert len(answered) == len(routes)


def test_an_unknown_garment_is_named_in_the_answer_not_merely_refused(live):
    """A 400 about a missing field, on a garment that does not exist, sends the operator looking
    for the wrong problem."""
    code, out = _get(live, "/api/claims/DENIM_9999")
    assert code == 404, (code, out[:200])
    assert b"no such garment" in out, out[:200]

    code, out = _post(live, "/api/measure/DENIM_9999",
                      {"operator": "alice", "name": "waist_cm", "readings": [40.0, 40.1]})
    assert code == 404, (code, out[:200])
    assert b"no such garment" in out, out[:200]


def test_asking_about_a_garment_that_is_not_there_does_not_create_it(live):
    """A 404 that leaves a directory behind is worse than a traceback: the next `garments` listing
    shows a session nobody opened."""
    before = set(p.name for p in (Path(live["tmp"]) / "garments").glob("DENIM_*"))
    for path in ("/api/state/DENIM_9998", "/api/claims/DENIM_9998"):
        _get(live, path)
    _post(live, "/api/confirm/DENIM_9998", {"operator": "alice", "claim": "x", "value": True})
    after = set(p.name for p in (Path(live["tmp"]) / "garments").glob("DENIM_*"))
    assert after == before, "asking about DENIM_9998 created %r" % (after - before)


def test_the_cli_wash_cannot_write_over_a_record_that_appeared_while_it_was_asking(tmp_path):
    """The other front door, on the same once-only record.

    `pilot.py wash --actual` folded the log, checked that the actual wash was absent, and then
    asked sixteen questions before appending. The phone writes to the same log. The window was wide
    enough to walk to the machine in: the app records the actual wash, this command appends a
    second one on top and exits 0 printing "recorded, not overwritten" -- and because fold() keeps
    the first, the deviations it then writes describe a wash that never happened.

    Driven deterministically rather than by timing: the competing record is written between the
    fifteenth answer and the sixteenth, so the interleaving under test happens on every run.
    """
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    b = Bench(str(tmp_path), spec, "DENIM_0051")
    b.open_session()
    gdir = Path(tmp_path) / "garments" / "DENIM_0051"
    Store(gdir).append("wash_planned", _WASH, operator="alice")

    import subprocess
    answers = ["Miele W1", "flat", "cottons 30", "30", "1200", "Persil", "35", "3 towels",
               "10:00", "11:30", "line", "n/a", "0", "11:30", "13:30", "DENIM_0051"]
    assert len(answers) == 16, "the command asks sixteen questions"

    env = dict(os.environ, PILOT_GARMENTS=str(tmp_path / "garments"))
    p = subprocess.Popen([sys.executable, str(ROOT / "tools" / "pilot.py"),
                          "--operator", "alice", "wash", "DENIM_0051", "--actual"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, env=env, cwd=str(ROOT))
    def wait_for(needle, seconds=60):
        """Read stdout until the command has actually asked. The fold happens before the first
        question, so seeing it is what makes the interleaving below deterministic rather than a
        race against process start-up."""
        buf, deadline = "", time.time() + seconds
        while needle not in buf and time.time() < deadline:
            ch = p.stdout.read(1)
            if not ch:
                break
            buf += ch
        assert needle in buf, "the command never asked its first question:\n%s" % buf[-400:]
        return buf

    try:
        head = wait_for("washing machine make/model")
        for line in answers[:15]:
            p.stdin.write(line + "\n")
        p.stdin.flush()
        # The phone, mid-interview: the command has folded and is now asking.
        Store(gdir).append("wash_actual", dict(_WASH, water_temp_c=60.0), operator="phone")
        out, err = p.communicate(input=answers[15] + "\n", timeout=120)
        out = head + out
    finally:
        if p.poll() is None:
            p.kill()

    assert p.returncode != 0, (
        "the command reported success over a record written while it was asking:\n%s" % out)
    assert "while you were typing" in (out + err), (out + err)[-500:]

    store = Store(gdir)
    raw, problems = store.manifest.read(verify=False)
    assert not problems, problems
    written = [e for e in raw if e["kind"] == "wash_actual"]
    assert len(written) == 1, "%d wash_actual entries reached the log" % len(written)
    assert written[0]["payload"]["water_temp_c"] == 60.0, "the phone's record is not the one kept"
    devs = [e for e in raw if e["kind"] == "deviation"]
    assert not devs, (
        "%d deviation(s) were written describing the difference between the plan and a wash record "
        "the log discarded: %r" % (len(devs), [d["payload"].get("field") for d in devs]))


def test_an_upload_that_ends_early_is_refused_rather_than_ingested(live):
    """`rfile.read(length)` returns what arrived, not what was promised.

    A phone that walks out of range mid-upload ends the stream early. The parser split whatever
    bytes were there on the boundary, found a well-formed part, and handed the handler a truncated
    photograph, which was written out under the shot's own content-addressed name -- and the gate
    then saw a photograph present for that frame. Measured on the unfixed parser at production
    scale: 209715200 bytes declared, 183500800 arrived, accepted with no error.

    This is an evidence question rather than an availability one, which is why it is refused rather
    than salvaged: half a photograph is not a photograph.
    """
    gdir = Path(live["tmp"]) / "garments" / "DENIM_0021"
    before = {p.name for p in gdir.rglob("*") if p.is_file()}
    shot_id = live["shot_id"]

    body = ("--q\r\nContent-Disposition: form-data; name=\"operator\"\r\n\r\nalice\r\n"
            "--q\r\nContent-Disposition: form-data; name=\"garment\"\r\n\r\nDENIM_0021\r\n"
            "--q\r\nContent-Disposition: form-data; name=\"shot_id\"\r\n\r\n%s\r\n"
            "--q\r\nContent-Disposition: form-data; name=\"file\"; filename=\"x.png\"\r\n\r\n"
            % shot_id).encode() + b"\x89PNG\r\n\x1a\n" + b"P" * 4000 + b"\r\n--q--\r\n"
    declared = len(body) + 50000          # the client promised more than it will send

    s = socket.create_connection(("127.0.0.1", live["port"]), timeout=SRV._Handler.timeout + 40)
    try:
        s.sendall(b"POST /api/upload?t=" + live["token"].encode() + b" HTTP/1.1\r\n"
                  b"Host: x\r\nContent-Type: multipart/form-data; boundary=q\r\n"
                  b"Content-Length: " + str(declared).encode() + b"\r\nConnection: close\r\n\r\n")
        s.sendall(body)
        s.shutdown(socket.SHUT_WR)        # the phone is gone
        got = b""
        s.settimeout(SRV._Handler.timeout + 30)
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                got += chunk
        except (socket.timeout, OSError):
            pass
    finally:
        s.close()

    assert b" 400 " in got, "a truncated upload was not refused: %r" % got[:300]
    assert b"ended early" in got, got[:400]
    after = {p.name for p in gdir.rglob("*") if p.is_file()}
    assert after == before, "a truncated upload left files behind: %r" % (after - before)


def test_parsing_an_upload_does_not_cost_four_times_its_size_in_heap(tmp_path):
    """`body.split(boundary)` copied every byte of the photograph a second time and held it for the
    whole loop, `.partition()` a third and the trailing-CRLF slice a fourth: one upload peaked at
    4.00x its own size, measured at three sizes by both tracemalloc and ru_maxrss. MAX_UPLOAD_BYTES
    caps ONE request at 200 MB and nothing counts bytes in flight, so several phones finishing
    together demanded gigabytes.

    Measured, not asserted about the source: a re-write that happens to allocate just as much would
    pass a grep and fail this.
    """
    import tracemalloc
    payload = bytes(range(256)) * (8 * 1024)          # 2 MiB of incompressible-looking bytes
    body = (b"--q\r\nContent-Disposition: form-data; name=\"operator\"\r\n\r\nalice\r\n"
            b"--q\r\nContent-Disposition: form-data; name=\"file\"; filename=\"x.png\"\r\n\r\n"
            + payload + b"\r\n--q--\r\n")
    src = tmp_path / "body.bin"
    src.write_bytes(body)

    class _H(object):
        def get(self, k, default=None):
            return ("multipart/form-data; boundary=q" if k == "Content-Type" else default)

    with open(src, "rb") as fh:
        tracemalloc.start()
        parts = SRV._parse_multipart(fh, _H(), len(body))
        _cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    assert parts["files"]["file"]["data"] == payload, "the parser stopped returning the file"
    assert parts["fields"]["operator"] == "alice"
    ratio = peak / float(len(body))
    assert ratio <= 2.5, (
        "parsing a %d-byte upload peaked at %d bytes of heap (%.2fx). The body itself and the one "
        "copy handed to the caller are unavoidable; anything beyond that is a copy nobody asked "
        "for." % (len(body), peak, ratio))


@pytest.mark.parametrize("body,expect_files,expect_fields", [
    # a preamble carrying its own blank line, which a naive walk reads as a part's headers
    (b"ignore me\r\n\r\nstill preamble\r\n--q\r\nContent-Disposition: form-data; name=\"a\"\r\n\r\n1\r\n--q--\r\n",
     [], ["a"]),
    # the declared boundary never appears
    (b"--zzz\r\nContent-Disposition: form-data; name=\"a\"\r\n\r\n1\r\n--zzz--\r\n", [], []),
    # a part with no Content-Disposition at all
    (b"--q\r\nX-Other: 1\r\n\r\nvalue\r\n--q--\r\n", [], []),
    # an empty file part
    (b"--q\r\nContent-Disposition: form-data; name=\"f\"; filename=\"e.png\"\r\n\r\n\r\n--q--\r\n",
     ["f"], []),
    # a field whose value contains something that looks like a boundary but is not
    (b"--q\r\nContent-Disposition: form-data; name=\"a\"\r\n\r\n--qq\r\n--q--\r\n", [], ["a"]),
])
def test_odd_multipart_bodies_yield_nothing_the_handler_can_mistake_for_a_photograph(
        body, expect_files, expect_fields, tmp_path):
    """The shapes a fuzzer reaches and a phone does not. What matters is the DIRECTION: a parser in
    front of a lifecycle gate may return less than the old one did, never more, and it must never
    turn a preamble or an unterminated body into a file."""
    src = tmp_path / "b.bin"
    src.write_bytes(body)

    class _H(object):
        def get(self, k, default=None):
            return ("multipart/form-data; boundary=q" if k == "Content-Type" else default)

    with open(src, "rb") as fh:
        parts = SRV._parse_multipart(fh, _H(), len(body))
    assert sorted(parts["files"]) == sorted(expect_files), parts["files"].keys()
    assert sorted(parts["fields"]) == sorted(expect_fields), parts["fields"].keys()


def test_a_rig_freeze_and_its_readings_are_written_without_anything_interleaving(tmp_path):
    """The freeze and the calibration readings taken against it were N+1 separate appends.

    A reading counts only against the freeze in effect, so anything landing between them can leave
    the readings bound to a configuration that is no longer current, and `rig.calibrated` then
    blocks a rig that was measured correctly. Measured on this route before the fix: eight
    concurrent freezes, eight distinct hashes handed back, nine of ten readings orphaned.

    Asserted as CONTIGUITY rather than by racing two freezes, because a race that happens to
    serialise proves nothing: a second writer hammers the same log throughout, and the whole group
    must still land in one unbroken run. The test also checks that the second writer really was
    writing, so it cannot pass by the competition never having shown up.
    """
    root = str(tmp_path)
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    b = Bench(root, spec, "DENIM_0061")
    b.open_session()
    sess = webapp.Session(root, os.path.join(root, "garments"),
                          ROOT / "protocol" / "shotplan" / "shotplan.json",
                          ROOT / "protocol" / "charuco_board.json")
    httpd, _ = SRV.serve(webapp.build_api(sess), data_root=os.path.join(root, "garments"), port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    live = {"port": httpd.server_address[1], "token": httpd.token}
    gdir = Path(root) / "garments" / "DENIM_0061"

    from denimtwin.pilot import gates as GATES, qa as QA
    checks = [{"check": n, "outcome": QA.PASS, "detail": "read off the rig"}
              for n in GATES.REQUIRED_SETUP_CHECKS]
    for c in checks:
        if c["check"] == "board_square_measured":
            c.update(squares_spanned=5, measured_mm=100.0)
    assert len(checks) >= 5, "the fixture posts too few readings to prove anything"

    stop = threading.Event()
    wrote = []

    def hammer():
        s2 = Store(gdir)
        i = 0
        while not stop.is_set():
            s2.append("note", {"n": i, "who": "the other phone"}, operator="bob")
            wrote.append(i)
            i += 1

    t = threading.Thread(target=hammer, daemon=True)
    t.start()
    try:
        # Wait until the other writer is demonstrably running before posting, rather than counting
        # how many appends it lands DURING the post. How many it lands is a function of how fast
        # this machine is; that it is contending for the same lock is the precondition that
        # actually matters, and it is the one worth asserting.
        deadline = time.time() + 30
        while len(wrote) < 3 and time.time() < deadline:
            time.sleep(0.01)
        assert len(wrote) >= 3, (
            "the competing writer never got going, so this test never had a race to win")
        code, out = _post(live, "/api/setup/DENIM_0061",
                          {"operator": "alice", "setup": dict(b.setup), "checks": checks,
                           "reason": "frozen while another writer is going"})
        assert code == 200, (code, out[:200])
    finally:
        stop.set(); t.join(timeout=30)
        httpd.shutdown(); httpd.server_close()

    store = Store(gdir)
    raw, problems = store.manifest.read(verify=False)
    assert not problems, problems
    frozen = [e for e in raw if e["kind"] == "setup_frozen"]
    assert len(frozen) == 1, "expected exactly one freeze, found %d" % len(frozen)
    lo = frozen[0]["seq"]
    group = [e["seq"] for e in raw if e["kind"] in ("setup_frozen", "setup_check")]
    hi = max(group)
    intruders = [e for e in raw if lo < e["seq"] < hi
                 and e["kind"] not in ("setup_frozen", "setup_check")]
    assert not intruders, (
        "%d entr(ies) written by another writer landed inside the rig freeze, between the freeze at "
        "%d and its last reading at %d: %r"
        % (len(intruders), lo, hi, [(e["seq"], e["kind"]) for e in intruders[:5]]))
    assert hi - lo == len(checks), (
        "the freeze and its %d readings do not occupy one unbroken run of the log" % len(checks))


def test_a_guarded_append_does_not_wait_on_the_lock_it_is_already_holding(tmp_path):
    """flock conflicts between two file descriptors of the same file even inside one process.

    The guard runs with the exclusive write lock held and folds the log to answer its question; a
    verifying read waits up to READ_LOCK_WAIT_S for the write lock to clear before reading. So the
    guard waited for itself -- the whole two seconds, every time, with every other writer blocked
    behind it -- and then read anyway. Holding the exclusive lock is itself the proof that no writer
    is mid-append, so that wait is skipped while it is held.

    The margin is four orders of magnitude, so this is a threshold no ordinary slowness reaches.
    """
    g = tmp_path / "garments" / "DENIM_0071"
    g.mkdir(parents=True)
    s = Store(g)
    s.append("session_opened", {"spec_version": "1", "spec_hash": "x"})

    t0 = time.time()
    for i in range(3):
        s.append_guarded("note", {"n": i}, guard=lambda _st: None)
    took = time.time() - t0

    assert took < 1.0, (
        "three guarded appends took %.2f s. READ_LOCK_WAIT_S is %.1f s, and this is what it looks "
        "like when the guard is waiting for a lock its own caller holds."
        % (took, __import__("denimtwin.pilot.manifest", fromlist=["x"]).READ_LOCK_WAIT_S))
    state, problems = s.fold()
    assert not problems, problems
    assert state["n_entries"] == 4
