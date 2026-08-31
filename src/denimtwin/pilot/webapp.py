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
import os
import sys
import time
import webbrowser
from pathlib import Path

from . import gates as GATES
from . import hem as HEM
from . import plan as PLAN
from . import qa as QA
from . import spec as SPEC
from .manifest import ingest_photo, read_exif, exif_timestamp
from .server import Api, serve
from .store import Store, setup_hash, diff_planned_actual


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

    def store(self, gid):
        d = self.garments / gid
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
            shots, meta = PLAN.activate(spec, st["features"])
        except PLAN.PlanError as e:
            shots, meta = [], {"error": str(e), "features": st["features"],
                               "assumed_present": [], "unevaluatable_conditions": []}
        ordered = PLAN.order(spec, shots)
        done = store.done_keys()
        blocked = set()
        for (sid, rep), q in st["qa"].items():
            if q.get("outcome") == QA.RETAKE:
                blocked.add((sid, rep))
        nxt = PLAN.next_action(spec, [e for e in ordered
                                      if not state_filter or e["state"] == state_filter],
                               done, blocked)
        if nxt is None:
            nxt = PLAN.next_action(spec, ordered, done)
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
        lo = (st["measurements"].get("leg_opening_cm") or {}).get("mean")
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

        gate = GATES.evaluate("ready_to_cut", spec, store, garment_dir=gdir, check_files=False)
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
            "measurements": {k: {"mean": v.get("mean"), "readings": v.get("readings"),
                                 "in_tolerance": v.get("in_tolerance")}
                             for k, v in st["measurements"].items()},
            "measurements_required": GATES.REQUIRED_MEASUREMENTS,
            "next": nxt_out,
            "ghost": ghost,
            "n_total": len(ordered), "n_done": len(done & {(e["shot_id"], e["rep"]) for e in ordered}),
            "seconds_remaining": PLAN.estimate_seconds(spec, remaining),
            "by_state": by_state, "by_region": by_region,
            "matched": matched,
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


