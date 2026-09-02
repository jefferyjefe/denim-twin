"""The API the phone talks to, and the projection of a session it needs to render.

Every handler here is a thin call onto the same modules `tools/pilot.py` uses. That is deliberate
and it is the reason the CLI can be called the source of truth: there is no second path into the
data, so there is no second implementation of the gate to disagree with the first.

The one thing this module owns is the PROJECTION -- assembling, in a single response, everything a
phone screen needs to show at once: the next action with its framing instructions, the region to
highlight, the coverage of every region and state, the hem loop, the quality results, the gate and
what is blocking it. It is one response rather than eight because the alternative is a screen whose
parts disagree with each other while five requests land, and a capture UI that says READY in one
panel and lists blocks in another is worse than no UI.
"""
import json
import math
import os
import re
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

from . import gates as GATES
from . import hem as HEM
from . import qa_primitives as Q
from . import plan as PLAN
from . import qa as QA
from . import spec as SPEC
from .manifest import ingest_photo, read_exif, exif_timestamp
from .server import Api, serve
from .store import Store, setup_hash, diff_planned_actual, mean_of


def _to_path(poly):
    """Region shapes may arrive as an SVG path or as a bare points list; normalise to a path."""
    poly = (poly or "").strip()
    if not poly:
        return ""
    if poly[0] in "MmLlCcQqAaZz":
        return poly
    nums = [float(x) for x in poly.replace(",", " ").split()]
    if len(nums) < 6:
        return ""
    d = "M %g %g " % (nums[0], nums[1])
    d += " ".join("L %g %g" % (nums[i], nums[i + 1]) for i in range(2, len(nums) - 1, 2))
    return d + " Z"


