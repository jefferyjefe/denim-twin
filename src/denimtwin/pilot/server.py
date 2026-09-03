"""The local capture server: a phone-shaped front end for the CLI, on the standard library only.

Design constraints, in the order they mattered:

* NOTHING LEAVES THE MACHINE. There is no outbound request anywhere in this module, no CDN in the
  page it serves, and no cloud storage path. Photographs land in the garment directory that
  .gitignore already excludes, and the UI displays that directory so the owner can see where their
  photographs are rather than trusting that they are somewhere sensible.

* LOCALHOST BY DEFAULT. Binding to 0.0.0.0 puts a filesystem-writing endpoint on whatever network
  the laptop is attached to, which for a phone-driven capture session is usually a cafe or a studio
  wifi. So LAN access is opt-in, and when it is on, every request must carry a token minted for that
  session only -- including the ones that only read, because "which garments does this person own"
  is not public either.

* NO FLASK. This repository pins its environment and CI installs requirements-ci.txt; adding a web
  framework to take four routes would put a dependency in the way of every future clean-CI run.
  http.server is enough for one operator and one phone.

The token is compared with hmac.compare_digest, the static tree is served from a fixed directory
with every path resolved and checked against it, and uploads are written through the manifest's
atomic ingest rather than by this module.
"""
import hmac
import io
import json
import os
import re
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

UI_DIR = Path(__file__).resolve().parent / "ui"

#: Only these extensions are ever served from the UI directory.
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webmanifest": "application/manifest+json",
    ".ico": "image/x-icon",
}
IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
               ".heic": "image/heic", ".webp": "image/webp", ".tif": "image/tiff",
               ".tiff": "image/tiff"}

MAX_UPLOAD_BYTES = 200 * 1024 * 1024      # a 48 MP HEIC burst is nowhere near this; a runaway is
MAX_BODY_BYTES = 2 * 1024 * 1024          # non-upload JSON bodies


class NoSuchGarment(KeyError):
    """Asked about a garment this session has no directory for.

    A KeyError SUBCLASS on purpose: the two handlers that already catch KeyError around `store()`
    keep catching it first and keep their own wording, so nothing that already answers this
    question changes its answer.
    """


def _operator_missing(body, is_multipart=False):
    """Every write must name the person making it. Returns an error sentence, or None.

    The system's whole answer to "a determined operator can still confirm something untrue" is that
    the claim is attributable. On the front door the operator actually uses it was not: the shipped
    UI sent operator='' and the server took it, so the rig freeze, every calibration reading, every
    measurement, every photograph and every operator assertion in a session driven from the phone
    was recorded against nobody. An unsigned attestation is not an attestation.

    Enforced HERE rather than in each handler because that is what the last two rounds keep finding:
    a rule applied on one path and not another is a second way in.
    """
    # A body that is not an object is refused here rather than waved through. Returning None let a
    # JSON list reach a handler that immediately calls .get() on it, which is a traceback and a
    # dropped connection -- the thing this whole surface is supposed to have stopped doing.
    if not isinstance(body, dict):
        return "the body of a write must be a JSON object"
    # `fields` is the MULTIPART shape, and only the multipart path produces it. Falling back to it
    # for a JSON body meant a decoy {"fields": {"operator": "x"}} satisfied this guard while the
    # handler read b["operator"] and found nothing -- so every JSON write could be unsigned again,
    # by a caller who simply put the name in the wrong place.
    fields = body.get("fields") if is_multipart else body
    if not isinstance(fields, dict):
        return "the body of a write must be a JSON object"
    who = fields.get("operator")
    if isinstance(who, str) and who.strip():
        return None
    return ("every recorded action must name the person taking it: send a non-empty `operator`. "
            "The record is only worth what the attribution is worth.")


class Api(object):
    """What the server exposes. Kept separate from HTTP so the CLI drives the same code paths.

    Handlers are registered as (method, regex) -> callable(match, query, body) -> (status, obj).
    The CLI never goes through HTTP; both call the same underlying modules, which is what makes the
    claim "the CLI supports the entire workflow without the web interface" testable rather than
    aspirational.
    """

    def __init__(self):
        self._routes = []

    def route(self, method, pattern):
        rx = re.compile("^" + pattern + "$")

        def deco(fn):
            self._routes.append((method.upper(), rx, fn))
            return fn
        return deco

    def dispatch(self, method, path, query, body):
        for m, rx, fn in self._routes:
            if m != method.upper():
                continue
            mo = rx.match(path)
            if mo:
                if method.upper() == "POST":
                    bad = _operator_missing(body, is_multipart=path == "/api/upload")
                    if bad:
                        return 400, {"error": bad}
                try:
                    return fn(mo, query, body)
                except NoSuchGarment as e:
                    # Ten of the eleven routes reached for a garment directory that was not there
                    # and let the KeyError out of the handler, which the base handler turns into a
                    # dropped connection: the phone saw "the server closed the connection", which
                    # is what it also sees when the capture app has died. The CLI has answered this
                    # in a sentence from the start ("no such garment: %s"). Caught by TYPE, and
                    # narrowly: a blanket except here would answer "no such garment" to an internal
                    # failure on a garment that does exist, which is a reassuring sentence about
                    # the wrong thing.
                    return 404, {"error": "no such garment: %s" % (e.args[0] if e.args else "")}
        return 404, {"error": "no such endpoint", "path": path}