def build_api(session):
    api = Api()

    @api.route("GET", "/api/garments")
    def _garments(m, q, b):
        return 200, {"garments": session.list_garments(),
                     "spec_version": session.spec.version,
                     "spec_hash": session.spec.content_hash[:12]}

    @api.route("GET", "/api/map")
    def _map(m, q, b):
        return 200, session.map_data()

    @api.route("GET", "/api/state/(DENIM_[0-9]{4})")
    def _state(m, q, b):
        try:
            return 200, session.snapshot(m.group(1), state_filter=(q.get("state") or [None])[0])
        except KeyError:
            return 404, {"error": "no such garment"}

    @api.route("POST", "/api/features/(DENIM_[0-9]{4})")
    def _features(m, q, b):
        st = session.store(m.group(1))
        st.append("feature_answers", {"answers": b.get("answers") or {}},
                  operator=b.get("operator"))
        return 200, {"ok": True}

    @api.route("POST", "/api/measure/(DENIM_[0-9]{4})")
    def _measure(m, q, b):
        name = b.get("name")
        readings = [float(x) for x in (b.get("readings") or []) if x not in (None, "")]
        need = GATES.REQUIRED_MEASUREMENTS.get(name)
        if need is None:
            return 400, {"error": "%s is not a required measurement" % name}
        tol = GATES.MEASUREMENT_TOLERANCE.get(name, GATES.MEASUREMENT_TOLERANCE["_default_cm"])
        if len(readings) < need:
            return 400, {"error": "%s needs %d independent readings, got %d"
                                  % (name, need, len(readings))}
        spread = max(readings) - min(readings)
        st = session.store(m.group(1))
        st.append("measurement", {"name": name, "readings": readings,
                                  "mean": sum(readings) / len(readings), "spread": spread,
                                  "tolerance": tol, "in_tolerance": spread <= tol},
                  operator=b.get("operator"))
        return 200, {"ok": True, "spread": spread, "in_tolerance": spread <= tol}

    @api.route("POST", "/api/confirm/(DENIM_[0-9]{4})")
    def _confirm(m, q, b):
        if not b.get("operator"):
            return 400, {"error": "a human verification needs a name on it"}
        st = session.store(m.group(1))
        st.append("human_verification",
                  {"shot_id": b.get("shot_id"), "rep": b.get("rep"), "claim": b.get("claim"),
                   "value": bool(b.get("value", True)), "note": b.get("note"),
                   "verifier_name": b.get("verifier") or b.get("operator"),
                   "measured_inseam_cm": b.get("measured_inseam_cm"),
                   "measured_outseam_cm": b.get("measured_outseam_cm")},
                  operator=b.get("operator"))
        return 200, {"ok": True}

    @api.route("POST", "/api/setup/(DENIM_[0-9]{4})")
    def _setup(m, q, b):
        st = session.store(m.group(1))
        cfg = b.get("setup") or {}
        h = setup_hash(cfg)
        st.append("setup_frozen", {"setup": cfg, "setup_hash": h,
                                   "reason": b.get("reason") or "frozen from the app"},
                  operator=b.get("operator"))
        for c in (b.get("checks") or []):
            st.append("setup_check", c, operator=b.get("operator"), setup_hash=h)
        return 200, {"ok": True, "setup_hash": h}

    @api.route("POST", "/api/upload")
    def _upload(m, q, b):
        fields = b.get("fields") or {}
        files = b.get("files") or {}
        gid = fields.get("garment")
        shot_id = fields.get("shot_id")
        rep = int(fields.get("rep") or 1)
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
            shots, _m = PLAN.activate(spec, st["features"])
        except PLAN.PlanError as e:
            return 400, {"error": str(e)}
        shot = {s["shot_id"]: s for s in shots}.get(shot_id)
        if shot is None:
            return 400, {"error": "%s is not an activated shot for this garment" % shot_id}
        name, blob = list(files.items())[0]
        tmp = gdir / "pilot" / ".incoming"
        tmp.mkdir(parents=True, exist_ok=True)
        ext = os.path.splitext(blob.get("filename") or "capture.jpg")[1].lower() or ".jpg"
        stage = tmp / ("upload%s" % ext)
        with open(str(stage), "wb") as f:
            f.write(blob["data"])
            f.flush()
            os.fsync(f.fileno())
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
                                 "state": shot["state"], "region_id": shot.get("region_id"),
                                 "already_present": already},
                     operator=fields.get("operator"), setup_hash=st["setup_hash"])
        board, bspec = session.board
        quality = QA.merged_quality(spec.doc["quality_defaults"], shot)
        from . import qa_primitives as Q
        compare = []
        for (sid, r), c in sorted(st["captures"].items()):
            p = gdir / (c.get("path") or "")
            if not p.exists() or (sid, r) == (shot_id, rep):
                continue
            oimg = cv2.imread(str(p))
            compare.append({"shot_id": sid, "rep": r, "sha256": c.get("sha256"),
                            "self_sha256": sha, "image": oimg,
                            "pose": Q.garment_pose(oimg) if oimg is not None else None,
                            "exif_ts": c.get("exif_ts"), "this_exif_ts": ts,
                            "is_previous_rep": (sid == shot_id and r == rep - 1)})
        assertions = {"operator": fields.get("operator")}
        for k in (fields.get("confirm") or "").split(","):
            if k.strip():
                assertions[k.strip()] = True
        checks = QA.check_capture(dest, shot, quality, board=board, board_spec=bspec, image=img,
                                  compare_to=compare, operator_assertions=assertions)
        outcome = QA.roll_up(checks)
        store.append("qa_result", {"shot_id": shot_id, "rep": rep, "outcome": outcome,
                                   "checks": [c.as_dict() for c in checks]},
                     operator=fields.get("operator"))
        return 200, {"ok": True, "outcome": outcome, "path": rel,
                     "already_present": already,
                     "checks": [c.as_dict() for c in checks],
                     "url": "/photo?p=%s/%s" % (gid, rel)}

    @api.route("POST", "/api/cutspec/(DENIM_[0-9]{4})")
    def _cutspec(m, q, b):
        from . import cutspec as CUT
        store = session.store(m.group(1))
        st, _ = store.fold()
        need = lambda k: (st["measurements"].get(k) or {}).get("mean")
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
    def _wash(m, q, b):
        store = session.store(m.group(1))
        st, _ = store.fold()
        which = "wash_actual" if b.get("actual") else "wash_planned"
        if b.get("actual") and not st["wash_planned"]:
            return 400, {"error": "record the planned wash first; actual settings never replace "
                                  "planned ones"}
        rec = dict(b.get("wash") or {})
        store.append(which, rec, operator=b.get("operator"))
        devs = []
        if b.get("actual"):
            devs = diff_planned_actual(st["wash_planned"], rec)
            for d in devs:
                store.append("deviation", dict(d, kind="wash"), operator=b.get("operator"))
        return 200, {"ok": True, "deviations": devs}

    @api.route("POST", "/api/offcut/(DENIM_[0-9]{4})")
    def _offcut(m, q, b):
        store = session.store(m.group(1))
        rec = dict(b.get("offcut") or {})
        if not rec.get("label"):
            return 400, {"error": "an offcut needs its physical label"}
        store.append("offcut", rec, operator=b.get("operator"))
        return 200, {"ok": True}

    @api.route("GET", "/api/gate/(DENIM_[0-9]{4})/([a-z_]+)")
    def _gate(m, q, b):
        gid, gate = m.group(1), m.group(2)
        if gate not in GATES.GATE_STATES:
            return 400, {"error": "unknown gate"}
        gdir = session.garments / gid
        v = GATES.evaluate(gate, session.spec, session.store(gid), garment_dir=gdir)
        return 200, v.as_dict()

    return api


def run(*, root, garments, spec_path, board_path, garment=None, port=8765, lan=False,
        open_browser=True):
    session = Session(root, garments, spec_path, board_path)
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
    print("  photographs stored:  %s" % garments)
    print("                       (gitignored; nothing is uploaded anywhere)")
    if not lan:
        print("\n  Bound to localhost. To reach it from the phone on this network, restart with")
        print("  --lan; the token above is then required on every request and lasts only as long")
        print("  as this process.")
    print("\n  Ctrl-C to stop.\n")
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