class Session(object):
    """One server process, one specification, many garments."""

    def __init__(self, root, garments, spec_path, board_path):
        self.root = Path(root)
        self.garments = Path(garments)
        self.spec_path = Path(spec_path)
        self.board_path = Path(board_path)
        self._spec = None
        self._board = None
        self.default_garment = None

    @property
    def spec(self):
        if self._spec is None:
            self._spec = SPEC.load(self.spec_path)
        return self._spec

    @property
    def board(self):
        if self._board is None:
            try:
                from ..capture.board import load_board
                self._board = load_board(self.board_path)
            except Exception:
                self._board = (None, None)
        return self._board

    def list_garments(self):
        return sorted(p.name for p in self.garments.glob("DENIM_*") if p.is_dir())

    # The one place a garment id becomes a directory. The route patterns check the shape of an id
    # in the URL, but /api/upload reads its id from a MULTIPART FIELD, which no route pattern ever
    # sees -- so the shape check has to live here, where every path in has to come through, rather
    # than on the way in. Containment is checked too: is_dir() alone is happy to be pointed
    # somewhere else entirely.
    def store(self, gid):
        if not re.match(r"^DENIM_[0-9]{4}$", str(gid or "")):
            raise KeyError(gid)
        d = self.garments / str(gid)
        try:
            d.resolve().relative_to(self.garments.resolve())
        except (ValueError, OSError):
            raise KeyError(gid)
        if not d.is_dir():
            raise KeyError(gid)
        return Store(d)

    # -- the projection ----------------------------------------------------------------------

    def snapshot(self, gid, *, state_filter=None):
        spec = self.spec
        gdir = self.garments / gid
        store = self.store(gid)
        st, problems = store.fold()
        try:
            # Screened exactly as the gate screens them. Handing the raw value to activate() meant
            # a leg opening of 4000 cm -- one stuck digit on a phone keypad -- expanded a hem series
            # of millions of frames and pinned the thread with no response and no timeout.
            shots, meta = PLAN.activate(spec, st["features"],
                                        GATES.plan_safe_measurements(st), st.get("cut_spec"),
                                        annotations=st.get("annotations"))
        except PLAN.PlanError as e:
            shots, meta = [], {"error": str(e), "features": st["features"],
                               "assumed_present": [], "unevaluatable_conditions": []}
        ordered = PLAN.order(spec, shots)
        done = store.done_keys()
        blocked = set()
        for (sid, rep), q in st["qa"].items():
            if q.get("outcome") == QA.RETAKE:
                blocked.add((sid, rep))
        nxt = PLAN.next_action([e for e in ordered
                                      if not state_filter or e["state"] == state_filter],
                               done, blocked)
        if nxt is None:
            nxt = PLAN.next_action(ordered, done)
        remaining = [e for e in ordered if (e["shot_id"], e["rep"]) not in done]

        # coverage by state
        by_state = {}
        for e in ordered:
            s = by_state.setdefault(e["state"], {"total": 0, "done": 0, "required": 0,
                                                 "required_done": 0, "optional": 0})
            d = (e["shot_id"], e["rep"]) in done
            s["total"] += 1
            s["done"] += int(d)
            if e["necessity"] == "optional":
                s["optional"] += 1
            else:
                s["required"] += 1
                s["required_done"] += int(d)

        # coverage by region
        by_region = {}
        for e in ordered:
            for rid in [e.get("region_id")] + list(e.get("also_covers_regions") or []):
                if not rid:
                    continue
                r = by_region.setdefault(rid, {"total": 0, "done": 0})
                r["total"] += 1
                r["done"] += int((e["shot_id"], e["rep"]) in done)

        # matched before/after
        matched = []
        by_sid = {s["shot_id"]: s for s in shots}
        companions = len(spec.companion_pairs())
        unmatched_regions = spec.unmatched_changing_regions()
        for a, b in spec.matched_pairs():
            if a not in by_sid and b not in by_sid:
                continue
            a_done = any((a, r) in done for r in range(1, 9))
            b_done = any((b, r) in done for r in range(1, 9))
            matched.append({"earlier": a, "later": b, "earlier_done": a_done,
                            "later_done": b_done,
                            "status": "complete" if a_done and b_done else
                                      ("awaiting_later" if a_done else "awaiting_earlier")})

        # hem loops
        hems = []
        lo = mean_of(st["measurements"].get("leg_opening_cm"))
        for leg in ("left", "right"):
            if lo is None:
                hems.append({"leg": leg, "available": False,
                             "why": "leg_opening_cm has not been measured, so the hem loop's "
                                    "length is unknown. Coverage is UNAVAILABLE, not complete."})
                continue
            g = HEM.HemGeometry.from_leg_opening(leg, lo)
            captured = []
            for (sid, rep) in done:
                if ".HEM." in sid and leg.upper() in sid and ".MACRO." in sid:
                    tail = sid.rsplit(".", 1)[-1]
                    if tail.startswith("P") and tail[1:].isdigit():
                        captured.append(int(tail[1:]))
            cov = g.coverage(captured)
            cov["available"] = True
            cov["macros"] = g.macros()
            nm = g.next_macro(captured)
            cov["next_macro"] = nm
            hems.append(cov)

        gate = GATES.evaluate("ready_to_cut", spec, store, garment_dir=gdir, check_files=True)
        qa_counts = {}
        for q in st["qa"].values():
            qa_counts[q.get("outcome")] = qa_counts.get(q.get("outcome"), 0) + 1

        # the ghost overlay's source, if the next action has an earlier match
        ghost = None
        if nxt:
            for m in (nxt.get("matched_shot_ids") or []):
                for r in range(1, 9):
                    cap = st["captures"].get((m, r))
                    if cap and cap.get("path"):
                        ghost = {"shot_id": m, "rep": r, "url": "/photo?p=%s/%s"
                                 % (gid, cap["path"]),
                                 "note": "capture aid only -- this overlay is never evidence"}
                        break
                if ghost:
                    break

        nxt_out = None
        if nxt:
            nxt_out = dict(nxt)
            nxt_out["quality"] = QA.merged_quality(spec.doc["quality_defaults"], nxt)
            nxt_out["region"] = spec.region_by_id.get(nxt.get("region_id"))
            key = (nxt["shot_id"], nxt["rep"])
            q = st["qa"].get(key)
            nxt_out["last_result"] = q.get("outcome") if q else None
            nxt_out["last_checks"] = (q.get("checks") if q else None)
            nxt_out["matched_captured"] = [
                {"shot_id": m, "captured": any((m, r) in done for r in range(1, 9))}
                for m in (nxt.get("matched_shot_ids") or [])]

        return {
            "garment_id": gid,
            "storage": str(gdir / "images"),
            "storage_note": "photographs stay on this machine; this directory is gitignored and "
                            "nothing here is uploaded",
            "spec_version": spec.version, "spec_hash": spec.content_hash[:12],
            "session_state": st["state"],
            "setup_hash": (st["setup_hash"] or "")[:12],
            "setup_frozen": bool(st["setup_hash"]),
            "setup_checks": st["setup_checks"],
            "features_answered": bool(st["features"]),
            "features": st["features"],
            "assumed_present": meta.get("assumed_present") or [],
            "measurements": {k: {"mean": mean_of(v), "readings": v.get("readings"),
                                 "in_tolerance": v.get("in_tolerance")}
                             for k, v in st["measurements"].items()},
            "measurements_required": GATES.REQUIRED_MEASUREMENTS,
            "next": nxt_out,
            "ghost": ghost,
            "n_total": len(ordered), "n_done": len(done & {(e["shot_id"], e["rep"]) for e in ordered}),
            "seconds_remaining": PLAN.estimate_seconds(spec, remaining),
            "by_state": by_state, "by_region": by_region,
            "matched": matched, "companion_pairs": companions,
            "unmatched_changing_regions": unmatched_regions,
            "hems": hems,
            "qa_counts": qa_counts,
            "gate": gate.as_dict(),
            "deviations": st["deviations"],
            "wash_planned": st["wash_planned"], "wash_actual": st["wash_actual"],
            "wash_deviations": diff_planned_actual(st["wash_planned"], st["wash_actual"]),
            "offcuts": st["offcuts"],
            "cut_spec": st["cut_spec"],
            "log_problems": problems,
            "upcoming": [{"shot_id": e["shot_id"], "rep": e["rep"], "state": e["state"],
                          "region_id": e.get("region_id"), "necessity": e["necessity"],
                          "est_seconds": e.get("est_seconds"),
                          "done": (e["shot_id"], e["rep"]) in done}
                         for e in ordered[:400]],
        }

    def map_data(self):
        spec = self.spec
        return {
            "viewbox": spec.regions_doc["viewbox"],
            "outlines": spec.regions_doc["outlines"],
            "left_right_convention": spec.regions_doc.get("left_right_convention", ""),
            "regions": [{"region_id": r["region_id"], "label": r["label"], "side": r["side"],
                         "group": r["group"], "d": _to_path(r["shape"]),
                         "can_change_by_cut": r["can_change_by_cut"],
                         "can_change_by_wash": r["can_change_by_wash"]}
                        for r in spec.regions],
            "states": spec.states,
        }