class _Handler(BaseHTTPRequestHandler):
    server_version = "denimtwin-pilot"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    #: Drop a connection that goes quiet. socketserver applies this to the connection socket, and
    #: BaseHTTPRequestHandler turns the resulting timeout into a closed connection rather than a
    #: stuck thread. HTTP/1.1 means keep-alive is on, so without it every tab that ever connected
    #: held a worker for the rest of the session -- and a phone on flaky wifi opens a new one each
    #: time it reconnects. Long enough for a 200 MB upload over a slow link to keep making
    #: progress between reads; short enough that an abandoned connection is gone in half a minute.
    timeout = 30

    # -- plumbing ---------------------------------------------------------------------------

    def log_message(self, fmt, *args):
        if self.server.verbose:
            super().log_message(fmt, *args)

    def _authorised(self, query):
        if not self.server.require_token:
            return True
        tok = None
        auth = self.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            tok = auth[7:]
        if tok is None:
            tok = (query.get("t") or [None])[0]
        if tok is None:
            tok = self.headers.get("X-Pilot-Token")
        if tok is None:
            cookie = self.headers.get("Cookie") or ""
            for part in cookie.split(";"):
                k, _, v = part.strip().partition("=")
                if k == "pilot_token":
                    tok = v
        if not tok:
            return False
        # compare_digest refuses a non-ASCII str and raises TypeError, and the call happens BEFORE
        # any authorisation decision -- so one query parameter from an unauthenticated client killed
        # the handler thread. Compare bytes, and treat anything unencodable as simply wrong.
        try:
            given = str(tok).encode("utf-8", "ignore")
        except Exception:                                        # noqa: BLE001
            return False
        return hmac.compare_digest(given, self.server.token.encode("utf-8"))

    def _send(self, status, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # A capture UI holding an unsent measurement must not be cached into staleness, and none of
        # this is safe to embed elsewhere.
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        # No external origin is reachable from this page. If a CDN ever creeps into the UI, it
        # breaks here rather than silently sending a request off the machine.
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data: blob:; style-src 'self' "
                         "'unsafe-inline'; script-src 'self'; connect-src 'self'; "
                         "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _static(self, rel):
        rel = rel.lstrip("/") or "index.html"
        base = self.server.ui_dir.resolve()
        try:
            p = (base / rel).resolve()
            p.relative_to(base)                     # refuses ../ and symlinks out of the tree
        except (ValueError, OSError):
            return self._send(403, {"error": "path outside the UI directory"})
        if not p.is_file():
            return self._send(404, {"error": "not found", "path": rel})
        ctype = STATIC_TYPES.get(p.suffix.lower())
        if ctype is None:
            return self._send(403, {"error": "refusing to serve %s" % p.suffix})
        self._send(200, p.read_bytes(), ctype)

    def _photo(self, query):
        """Serve a capture back to the phone for the ghost overlay. Confined to the data root."""
        rel = (query.get("p") or [""])[0]
        base = self.server.data_root.resolve()
        try:
            p = (base / rel).resolve()
            p.relative_to(base)
        except (ValueError, OSError):
            return self._send(403, {"error": "path outside the garment data directory"})
        if not p.is_file() or p.suffix.lower() not in IMAGE_TYPES:
            return self._send(404, {"error": "no such capture"})
        self._send(200, p.read_bytes(), IMAGE_TYPES[p.suffix.lower()])

    # -- verbs ------------------------------------------------------------------------------

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/healthz":                      # the only unauthenticated route: liveness only
            return self._send(200, {"ok": True, "service": "denimtwin-pilot"})
        if not self._authorised(q):
            return self._send(401, {"error": "this session needs its token. Open the URL the "
                                             "`serve` command printed, including ?t=..."})
        if u.path.startswith("/api/"):
            status, obj = self.server.api.dispatch("GET", u.path, q, None)
            return self._send(status, obj)
        if u.path == "/photo":
            return self._photo(q)
        # Handing the token to the page as a cookie means every later fetch carries it without the
        # token having to live in each URL (and therefore in the phone's history for every route).
        extra = None
        if self.server.require_token and (q.get("t") or [None])[0]:
            extra = {"Set-Cookie": "pilot_token=%s; Path=/; SameSite=Strict; HttpOnly"
                                   % self.server.token}
        if u.path in ("/", "/index.html"):
            base = self.server.ui_dir.resolve() / "index.html"
            if not base.is_file():
                return self._send(500, {"error": "UI not installed at %s" % base})
            return self._send(200, base.read_bytes(), STATIC_TYPES[".html"], extra)
        return self._static(u.path)

    do_HEAD = do_GET

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._authorised(q):
            return self._send(401, {"error": "this session needs its token"})
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        # Three defects lived in the bare int() this replaces. A non-numeric header raised out of
        # the handler -- a traceback on the console and a dropped connection where the rest of this
        # system's rule is "a refusal with a sentence, not a stack trace". A NEGATIVE header
        # compared below every size limit, so MAX_UPLOAD_BYTES and MAX_BODY_BYTES were thresholds
        # nothing could exceed. And rfile.read(-1) reads to EOF, which is not the length the client
        # declared.
        raw_len = (self.headers.get("Content-Length") or "0").strip()
        try:
            length = int(raw_len)
        except (TypeError, ValueError):
            return self._send(400, {"error": "Content-Length is not a number"})
        if length < 0:
            return self._send(400, {"error": "Content-Length cannot be negative"})
        if u.path == "/api/upload":
            if length > MAX_UPLOAD_BYTES:
                return self._send(413, {"error": "upload larger than %d bytes" % MAX_UPLOAD_BYTES})
            try:
                parts = _parse_multipart(self.rfile, self.headers, length)
            except ValueError as e:
                return self._send(400, {"error": "could not read the upload: %s" % e})
            status, obj = self.server.api.dispatch("POST", u.path, q, parts)
            return self._send(status, obj)
        if length > MAX_BODY_BYTES:
            return self._send(413, {"error": "body too large"})
        raw = self.rfile.read(length) if length else b"{}"
        def _no_constants(name):
            raise ValueError("%s is not a value this API accepts" % name)

        try:
            # Python's json accepts NaN and Infinity by default. NaN compares false against every
            # bound, so a NaN measurement slipped past a tolerance check and switched it off; and
            # canonical() refuses to serialise one, so it would break the log on write instead.
            #
            # RecursionError is caught too: json's C parser recurses per nesting level, so a body of
            # ten thousand open brackets killed the request thread outright -- no response, no log
            # line, and on a threaded server one worker gone for every such request.
            body = json.loads(raw.decode("utf-8") or "{}", parse_constant=_no_constants)
        except RecursionError:
            return self._send(400, {"error": "body is nested too deeply to parse"})
        except (ValueError, UnicodeDecodeError) as e:
            return self._send(400, {"error": "body is not acceptable JSON: %s" % e})
        if ctype not in ("application/json", ""):
            return self._send(415, {"error": "expected application/json"})
        status, obj = self.server.api.dispatch("POST", u.path, q, body)
        return self._send(status, obj)


def _parse_multipart(rfile, headers, length):
    """Minimal multipart/form-data reader: enough for one file plus text fields.

    `cgi.FieldStorage` is deprecated and gone in 3.13, and email.parser wants the whole body in
    memory as a string, which mangles binary. This reads the body once as bytes and splits on the
    boundary, which is all a single-photograph POST needs.
    """
    ctype = headers.get("Content-Type") or ""
    m = re.search(r'boundary="?([^";]+)"?', ctype)
    if not m:
        raise ValueError("no multipart boundary")
    boundary = ("--" + m.group(1)).encode("ascii")
    body = rfile.read(length)
    # A SHORT READ IS NOT A PHOTOGRAPH. read() returns what arrived, and a phone that walks out of
    # range or a wifi drop mid-upload ends the stream early -- so the body was parsed as though it
    # were complete, the truncated bytes were written out under the shot's own content-addressed
    # name, and the gate then saw a photograph present for that frame. Measured on this parser:
    # 209715200 bytes declared, 183500800 arrived, accepted silently. This is an evidence question,
    # not an availability one, and the only honest answer to half a photograph is to refuse it.
    if len(body) != length:
        raise ValueError(
            "the upload ended early: %d bytes of the %d the client declared. A truncated "
            "photograph is not a photograph -- take it again." % (len(body), length))
    out = {"files": {}, "fields": {}}
    # Walked with find() over a memoryview rather than body.split(boundary). split() built a second
    # copy of every byte of the photograph and held it for the whole loop, .partition() built a
    # third and the trailing-CRLF slice a fourth, so parsing one upload peaked at four times its
    # size in heap -- measured 4.00x by both tracemalloc and ru_maxrss at 4 MiB, 16 MiB and 64 MiB.
    # MAX_UPLOAD_BYTES caps ONE request at 200 MB and nothing counts bytes in flight, so eight
    # phones finishing together were 6.4 GB of demanded heap. Slicing a memoryview copies nothing,
    # so the only copy made per part is the one the caller keeps.
    view = memoryview(body)
    start = body.find(boundary)
    while start >= 0:
        start += len(boundary)
        nxt = body.find(boundary, start)
        stop = len(body) if nxt < 0 else nxt
        sep = body.find(b"\r\n\r\n", start, stop)
        if sep < 0:                                  # preamble, epilogue, or a headerless chunk
            start = nxt
            continue
        d0, d1 = sep + 4, stop
        if body[d1 - 2:d1] == b"\r\n":
            d1 -= 2
        disp = ""
        for line in bytes(view[start:sep]).split(b"\r\n"):
            if line.lower().startswith(b"content-disposition:"):
                disp = line.decode("latin-1", "replace")
        name = re.search(r'name="([^"]*)"', disp)
        fname = re.search(r'filename="([^"]*)"', disp)
        start = nxt
        if not name:
            continue
        if fname and fname.group(1):
            out["files"][name.group(1)] = {"filename": os.path.basename(fname.group(1)),
                                           "data": bytes(view[d0:d1])}
        else:
            out["fields"][name.group(1)] = bytes(view[d0:d1]).decode("utf-8", "replace")
    return out


class PilotServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with a ceiling on how many connections may be open at once.

    This is a local instrument, not a public server, and the failure that matters is not a breach:
    it is the capture interface becoming unavailable in the middle of a session that cannot be
    paused, because something on the network -- a scanner, a captive-portal probe, a phone
    reconnecting in a loop -- opened more connections than there are threads. The ceiling is high
    enough that the operator and their phone never approach it, and refusing past it is better than
    queueing: a refusal is visible, and an instrument that has stopped answering is not.
    """
    daemon_threads = True
    allow_reuse_address = True

    #: Concurrent connections. One operator, one phone, one laptop tab: single digits in practice.
    max_connections = 32

    #: The accept queue has to be at least as deep as the ceiling, or the ceiling is not what
    #: decides. socketserver's default is 5: connections six and beyond were reset by the OS before
    #: process_request ever ran, so the visible refusal promised above never reached the phone --
    #: it saw a connection reset, which is indistinguishable from the capture app having died
    #: mid-session. The 503 is the answer this server means to give; this is what lets it give it.
    request_queue_size = max_connections

    def __init__(self, *args, **kw):
        ThreadingHTTPServer.__init__(self, *args, **kw)
        self._slots = threading.BoundedSemaphore(self.max_connections)
        self.refused_connections = 0

    def process_request(self, request, client_address):
        if not self._slots.acquire(False):
            self.refused_connections += 1
            try:
                body = b'{"error":"too many open connections; the capture app is busy"}\n'
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\n"
                                b"Content-Type: application/json\r\n"
                                b"Content-Length: " + str(len(body)).encode() +
                                b"\r\nConnection: close\r\n\r\n" + body)
            except OSError:
                pass
            # close_request, NOT shutdown_request: nothing was acquired for this connection, and
            # releasing a BoundedSemaphore that was never acquired raises.
            self.close_request(request)
            return
        ThreadingHTTPServer.process_request(self, request, client_address)

    def shutdown_request(self, request):
        try:
            ThreadingHTTPServer.shutdown_request(self, request)
        finally:
            try:
                self._slots.release()
            except ValueError:
                pass


def lan_ip():
    """The address a phone on the same network would use. No packet is sent; connect() on UDP
    only picks a route. Returns None when there is no route rather than guessing."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))      # TEST-NET-1: reserved, unroutable, never receives anything
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def serve(api, *, data_root, host="127.0.0.1", port=8765, lan=False, ui_dir=None,
          token=None, verbose=False):
    """Start the server and return (httpd, url). Caller runs serve_forever or shutdown."""
    bind = "0.0.0.0" if lan else host
    httpd = PilotServer((bind, port), _Handler)
    httpd.api = api
    httpd.data_root = Path(data_root)
    httpd.ui_dir = Path(ui_dir or UI_DIR)
    httpd.verbose = verbose
    # A token is minted for every session. On loopback it is still required, because "only local
    # processes can reach it" is not the same as "only the operator can reach it" on a shared Mac.
    httpd.token = token or secrets.token_urlsafe(24)
    httpd.require_token = True
    shown = lan_ip() if lan else host
    url = "http://%s:%d/?t=%s" % (shown or host, httpd.server_address[1], httpd.token)
    return httpd, url