class BadInput(Exception):
    pass


def _num(v, name, *, allow_none=False):
    """A finite number, or a refusal naming the field.

    Everything that reaches the log or the gate goes through here. The API used to store whatever
    JSON arrived: a repeat index of "two" was written straight into the log and then every later
    fold() raised on int(), permanently bricking the garment -- the gate could no longer be run at
    all, on a garment whose evidence was intact.
    """
    if v is None or v == "":
        if allow_none:
            return None
        raise BadInput("%s is required" % name)
    # bool is an int subclass, so float(True) is 1.0 and a JSON body of [true, true, true] arrived
    # as three perfectly agreeing readings of 1.0. A measurement is a number somebody read off an
    # instrument; true is not one.
    if isinstance(v, bool):
        raise BadInput("%s must be a number, not a true/false value" % name)
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise BadInput("%s must be a number, got %r" % (name, v))
    if not math.isfinite(f):
        raise BadInput("%s must be a finite number, got %r" % (name, v))
    return f


def _int(v, name, *, allow_none=False, lo=None, hi=None):
    f = _num(v, name, allow_none=allow_none)
    if f is None:
        return None
    if f != int(f):
        raise BadInput("%s must be a whole number, got %r" % (name, v))
    i = int(f)
    if lo is not None and i < lo:
        raise BadInput("%s must be at least %d" % (name, lo))
    if hi is not None and i > hi:
        raise BadInput("%s must be at most %d" % (name, hi))
    return i


def _shot_id(v, name="shot_id", *, allow_none=False):
    if v is None:
        if allow_none:
            return None
        raise BadInput("%s is required" % name)
    v = str(v)
    if not re.fullmatch(r"[A-Z0-9_]+(\.[A-Z0-9_]+)+", v):
        raise BadInput("%s %r is not a shot id" % (name, v))
    return v


def validate_answers(spec, answers):
    """Feature answers, coerced to the type the specification declares for each key.

    An answer stored verbatim is an answer the plan will misread. A count arriving as the string
    "2.0" made instance_count()'s int() raise, which plan.activate swallowed as zero instances --
    so posting a string silently DELETED the photographs that count was supposed to require.
    """
    if not isinstance(answers, dict):
        raise BadInput("answers must be an object")
    by_key = {f["key"]: f for f in spec.features}
    out = {}
    for k, v in answers.items():
        f = by_key.get(k)
        if f is None:
            raise BadInput("%r is not a feature in this shot plan" % k)
        if v is None:
            continue
        t = f["type"]
        if t == "bool":
            if isinstance(v, bool):
                out[k] = v
            elif str(v).lower() in ("true", "yes", "y", "1"):
                out[k] = True
            elif str(v).lower() in ("false", "no", "n", "0"):
                out[k] = False
            else:
                raise BadInput("%s must be true or false, got %r" % (k, v))
        elif t == "count":
            out[k] = _int(v, k, lo=0, hi=500)
        elif t == "number":
            out[k] = _num(v, k)
        elif t == "enum":
            if str(v) not in (f.get("options") or []):
                raise BadInput("%s must be one of %s" % (k, f.get("options")))
            out[k] = str(v)
        else:
            out[k] = str(v)
    return out


#: The rig fields a freeze has to state now live in gates.py, so the CLI and the API cannot drift
#: apart on what a frozen rig is. This wrapper only translates the refusal into a 400.
REQUIRED_SETUP_FIELDS = GATES.REQUIRED_SETUP_FIELDS


def validate_setup(cfg):
    try:
        return GATES.validate_setup(cfg)
    except ValueError as e:
        raise BadInput(str(e))


def build_api(session):
    """Every handler takes (match, query, body) because the dispatcher passes all three.

    A handler names with a leading underscore whatever it does not read, so the signature says which
    parts of the request each route actually depends on -- and so that
    tests/test_no_dead_parameters.py, which exists because a keyword argument nobody reads is a lie
    to the caller, can tell a uniform signature from a forgotten one.
    """
    api = Api()

    @api.route("GET", "/api/garments")
    def _garments(_m, _q, _b):
        return 200, {"garments": session.list_garments(),
                     "default_garment": session.default_garment,
                     "spec_version": session.spec.version,
                     "spec_hash": session.spec.content_hash[:12]}

    @api.route("GET", "/api/map")
    def _map(_m, _q, _b):
        return 200, session.map_data()

    @api.route("GET", "/api/state/(DENIM_[0-9]{4})")
    def _state(m, q, _b):
        try:
            return 200, session.snapshot(m.group(1), state_filter=(q.get("state") or [None])[0])
        except KeyError:
            return 404, {"error": "no such garment"}
        except Exception as e:                  # noqa: BLE001
            # The command line wraps every command in exactly this rule and prints a sentence; this
            # handler caught KeyError alone, so anything else became a traceback on the console and
            # a DROPPED CONNECTION. /api/state is the single projection the phone renders -- next
            # action, coverage, gate, all of it -- so the app went blank with nothing to read.
            return 500, {"error": "this garment's state could not be assembled: %s: %s"
                                  % (type(e).__name__, e),
                         "fix": "run `tools/pilot.py status %s` on the Mac, which reports the same "
                                "condition as a sentence" % m.group(1)}

    @api.route("POST", "/api/features/(DENIM_[0-9]{4})")
    def _features(m, _q, b):
        try:
            answers = validate_answers(session.spec, b.get("answers") or {})
        except BadInput as e:
            return 400, {"error": str(e)}
        st = session.store(m.group(1))
        st.append("feature_answers", {"answers": answers}, operator=b.get("operator"))
        return 200, {"ok": True, "answers": answers}

    @api.route("POST", "/api/measure/(DENIM_[0-9]{4})")
    def _measure(m, _q, b):
        name = b.get("name")
        need = GATES.REQUIRED_MEASUREMENTS.get(name) or GATES.POST_WASH_MEASUREMENTS.get(name)
        if need is None:
            return 400, {"error": "%s is not a required measurement" % name}
        raw = b.get("readings")
        # A LIST, explicitly. A JSON string iterates as its characters, so "111" arrived as three
        # independent readings of 1.0 mm -- inside the plausible range, inside the tolerance, and
        # reported by the gate as "independent readings in tolerance" for evidence that was never
        # collected. The count exists precisely so the spread between separate readings can be seen.
        if not isinstance(raw, list):
            return 400, {"error": "readings must be a list of numbers, one per independent reading"}
        try:
            readings = [_num(x, "%s reading" % name) for x in raw if x not in (None, "")]
        except BadInput as e:
            return 400, {"error": str(e)}
        tol = GATES.MEASUREMENT_TOLERANCE.get(name, GATES.MEASUREMENT_TOLERANCE["_default_cm"])
        if len(readings) < need:
            return 400, {"error": "%s needs %d independent readings, got %d"
                                  % (name, need, len(readings))}
        spread = max(readings) - min(readings)
        st = session.store(m.group(1))
        # The state this reading belongs to. This route did not send one at all, so every
        # measurement taken on the phone landed in the pre-cut bucket -- including the post-wash
        # re-measurement, which then overwrote the baseline it exists to be compared with. The CLI
        # takes the state from where the log says the garment has got to, and so does this: the
        # phone is not a second set of rules.
        folded, _ = st.fold()
        ms = b.get("state") or folded["lifecycle_state"]
        st.append("measurement", {"name": name, "readings": readings,
                                  "mean": sum(readings) / len(readings), "spread": spread,
                                  "tolerance": tol, "state": ms,
                                  "in_tolerance": spread <= tol},
                  operator=b.get("operator"))
        return 200, {"ok": True, "spread": spread, "in_tolerance": spread <= tol, "state": ms}

    @api.route("POST", "/api/confirm/(DENIM_[0-9]{4})")
    def _confirm(m, _q, b):
        if not b.get("operator"):
            return 400, {"error": "a human verification needs a name on it"}
        if not b.get("claim"):
            return 400, {"error": "a verification must say what it verifies"}
        try:
            rep_ = _int(b.get("rep"), "rep", allow_none=True, lo=1, hi=99)
            shot_ = _shot_id(b.get("shot_id"), allow_none=True)
            mi = _num(b.get("measured_inseam_cm"), "measured_inseam_cm", allow_none=True)
            mo = _num(b.get("measured_outseam_cm"), "measured_outseam_cm", allow_none=True)
        except BadInput as e:
            return 400, {"error": str(e)}
        st = session.store(m.group(1))
        # Bind it to the photograph it is about, so re-ingesting a different frame under the same
        # shot id cannot inherit the confirmation.
        cap_sha = b.get("capture_sha256")
        if cap_sha is None and shot_:
            st_, _ = st.fold()
            cap = st_["captures"].get((shot_, rep_ or 1))
            cap_sha = (cap or {}).get("sha256")
        st.append("human_verification",
                  {"shot_id": shot_, "rep": rep_, "claim": str(b.get("claim")),
                   "value": bool(b.get("value", True)), "note": b.get("note"),
                   "verifier_name": b.get("verifier") or b.get("operator"),
                   "operator": b.get("operator"), "capture_sha256": cap_sha,
                   "measured_inseam_cm": mi, "measured_outseam_cm": mo},
                  operator=b.get("operator"))
        return 200, {"ok": True}

    @api.route("POST", "/api/setup/(DENIM_[0-9]{4})")
    def _setup(m, _q, b):
        st = session.store(m.group(1))
        try:
            cfg = validate_setup(b.get("setup") or {})
        except BadInput as e:
            return 400, {"error": str(e)}
        h = setup_hash(cfg)
        # VALIDATE EVERYTHING, THEN WRITE. The freeze used to be appended first, so a malformed
        # calibration reading returned 400 -- the API saying nothing happened -- with the rig
        # already silently re-frozen under the configuration the caller supplied and the server then
        # refused. Because a reading only counts against the freeze in effect, that orphaned every
        # calibration reading in the session at once and turned a READY garment into NOT READY.
        # A rejected request must leave the log exactly as it found it.
        checks_ok = []
        for c in (b.get("checks") or []):
            if not isinstance(c, dict):
                return 400, {"error": "each check must be an object"}
            name = c.get("check")
            if name not in GATES.REQUIRED_SETUP_CHECKS:
                return 400, {"error": "%r is not a calibration reading this gate knows; it must be "
                                      "one of %s" % (name, ", ".join(GATES.REQUIRED_SETUP_CHECKS))}
            if c.get("outcome") not in (QA.PASS, QA.RETAKE, QA.UNAVAILABLE, QA.HUMAN):
                return 400, {"error": "check %r must record an explicit outcome" % name}
            if name == "board_square_measured":
                try:
                    c = dict(c, squares_spanned=_int(c.get("squares_spanned"),
                                                     "squares_spanned", lo=1, hi=200),
                             measured_mm=_num(c.get("measured_mm"), "measured_mm"))
                except BadInput as e:
                    return 400, {"error": str(e)}
            checks_ok.append(c)
        st.append("setup_frozen", {"setup": cfg, "setup_hash": h,
                                   "reason": b.get("reason") or "frozen from the app"},
                  operator=b.get("operator"))
        for c in checks_ok:
            st.append("setup_check", c, operator=b.get("operator"), setup_hash=h)
        return 200, {"ok": True, "setup_hash": h}

    @api.route("POST", "/api/upload")
    def _upload(_m, _q, b):
        fields = b.get("fields") or {}
        files = b.get("files") or {}
        gid = fields.get("garment")
        shot_id = fields.get("shot_id")
        try:
            rep = _int(fields.get("rep") or 1, "rep", lo=1, hi=99)
            shot_id = _shot_id(shot_id)
        except BadInput as e:
            return 400, {"error": str(e)}
        if not gid or not shot_id or not files:
            return 400, {"error": "garment, shot_id and a file are required"}
        try:
            store = session.store(gid)
        except KeyError:
            return 404, {"error": "no such garment"}
        gdir = session.garments / gid
        st, _ = store.fold()
        spec = session.spec
        try:
            shots, _m = PLAN.activate(spec, st["features"],
                                      GATES.plan_safe_measurements(st), st.get("cut_spec"),
                                      annotations=st.get("annotations"))
        except PLAN.PlanError as e:
            return 400, {"error": str(e)}
        shot = {s["shot_id"]: s for s in shots}.get(shot_id)
        if shot is None:
            return 400, {"error": "%s is not an activated shot for this garment" % shot_id}
        name, blob = list(files.items())[0]
        tmp = gdir / "pilot" / ".incoming"
        tmp.mkdir(parents=True, exist_ok=True)
        ext = os.path.splitext(blob.get("filename") or "capture.jpg")[1].lower() or ".jpg"
        # One staging path per REQUEST. A single fixed path per garment meant two photographs
        # arriving together -- which is what a phone does when the operator taps twice, and the
        # server is threaded -- wrote over each other, so one frame could be ingested under the
        # other's shot id, or spliced from both.
        fd, stage_name = tempfile.mkstemp(dir=str(tmp), prefix="upload-", suffix=ext)
        stage = Path(stage_name)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(blob["data"])
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            try:
                os.unlink(stage_name)
            except OSError:
                pass
            raise
        dest_dir = gdir / "images" / shot["state"]
        dest, sha, already = ingest_photo(stage, dest_dir, shot_id, rep, move=True)
        rel = str(dest.relative_to(gdir))
        exif = read_exif(dest)
        ts = exif_timestamp(exif)
        import cv2
        img = cv2.imread(str(dest))
        h_, w_ = (img.shape[:2] if img is not None else (None, None))
        store.append("capture", {"shot_id": shot_id, "rep": rep, "path": rel, "sha256": sha,
                                 "exif": exif, "exif_ts": ts, "width": w_, "height": h_,
                                 "dhash": Q.dhash_bits(img).hex() if img is not None else None,
                                 "state": shot["state"], "region_id": shot.get("region_id"),
                                 # The same five identity fields the CLI records. The phone is how
                                 # the frames are actually taken in the room, and this path was
                                 # dropping exactly the fields the annotation mechanism exists to
                                 # record -- so every photograph taken through the navigator's own
                                 # UI had no recorded subject at all.
                                 "instance_index": shot.get("instance_index"),
                                 "instance_total": shot.get("instance_total"),
                                 "annotation_id": shot.get("annotation_id"),
                                 "annotation_type": shot.get("annotation_type"),
                                 "annotation_location": shot.get("annotation_location"),
                                 "already_present": already},
                     operator=fields.get("operator"), setup_hash=st["setup_hash"])
        board, bspec = session.board
        quality = QA.merged_quality(spec.doc["quality_defaults"], shot)
        # One implementation, in qa.compare_set: this path had its own copy, and a comparison that
        # exists on the command line and not here is the shape of the last round's finding.
        compare = QA.compare_set(st, gdir, shot_id, rep, shot, self_sha=sha, self_ts=ts,
                                   board=board, board_spec=bspec)
        assertions = {"operator": fields.get("operator")}
        for k in (fields.get("confirm") or "").split(","):
            if k.strip():
                assertions[k.strip()] = True
        checks, na = QA.check_capture(dest, shot, quality, rep=rep, board=board,
                                      board_spec=bspec, image=img, compare_to=compare,
                                      operator_assertions=assertions)
        outcome = QA.roll_up(checks)
        store.append("qa_result", {"shot_id": shot_id, "rep": rep, "outcome": outcome,
                                   "shot_class": QA.shot_class(shot), "capture_sha256": sha,
                                   "checks": [c.as_dict() for c in checks],
                                   "not_applicable": na},
                     operator=fields.get("operator"))
        return 200, {"ok": True, "outcome": outcome, "path": rel,
                     "already_present": already, "shot_class": QA.shot_class(shot),
                     "checks": [c.as_dict() for c in checks], "not_applicable": na,
                     "url": "/photo?p=%s/%s" % (gid, rel)}

    @api.route("POST", "/api/cutspec/(DENIM_[0-9]{4})")
    def _cutspec(m, _q, b):
        from . import cutspec as CUT
        store = session.store(m.group(1))
        st, _ = store.fold()
        need = lambda k: mean_of(st["measurements"].get(k))
        missing = [k for k in ("original_inseam_cm", "thigh_cm", "leg_opening_cm") if need(k) is None]
        if missing:
            return 400, {"error": "these measurements are needed first: %s" % ", ".join(missing)}
        try:
            s = CUT.compute(target_inseam_cm=float(b["target_inseam_cm"]),
                            original_inseam_cm=need("original_inseam_cm"),
                            thigh_cm=need("thigh_cm"), leg_opening_cm=need("leg_opening_cm"))
        except Exception as e:
            return 400, {"error": str(e)}
        store.append("cut_spec", s, operator=b.get("operator"))
        return 200, {"ok": True, "cut_spec": s,
                     "packet": CUT.packet_lines(m.group(1), s)}

    @api.route("POST", "/api/wash/(DENIM_[0-9]{4})")
    def _wash(m, _q, b):
        store = session.store(m.group(1))
        st, _ = store.fold()
        which = "wash_actual" if b.get("actual") else "wash_planned"
        if b.get("actual") and not st["wash_planned"]:
            return 400, {"error": "record the planned wash first; actual settings never replace "
                                  "planned ones"}
        rec = dict(b.get("wash") or {})
        missing = [k for k in GATES.WASH_FIELDS if rec.get(k) in (None, "")]
        if missing:
            return 400, {"error": "a wash record needs every field; missing: %s"
                                  % ", ".join(missing)}
        for k in ("water_temp_c", "spin_rpm", "detergent_ml", "dryer_minutes"):
            try:
                rec[k] = _num(rec.get(k), k)
            except BadInput as e:
                return 400, {"error": str(e)}
        if not b.get("actual") and st["wash_planned"]:
            return 400, {"error": "this garment already has a wash plan; the planned settings are "
                                  "what a deviation is measured against and are not revised"}
        # Symmetrically for the ACTUAL. The CLI refuses a second recording by name and this route
        # accepted any number, returning {"ok": true} each time while fold() discarded all but the
        # first -- so a phone retrying a timed-out POST was told its settings were saved when they
        # were not, and a correction that overwrites erases exactly the deviation the planned/actual
        # split exists to preserve.
        if b.get("actual") and st["wash_actual"]:
            return 409, {"error": "the actual wash is already recorded for this garment. It is "
                                  "written once, like the plan: a correction that overwrites is "
                                  "indistinguishable from the wash never having deviated.",
                         "fix": "record the difference as a deviation of kind 'wash', naming the "
                                "field"}
        store.append(which, rec, operator=b.get("operator"))
        devs = []
        if b.get("actual"):
            devs = diff_planned_actual(st["wash_planned"], rec)
            for d in devs:
                store.append("deviation", dict(d, kind="wash"), operator=b.get("operator"))
        return 200, {"ok": True, "deviations": devs}

    @api.route("POST", "/api/offcut/(DENIM_[0-9]{4})")
    def _offcut(m, _q, b):
        store = session.store(m.group(1))
        from . import offcut as OFF
        rec = dict(b.get("offcut") or {})
        cond = rec.get("assigned_wash_condition")
        if cond is not None and OFF.classify(cond) is None:
            return 400, {"error": "%r is not a wash condition this protocol defines; it must be "
                                  "one of %s" % (cond, ", ".join(OFF.CONDITIONS))}
        leg = str(rec.get("originating_leg", ""))[:1].lower()
        if rec.get("originating_leg") is not None and leg not in ("l", "r"):
            return 400, {"error": "originating_leg must be left or right"}
        lbl = rec.get("label")
        if not isinstance(lbl, str) or not lbl.strip():
            # A JSON array passes a truthiness test and then cannot be a projection key, which made
            # the garment permanently ungateable.
            return 400, {"error": "an offcut needs its physical label as text"}
        store.append("offcut", rec, operator=b.get("operator"))
        return 200, {"ok": True}

    @api.route("POST", "/api/deviation/(DENIM_[0-9]{4})")
    def _deviation(m, _q, b):
        from .store import DEVIATION_KINDS
        kind = b.get("kind")
        if kind not in DEVIATION_KINDS:
            return 400, {"error": "kind must be one of %s" % ", ".join(DEVIATION_KINDS)}
        if not b.get("field"):
            return 400, {"error": "a deviation must say what departed"}
        reason = (b.get("reason") or "").strip()
        if len(reason) < 12:
            return 400, {"error": "a deviation needs a reason someone can read later"}
        if not b.get("operator"):
            return 400, {"error": "a deviation needs a name on it"}
        session.store(m.group(1)).append(
            "deviation", {"kind": kind, "field": str(b["field"]), "planned": b.get("planned"),
                          "actual": b.get("actual"), "reason": reason},
            operator=b.get("operator"))
        return 200, {"ok": True}

    @api.route("GET", "/api/gate/(DENIM_[0-9]{4})/([a-z_]+)")
    def _gate(m, _q, _b):
        gid, gate = m.group(1), m.group(2)
        if gate not in GATES.GATE_LAST_STATE:
            return 400, {"error": "unknown gate"}
        gdir = session.garments / gid
        v = GATES.evaluate(gate, session.spec, session.store(gid), garment_dir=gdir)
        return 200, v.as_dict()

    return api


def run(*, root, garments, spec_path, board_path, garment=None, port=8765, lan=False,
        open_browser=True):
    session = Session(root, garments, spec_path, board_path)
    if garment:
        if garment not in session.list_garments():
            print("no such garment: %s" % garment, file=sys.stderr)
            return 2
        session.default_garment = garment
    try:
        session.spec
    except Exception as e:
        print("cannot start: the shot-plan specification does not load.\n%s" % e, file=sys.stderr)
        return 2
    api = build_api(session)
    httpd, url = serve(api, data_root=garments, port=port, lan=lan)
    where = "this machine only" if not lan else "this machine and the local network"
    print("=" * 68)
    print("  denim-twin Pilot Capture Navigator")
    print("=" * 68)
    print("  open on your phone:  %s" % url)
    print("  reachable from:      %s" % where)
    if session.default_garment:
        print("  garment:             %s" % session.default_garment)
    print("  photographs stored:  %s" % garments)
    print("                       (gitignored; nothing is uploaded anywhere)")
    if not lan:
        print("\n  Bound to localhost. To reach it from the phone on this network, restart with")
        print("  --lan; the token above is then required on every request and lasts only as long")
        print("  as this process.")
    print("\n  Ctrl-C to stop.\n")
    # The banner carries the session token, and it is the only place it appears. Redirect stdout to
    # a file and Python block-buffers it, so `serve > log &` showed an empty log and no way in until
    # something else happened to fill 8 KB.
    sys.stdout.flush()
    if open_browser and not lan:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped. Photographs and the capture log are on disk under %s" % garments)
    finally:
        httpd.server_close()
    return 0
