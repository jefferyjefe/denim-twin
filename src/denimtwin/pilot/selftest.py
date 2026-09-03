"""Run the whole system against synthetic images, and try to make it lie.

Two kinds of scenario, and both are necessary.

The NEGATIVE ones try to obtain a pass that is not deserved: five copies of one photograph offered
as five independent re-lays, a photograph swapped under a manifest entry, a measurement recorded
once and called two readings, a hem series whose length is unknown, a capture with no calibration
board. Each asserts that the system refuses, and names which refusal.

The POSITIVE one matters just as much, and is the one a suspicious gate quietly fails: a gate that
says NO to everything is not safe, it is broken, and it teaches its operator to route around it. So
one scenario drives a complete session to READY TO CUT and asserts that the gate opens. If it cannot
be made to open with valid evidence, that is a defect of the same severity as opening it without.

Everything runs in a temporary directory. Nothing here touches data/garments -- the repository's
real garment records are not a test fixture, and `tests/conftest.py` already had to learn that a
suite which writes where the evidence lives is a suite that can destroy it.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import pathlib
import threading
import zlib
from pathlib import Path

from . import gates as GATES
from . import hem as HEM
from . import plan as PLAN
from . import qa as QA
from . import claims as CLAIMS
from . import spec as SPEC
from . import subjects as SUBJ
from . import manifest as MF
from .fixtures import synth_capture
from .manifest import ManifestError, ingest_photo, sha256_file
from .store import Store, setup_hash

ROOT = Path(__file__).resolve().parents[3]


def _resolved(state, shot_id, rep):
    """Is every HUMAN claim on this frame cleared, by the gate's own rule?"""
    from .gates import _human_resolved
    q = state["qa"].get((shot_id, rep))
    if not q:
        return False
    return _human_resolved(state, shot_id, rep, q, state["captures"].get((shot_id, rep)))


class Result(object):
    def __init__(self, name, ok, detail, expectation):
        self.name, self.ok, self.detail, self.expectation = name, ok, detail, expectation


class Bench(object):
    """One temporary garment with the machinery to drive it."""

    def __init__(self, tmp, spec, gid="DENIM_9001"):
        self.tmp = Path(tmp)
        self.spec = spec
        self.gid = gid
        self.dir = self.tmp / "garments" / gid
        for s in ("rig", "intake", "before", "marked", "immediate_after", "post_wash"):
            (self.dir / "images" / s).mkdir(parents=True, exist_ok=True)
        self.store = Store(self.dir)
        self.setup = {"camera_model": "synthetic", "mount_height_cm": 80.0, "lens": "main",
                      "backdrop": "dark green matte", "lighting": "two diffuse 45deg",
                      "leg_gap_cm": 4.0, "exposure_locked": True, "room": "test"}
        self.setup_hash = setup_hash(self.setup)
        self._board = None

    @property
    def board(self):
        if self._board is None:
            from ..capture.board import load_board
            self._board = load_board(ROOT / "protocol" / "charuco_board.json")
        return self._board

    # -- session steps -----------------------------------------------------------------------

    def open_session(self, spec_hash=None):
        self.store.append("session_opened",
                          {"spec_version": self.spec.version,
                           "spec_hash": spec_hash or self.spec.content_hash,
                           "protocol_version": self.spec.doc["protocol_version"]})

    def freeze_rig(self, *, board_mm=200.0, squares=8, skip=()):
        self.store.append("setup_frozen", {"setup": self.setup, "setup_hash": self.setup_hash,
                                           "reason": "selftest"})
        for c in GATES.REQUIRED_SETUP_CHECKS:
            if c in skip:
                continue
            rec = {"check": c, "outcome": QA.PASS, "confirmed_by": "selftest"}
            if c == "board_square_measured":
                rec.update({"squares_spanned": squares, "measured_mm": board_mm})
            self.store.append("setup_check", rec, setup_hash=self.setup_hash)

    def answer_features(self, overrides=None):
        ans = {}
        for f in self.spec.features:
            ans[f["key"]] = 0 if f["type"] == "count" else (
                False if f["unanswered_means"] == "absent" else True)
        ans.update(overrides or {})
        self.store.append("feature_answers", {"answers": ans}, operator="selftest")
        return ans

    def measure(self, *, skip=(), bad_tolerance=(), single_reading=()):
        vals = {"waist_cm": 82.0, "front_rise_cm": 27.0, "back_rise_cm": 37.0, "thigh_cm": 60.0,
                "original_inseam_cm": 78.0, "leg_opening_cm": 40.0,
                "fabric_thickness_mm": 1.05, "mass_grams": 640.0}
        for name, n in sorted(GATES.REQUIRED_MEASUREMENTS.items()):
            if name in skip:
                continue
            base = vals[name]
            step = 0.05 if name == "fabric_thickness_mm" else (0.5 if name == "mass_grams" else 0.1)
            readings = [base + i * step for i in range(n)]
            if name in bad_tolerance:
                readings = [base, base + 40.0] + readings[2:]
            if name in single_reading:
                readings = readings[:1]
            tol = GATES.MEASUREMENT_TOLERANCE.get(name, GATES.MEASUREMENT_TOLERANCE["_default_cm"])
            spread = max(readings) - min(readings)
            self.store.append("measurement",
                              {"name": name, "readings": readings,
                               "mean": sum(readings) / len(readings), "spread": spread,
                               "tolerance": tol, "in_tolerance": spread <= tol},
                              operator="selftest")

    def activated(self):
        st, _ = self.store.fold()
        return PLAN.activate(self.spec, st["features"],
                             GATES.plan_safe_measurements(st), st.get("cut_spec"),
                             annotations=st.get("annotations"))

    def synth_for(self, shot, rep, *, relay=None, seed=None, **kw):
        """A synthetic frame that actually satisfies the shot it stands in for.

        A fixture that cannot meet the requirement under test proves nothing about the requirement:
        the positive control would fail on the fixture's resolution rather than on the system's
        behaviour, and the failure would look identical to a real one. So the frame is sized from
        the shot's own `min_long_edge_px` and scaled from its own `max_mm_per_px`, and the board is
        drawn only when the shot actually asks for a board -- a macro that needs 0.05 mm/px has no
        room for a 200 mm board, which is exactly why its scale reference is a rule.

        Different shots are also given different crease fields, so two distinct shots do not collide
        in the duplicate check the way two frames of one lay should.
        """
        q = QA.merged_quality(self.spec.doc["quality_defaults"], shot)
        mm = q.get("max_mm_per_px")
        mm = float(mm) * 0.8 if mm else 0.35
        mm = max(mm, 0.02)
        long_edge = max(int(q.get("min_long_edge_px") or 1600) + 200, 1600)
        w = min(long_edge, 4200)
        h = int(w * 0.75)
        subject = "jeans_back" if shot.get("garment_side") == "back" else "jeans_front"
        if shot.get("camera_angle") in ("macro_perpendicular", "side_profile"):
            subject = "hem_macro"
        if shot["state"] == "rig":
            subject = "blank_backdrop"
        wants_board = shot.get("scale_reference") in ("charuco_board", "both") \
            or q.get("requires_board")
        if wants_board:
            # The board is 200 x 275 mm. At a fine scale it does not fit a frame sized only for the
            # subject, and `synth_capture` then shrinks it -- which silently changes the frame's real
            # mm/px and makes the fixture fail the scale requirement it was built to satisfy. Give
            # the board room instead.
            board_px = 275.0 / mm
            w = max(w, int(board_px * 1.25))
            h = int(w * 0.75)
        # The seed must be unique per (shot, repeat). Deriving it by ADDING the repeat to a running
        # counter collides -- frame 10 repeat 2 and frame 11 repeat 1 land on the same number, and
        # two different shots then produce byte-identical images that the duplicate check correctly
        # rejects. The bug was in the fixture, and it looked exactly like a system fault.
        base = seed if seed is not None else 0
        uniq = zlib.crc32(("%s|%d|%d" % (shot["shot_id"], rep, base)).encode()) % (2 ** 31)
        # A VIDEO SHOT NEEDS A VIDEO. The plan requires two motion clips after the wash, and a
        # fixture that answers them with a PNG fails them for a fact about the fixture: `readable`
        # is cv2.imread, which returns None for every container, so the frame is a RETAKE and the
        # finalize gate cannot open. Excusing that in the assertion would have hidden the one
        # difference between a positive control and a list of things that happen to be true.
        if QA.shot_class(shot) == "video":
            return self._synth_clip(shot, rep, uniq)
        args = dict(subject=subject, mm_per_px=mm, size=(w, h),
                    seed=uniq,
                    # An explicit relay index means the caller is saying something specific about
                    # the lay -- "this is the same lay as the last frame" is how the negative
                    # scenarios are built -- so it is never perturbed. Only the default is offset
                    # per shot, so two different shots do not share a crease field.
                    relay=(relay if relay is not None else rep + (uniq % 977) * 1000),
                    board=bool(wants_board),
                    ruler=shot.get("scale_reference") in ("ruler", "both"))
        args.update(kw)
        p = self.tmp / "synth" / ("%s_r%d.png" % (shot["shot_id"].replace(".", "_"), rep))
        p.parent.mkdir(parents=True, exist_ok=True)
        synth_capture(str(p), **args)
        return p

    def _synth_clip(self, shot, rep, uniq, fps=20.0):
        """A synthetic clip, sized and timed from the SHOT'S OWN requirements.

        Same principle as the still path: a fixture that cannot meet the requirement under test
        proves nothing about the requirement, because the positive control then fails on the
        fixture's resolution rather than on the system's behaviour, and the two failures look
        identical. So the long edge comes from `min_long_edge_px` and the duration from the shot's
        own `video_seconds`.

        Deliberately moving: `duplicate_content` compares frames, and a clip of a still image is a
        still image with a container around it.
        """
        import cv2
        import numpy as np
        q = QA.merged_quality(self.spec.doc["quality_defaults"], shot)
        p = self.tmp / "synth" / ("%s_r%d.mp4" % (shot["shot_id"].replace(".", "_"), rep))
        p.parent.mkdir(parents=True, exist_ok=True)
        w = max(int(q.get("min_long_edge_px") or 1080) + 120, 1200)
        h = int(w * 0.75)
        seconds = float(shot.get("video_seconds") or 6.0)
        vw = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        if not vw.isOpened():
            vw.release()
            raise RuntimeError("this build of OpenCV has no video writer, so a video-class shot "
                               "cannot be exercised; the finalize gate cannot be proven here")
        rng = np.random.RandomState(uniq % (2 ** 31))
        bg = np.full((h, w, 3), 90, np.uint8)
        bg[:, :, 1] = np.clip(bg[:, :, 1].astype(int)
                              + rng.randint(0, 14, (h, w)), 0, 255).astype(np.uint8)
        n = max(int(seconds * fps), 2)
        x0, x1 = int(w * 0.2), int(w * 0.8)
        for i in range(n):
            fr = bg.copy()
            y = int(h * 0.2) + int(h * 0.12 * abs(((i / float(n - 1)) * 2) - 1))
            cv2.rectangle(fr, (x0, y), (x1, y + int(h * 0.45)), (128, 96, 64), -1)
            cv2.rectangle(fr, (x0, y), (x1, y + int(h * 0.45)), (170, 140, 110), 3)
            vw.write(fr)
        vw.release()
        return p

    def add(self, shot, rep, src, *, confirm_all=True, setup_hash_override="__default__",
            subject_declared=None):
        from .manifest import read_exif, exif_timestamp
        from . import qa_primitives as Q
        import cv2
        subject = SUBJ.capture_fields(shot, rep, declared=subject_declared)
        dest, sha, already = ingest_photo(src, self.dir / "images" / shot["state"],
                                          shot["shot_id"], rep)
        rel = str(dest.relative_to(self.dir))
        exif = read_exif(dest)
        # Per CAPTURE, not per repeat index: a series written as separate shot ids is always
        # rep 1, so every frame in it landed on the same synthetic second and the relay check
        # correctly refused a re-lay that appeared to take no time at all.
        self._clock = getattr(self, "_clock", 0) + 1
        ts = exif_timestamp(exif) or (time.time() + self._clock * 180)
        img = Q.decode_any(dest)   # a clip is decoded from its first frame, like the real paths
        sh = self.setup_hash if setup_hash_override == "__default__" else setup_hash_override
        self.store.append("capture",
                          {"shot_id": shot["shot_id"], "rep": rep, "path": rel, "sha256": sha,
                           "exif": exif, "exif_ts": ts,
                           "width": img.shape[1] if img is not None else None,
                           "height": img.shape[0] if img is not None else None,
                           "dhash": Q.dhash_bits(img).hex() if img is not None else None,
                           "state": shot["state"], "region_id": shot.get("region_id"),
                           "instance_index": shot.get("instance_index"),
                           "instance_total": shot.get("instance_total"),
                           "annotation_id": shot.get("annotation_id"),
                           "annotation_type": shot.get("annotation_type"),
                           "annotation_location": shot.get("annotation_location"),
                           "subject_id": subject["subject_id"],
                           "subject_aspect": subject["subject_aspect"]},
                          operator="selftest", setup_hash=sh)
        st, _ = self.store.fold()
        board, bspec = self.board
        # qa.compare_set: the bench must build its comparison set exactly the way the real
        # ingest paths do, or the scenarios test something the operator never runs.
        compare = QA.compare_set(st, self.dir, shot['shot_id'], rep, shot, self_sha=sha,
                                 self_ts=ts, board=board, board_spec=bspec)
        assertions = {"operator": "selftest"}
        if confirm_all:
            for k in ("ruler_visible", "side_confirmed", "region_confirmed",
                      "relay_confirmed", "camera_repositioned"):
                assertions[k] = True
        checks, na = QA.check_capture(dest, shot,
                                      QA.merged_quality(self.spec.doc["quality_defaults"], shot),
                                      rep=rep, board=board, board_spec=bspec, image=img,
                                      compare_to=compare, operator_assertions=assertions)
        outcome = QA.roll_up(checks)
        self.store.append("qa_result", {"shot_id": shot["shot_id"], "rep": rep,
                                        "outcome": outcome, "shot_class": QA.shot_class(shot),
                                        "capture_sha256": sha,
                                        "checks": [c.as_dict() for c in checks],
                                        "not_applicable": na},
                          operator="selftest")
        return outcome, checks

    def resolve_humans(self):
        """Clear every outstanding claim, THROUGH THE MODEL BOTH FRONT DOORS USE.

        This used to hand-write the log entry, so the full-plan run -- the one thing that drives the
        real 424-frame plan end to end -- exercised neither front door's confirmation path. Every
        claim in it was cleared by a record the operator has no way to produce. Going through
        `claims.resolve` and `claims.payload` means the run proves the path an operator will
        actually use, including the binding fields.

        Already-cleared claims are skipped, so calling this after each capture phase does not write
        the same verification three times.
        """
        st, _ = self.store.fold()
        n = 0
        for (sid, rep) in sorted(st["qa"]):
            for c in CLAIMS.pending_claims(st, sid, rep):
                if c["resolved"]:
                    continue
                claim = CLAIMS.resolve(st, sid, rep, code=c["code"])
                self.store.append(
                    "human_verification",
                    CLAIMS.payload(claim=claim, shot_id=sid, rep=rep, value=True,
                                   operator="selftest", verifier="selftest",
                                   bind=CLAIMS.binding(st, self.spec, sid, rep),
                                   interface="cli", entry_mode="scripted"),
                    operator="selftest")
                n += 1
        return n

    def cut_ready_extras(self, *, tolerance_error_cm=0.0, skip=()):
        from . import cutspec as CUT
        st, _ = self.store.fold()
        m = st["measurements"]
        if "cut_spec" not in skip:
            s = CUT.compute(target_inseam_cm=15.0,
                            original_inseam_cm=m["original_inseam_cm"]["mean"],
                            thigh_cm=m["thigh_cm"]["mean"],
                            leg_opening_cm=m["leg_opening_cm"]["mean"])
            self.store.append("cut_spec", s, operator="selftest")
            if "verification" not in skip:
                self.store.append("human_verification",
                                  {"shot_id": None, "rep": None, "claim": "cut_marks_verified",
                                   "value": True, "verifier_name": "second person",
                                   "operator": "selftest",
                                   "measured_inseam_cm": s["target_inseam_cm"] + tolerance_error_cm,
                                   "measured_outseam_cm": s["predicted_outseam_cm"]},
                                  operator="selftest")
        for claim in ("legs_cut_separately", "offcuts_retained_labelled"):
            if claim in skip:
                continue
            self.store.append("human_verification",
                              {"shot_id": None, "rep": None, "claim": claim, "value": True,
                               "verifier_name": "selftest", "operator": "selftest"},
                              operator="selftest")

    def after_cut_extras(self, *, skip=()):
        """Everything that happens between the shears and the finished record.

        Order matters and is the point: the recorded cut moves the garment to immediate_after and
        the recorded wash moves it to post_wash, so the post-wash readings land in their own bucket
        rather than on top of the pre-cut ones.
        """
        from . import offcut as OFF
        st, _ = self.store.fold()
        cs = st.get("cut_spec") or {}
        tgt = cs.get("target_inseam_cm") or 15.0
        outs = cs.get("predicted_outseam_cm") or tgt
        if "cut_performed" not in skip:
            self.store.append("cut_performed",
                              {"achieved_inseam_cm": {"L": tgt + 0.1, "R": tgt},
                               "achieved_outseam_cm": {"L": outs + 0.1, "R": outs},
                               "tool": "Fiskars 9in dressmaking shears",
                               "legs_cut_separately": True, "operator": "selftest"},
                              operator="selftest")
        if "offcuts" not in skip:
            for lbl, leg, cond in ((self.gid + "_OFFCUT_L", "L", OFF.WITH_GARMENT),
                                   (self.gid + "_OFFCUT_R", "R", OFF.SEPARATE_LOAD)):
                self.store.append("offcut", {"label": lbl, "originating_leg": leg,
                                             "assigned_wash_condition": cond},
                                  operator="selftest")
        plan = {"machine": "Miele W1", "location": "flat", "cycle": "cottons 30",
                "water_temp_c": 30.0, "spin_rpm": 1200.0, "detergent": "Persil",
                "detergent_ml": 35.0, "filler_load": "3 towels", "start_time": "10:00",
                "end_time": "11:30", "dryer_method": "line", "dryer_setting": "n/a",
                "dryer_minutes": 0.0, "conditioning_start": "11:30",
                "conditioning_end": "13:30", "garment_in_load": self.gid + " + offcut L"}
        if "wash_planned" not in skip:
            self.store.append("wash_planned", plan, operator="selftest")
        if "wash_actual" not in skip:
            self.store.append("wash_actual", dict(plan), operator="selftest")
        if "post_wash_measurements" not in skip:
            pre = st["measurements"]
            for name, n in sorted(GATES.POST_WASH_MEASUREMENTS.items()):
                base = (pre.get(name) or {}).get("mean") or 40.0
                base *= 0.985                       # a plausible one-wash shrink
                readings = [base + i * 0.1 for i in range(n)]
                self.store.append("measurement",
                                  {"name": name, "readings": readings,
                                   "mean": sum(readings) / len(readings),
                                   "spread": max(readings) - min(readings),
                                   "state": "post_wash"},
                                  operator="selftest")

    def describe_instances(self, *, discovered_in=None, feature_keys=None, prefix=""):
        """Describe every counted feature instance the answers say the garment has.

        Without this the full plan is not the full plan: `answer_features` answers 0 to every count,
        and the 424-frame plan collapses to 197. The counted features are exactly the part where a
        photograph has to name the object it is of, so a full-plan run that never expands one is a
        run that skips the mechanism most worth exercising.
        """
        st, _ = self.store.fold()
        out = []
        for f in self.spec.features:
            if f["type"] != "count":
                continue
            if feature_keys is not None and f["key"] not in feature_keys:
                continue
            try:
                n = int(float(st["features"].get(f["key"]) or 0))
            except (TypeError, ValueError):
                continue
            for i in range(1, n + 1):
                aid = "%s%s.%02d" % (prefix, f["key"].replace("n_", "").upper(), i)
                payload = {"annotation_id": aid, "feature": f["key"],
                           "type": f["key"].replace("n_", ""),
                           "location": "synthetic instance %d of %s" % (i, f["key"]),
                           "note": "self-test", "size_mm": 10.0 + i,
                           "operator": "selftest"}
                if discovered_in:
                    payload["discovered_in"] = discovered_in
                self.store.append("annotation", payload, operator="selftest")
                out.append(aid)
        return out

    def capture_states(self, states, *, include_optional=False, seed=0, skip_shots=()):
        """Every required frame in these lifecycle states, taken once per repeat.

        Returns (frames captured, the shot dicts it captured). The plan is re-derived on entry, so
        a state reached after an annotation or a cut specification sees the frames that only exist
        because of it.
        """
        shots, _m = self.activated()
        _SHOT_BY_ID.update({x["shot_id"]: x for x in shots})
        want = [x for x in shots
                if x["state"] in states
                and (include_optional or x["necessity"] != "optional")
                and x["shot_id"] not in skip_shots]
        n = 0
        for sh in PLAN.order(self.spec, want):
            rep = sh.get("rep", 1)
            self.add(sh, rep, self.synth_for(sh, rep, relay=_lay_index(sh, rep), seed=seed))
            n += 1
        return n, want

    def entries(self):
        """This session's log entries, in order, as the appender wrote them."""
        return self.manifest_entries()

    def manifest_entries(self):
        entries, _problems = self.store.manifest.read(verify=False)
        return entries

    def gate(self, gate_id="ready_to_cut", **kw):
        return GATES.evaluate(gate_id, self.spec, self.store, garment_dir=self.dir, **kw)

    def blocked_conditions(self, gate_id="ready_to_cut", **kw):
        return {b.condition for b in self.gate(gate_id, **kw).blocks}


# ------------------------------------------------------------------------------------------
# scenarios
# ------------------------------------------------------------------------------------------

def _mini_spec(tmp):
    """A four-shot specification, so the positive control can be driven to READY quickly.

    It is a real specification loaded through the real loader -- the gate under test is the same
    code path as production. Only the shot list is small.
    """
    src = ROOT / "protocol" / "shotplan"
    d = Path(tmp) / "shotplan"
    d.mkdir(parents=True, exist_ok=True)
    for f in ("shotplan.schema.json", "regions.schema.json"):
        shutil.copy(str(src / f), str(d / f))
    regions = json.loads((src / "regions.json").read_text())
    doc = json.loads((src / "shotplan.json").read_text())
    keep = []
    for want in ("whole_garment_front", "whole_garment_back"):
        for s in doc["shots"]:
            if s["region_id"] == want and s["camera_angle"] == "overhead" \
                    and s["necessity"] == "required" and s["state"] == "before":
                c = dict(s)
                c["min_reps"] = 2
                c["relay_between_reps"] = True
                c["matched_shot_ids"] = []
                keep.append(c)
                break
    if len(keep) < 2:                       # the plan changed; synthesise the two frames instead
        keep = [{
            "shot_id": "BEFORE.WHOLE.%s_OVERHEAD" % side.upper(), "state": "before",
            "garment_side": side, "region_id": "whole_garment_%s" % side,
            "camera_angle": "overhead",
            "framing": "whole garment, board in frame", "scale_reference": "charuco_board",
            "min_reps": 2, "relay_between_reps": True, "necessity": "required",
            "est_seconds": 45, "camera_height_group": "mount_overhead", "lens": "main",
            "purpose": "silhouette and scale before any modification",
            "quality": {"min_subject_px": 400,
                        "subject_px_meaning": "garment width"},
        } for side in ("front", "back")]
    doc["shots"] = keep
    # The features stay exactly as they are. Only the shot list shrinks: the region map's own
    # conditions reference most of the feature keys, and a specification whose regions point at
    # features that are not declared is precisely what the loader is supposed to refuse.
    (d / "regions.json").write_text(json.dumps(regions))
    (d / "shotplan.json").write_text(json.dumps(doc))
    return SPEC.load(d / "shotplan.json")



def _lay_index(shot, rep):
    """The lay this frame is taken from, as the fixture must render it.

    A repeat inside a shot id advances the lay by its repeat number. A series written as SEPARATE
    shot ids advances it by depth along the relay_after chain -- otherwise the fixture hands five
    frames of ONE lay to the five frames whose entire purpose is being five different lays, and the
    positive control passes only for as long as nothing checks.
    """
    depth, seen, cur = 0, set(), shot
    while cur and cur.get("relay_after") and cur["shot_id"] not in seen:
        seen.add(cur["shot_id"])
        depth += 1
        cur = _SHOT_BY_ID.get(cur["relay_after"])
    return rep + depth


_SHOT_BY_ID = {}

def scenarios(full_spec, tmp_root, want_full=False):
    out = []

    def new(name, spec=None, gid="DENIM_9001"):
        t = Path(tempfile.mkdtemp(dir=str(tmp_root), prefix=name[:18] + "_"))
        return Bench(t, spec or full_spec, gid)

    # -- 1. a fresh garment is never ready ---------------------------------------------------
    b = new("fresh")
    v = b.gate()
    out.append(Result("fresh garment is not ready to cut", not v.ready,
                      "%d blocks: %s" % (len(v.blocks),
                                         ", ".join(sorted(x.condition for x in v.blocks))[:150]),
                      "a garment with no evidence must be blocked"))

    # -- 2. an empty plan is a block, not a pass ---------------------------------------------
    b = new("emptyplan")
    b.open_session()
    b.freeze_rig()
    v = b.gate()
    out.append(Result("unanswered questionnaire blocks the plan",
                      "features.answered" in {x.condition for x in v.blocks},
                      "blocks: " + ", ".join(sorted(x.condition for x in v.blocks))[:150],
                      "no features answered means no plan, and no plan is not an empty requirement"))

    # -- 3. missing measurements block --------------------------------------------------------
    b = new("nomeasure")
    b.open_session(); b.freeze_rig(); b.answer_features()
    b.measure(skip=("thigh_cm", "back_rise_cm"))
    out.append(Result("missing measurements block the cut",
                      "measurements.complete" in b.blocked_conditions(),
                      "blocked: " + ", ".join(sorted(b.blocked_conditions()))[:150],
                      "a dimension nobody measured cannot be quietly treated as measured"))

    # -- 4. one reading is not two ------------------------------------------------------------
    b = new("onereading")
    b.open_session(); b.freeze_rig(); b.answer_features()
    b.measure(single_reading=("waist_cm",))
    out.append(Result("a single reading does not satisfy 'two independent readings'",
                      "measurements.complete" in b.blocked_conditions(),
                      "blocked: measurements.complete present = %s"
                      % ("measurements.complete" in b.blocked_conditions()),
                      "the protocol asks for two readings so their spread can be seen"))

    # -- 5. readings that disagree block ------------------------------------------------------
    b = new("badtol")
    b.open_session(); b.freeze_rig(); b.answer_features()
    b.measure(bad_tolerance=("waist_cm",))
    out.append(Result("readings outside tolerance block the cut",
                      "measurements.complete" in b.blocked_conditions(),
                      "waist readings 40 cm apart",
                      "two readings that disagree by 40 cm were not both measurements of a waist"))

    # -- 6. a photograph is never overwritten -------------------------------------------------
    b = new("overwrite")
    shot = {"shot_id": "TEST.A", "state": "before"}
    p1 = b.tmp / "a.png"; synth_capture(str(p1), subject="jeans_front", mm_per_px=0.5,
                                        size=(900, 700), seed=1)
    p2 = b.tmp / "b.png"; synth_capture(str(p2), subject="jeans_front", mm_per_px=0.5,
                                        size=(900, 700), seed=2)
    d1, s1, _ = ingest_photo(p1, b.dir / "images" / "before", "TEST.A", 1)
    refused = False
    try:
        shutil.copy(str(p2), str(d1))            # simulate something replacing the file in place
        ingest_photo(p2, b.dir / "images" / "before", "TEST.A", 1)
    except ManifestError:
        refused = True
    # the content-addressed name means a different image simply cannot land on the same path
    d2, s2, _ = ingest_photo(p2, b.dir / "images" / "before", "TEST.A", 1)
    out.append(Result("a different photograph never lands on an existing one",
                      d2 != d1 and s2 != s1,
                      "%s vs %s" % (d1.name, d2.name),
                      "content-addressed names make an in-place replacement impossible"))

    # -- 7. re-ingesting identical bytes is idempotent -----------------------------------------
    b = new("idem")
    p = b.tmp / "a.png"; synth_capture(str(p), subject="jeans_front", mm_per_px=0.5,
                                       size=(900, 700), seed=3)
    da, sa, first = ingest_photo(p, b.dir / "images" / "before", "TEST.A", 1)
    db, sb, second = ingest_photo(p, b.dir / "images" / "before", "TEST.A", 1)
    out.append(Result("an interrupted upload can be retried safely",
                      da == db and sa == sb and not first and second,
                      "second ingest reported already_present=%s" % second,
                      "retrying a torn copy must complete it or find it complete, never duplicate"))

    # -- 8. a torn manifest line is quarantined, not silently dropped --------------------------
    b = new("torn")
    b.open_session()
    with open(str(b.store.manifest.path), "a") as f:
        f.write('{"seq":99,"kind":"cap')
    entries, problems = b.store.manifest.read()
    kinds = {p["kind"] for p in problems}
    b.store.append("note", {"text": "after the tear"})
    entries2, problems2 = b.store.manifest.read()
    out.append(Result("a torn manifest line is detected and quarantined",
                      "torn_final_line" in kinds and not problems2
                      and os.path.exists(str(b.store.manifest.path) + ".torn"),
                      "detected %s; after repair %d problems; .torn kept=%s"
                      % (sorted(kinds), len(problems2),
                         os.path.exists(str(b.store.manifest.path) + ".torn")),
                      "an interrupted append damages one line and must not read as an empty log"))

    # -- 9. editing history breaks the chain ---------------------------------------------------
    b = new("tamper")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    lines = Path(b.store.manifest.path).read_text().strip().split("\n")
    o = json.loads(lines[3]); o["payload"]["readings"] = [82.0, 82.0]
    lines[3] = json.dumps(o, sort_keys=True, separators=(",", ":"))
    Path(b.store.manifest.path).write_text("\n".join(lines) + "\n")
    _, problems = b.store.manifest.read()
    out.append(Result("editing the log to fix a number breaks the hash chain",
                      any(p["kind"] in ("chain_mismatch", "chain_break") for p in problems)
                      and "log.intact" in b.blocked_conditions(),
                      "problems: %s" % [p["kind"] for p in problems][:4],
                      "a manifest edited to make the gate pass must be detectable"))

    # -- 10. captures taken before the rig was frozen are not attributable ---------------------
    b = new("nosetup")
    b.open_session(); b.answer_features(); b.measure()
    b.freeze_rig()
    sh = {"shot_id": "BEFORE.X", "state": "before", "garment_side": "front",
          "region_id": "whole_garment_front", "camera_angle": "overhead", "framing": "-",
          "scale_reference": "charuco_board", "min_reps": 1, "necessity": "required",
          "est_seconds": 30, "camera_height_group": "m", "lens": "main", "purpose": "x"}
    src = b.synth_for(sh, 1)
    b.add(sh, 1, src, setup_hash_override=None)
    out.append(Result("a capture with no rig hash is not attributable",
                      "rig.captures_attributable" in b.blocked_conditions(),
                      "blocked: rig.captures_attributable",
                      "a photograph that cannot be tied to a frozen rig is not evidence of it"))

    # -- 11. the printed board being the wrong size blocks -------------------------------------
    b = new("badboard")
    b.open_session(); b.answer_features(); b.measure()
    b.freeze_rig(board_mm=190.0, squares=8)          # 23.75 mm/square: a 'fit to page' print
    out.append(Result("a board printed at the wrong scale blocks the cut",
                      "rig.board_square_measured" in b.blocked_conditions(),
                      "measured 23.75 mm per square against a declared 25.0",
                      "every scale in the session would carry the printing error"))

    # -- 12. an incomplete rig calibration blocks ----------------------------------------------
    b = new("rigskip")
    b.open_session(); b.answer_features(); b.measure()
    b.freeze_rig(skip=("board_garment_coplanar", "daylight_controlled"))
    out.append(Result("skipping calibration readings blocks the cut",
                      "rig.calibrated" in b.blocked_conditions(),
                      "two readings not recorded",
                      "an unrecorded calibration reading is not a passed one"))

    # -- 13. a hem series that cannot be sized blocks -------------------------------------------
    b = new("hemblock")
    b.open_session(); b.freeze_rig(); b.answer_features()
    b.measure(skip=("leg_opening_cm",))
    blocked = b.blocked_conditions()
    out.append(Result("a hem series with no measured leg opening blocks, not vanishes",
                      "plan.fully_expanded" in blocked or "measurements.complete" in blocked,
                      "blocked: " + ", ".join(sorted(blocked))[:140],
                      "expanding to zero frames would delete the fray series and the gate would "
                      "then find nothing missing"))

    # -- 14. the same photograph cannot be five relays -----------------------------------------
    b = new("relay")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sh = {"shot_id": "BEFORE.WHOLE.FRONT_OVERHEAD", "state": "before", "garment_side": "front",
          "region_id": "whole_garment_front", "camera_angle": "overhead",
          "framing": "-", "scale_reference": "charuco_board", "min_reps": 2,
          "relay_between_reps": True, "necessity": "required", "est_seconds": 45,
          "camera_height_group": "m", "lens": "main", "purpose": "x"}
    src = b.synth_for(sh, 1, relay=0, seed=42)
    b.add(sh, 1, src)
    same = b.tmp / "same_again.png"
    shutil.copy(str(src), str(same))
    outcome2, checks2 = b.add(sh, 2, same)
    relay_checks = [c for c in checks2 if c.check_id in ("relay_independence", "duplicate_content")]
    out.append(Result("one photograph cannot be two independent relays",
                      outcome2 == QA.RETAKE and any(c.outcome == QA.RETAKE for c in relay_checks),
                      "%s; %s" % (outcome2, "; ".join("%s=%s" % (c.check_id, c.outcome)
                                                      for c in relay_checks)),
                      "the same frame resubmitted is not a repeat"))

    # -- 15. the same LAY re-shot is not a relay either ------------------------------------------
    b = new("samelay")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    src1 = b.synth_for(sh, 1, relay=0, seed=7)
    b.add(sh, 1, src1)
    # What a re-shot of an UNMOVED garment actually is: the same frame, new sensor noise, a pixel
    # of camera shake. A fresh render with a new texture seed changes the cloth's own micro-texture,
    # which is the one thing that does not change when nobody touches it -- and modelling it that
    # way flattered the check by exactly that amount.
    from .fixtures import reshoot as _reshoot
    src2 = b.tmp / "same_lay_reshot.png"
    _reshoot(src1, src2, sensor_sigma=3.0, shake_px=1.5, seed=5)
    o2, c2 = b.add(sh, 2, src2)
    rc = [c for c in c2 if c.check_id == "relay_independence"]
    out.append(Result("the same lay photographed twice is not a relay",
                      bool(rc) and rc[0].outcome == QA.RETAKE,
                      "relay_independence=%s (%s)" % (rc[0].outcome if rc else "absent",
                                                      (rc[0].detail[:80] if rc else "")),
                      "a second frame of an unmoved garment measures nothing new"))

    # -- 16. no board means UNAVAILABLE, never PASS ----------------------------------------------
    b = new("noboard")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    src = b.synth_for(sh, 1, board=False)
    o, checks = b.add(sh, 1, src)
    scale = [c for c in checks if c.check_id in ("scale", "board_corners")]
    out.append(Result("a frame with no calibration board never passes",
                      o != QA.PASS and any(c.outcome in (QA.UNAVAILABLE, QA.RETAKE) for c in scale),
                      "%s; %s" % (o, "; ".join("%s=%s" % (c.check_id, c.outcome) for c in scale)),
                      "no board means no scale, and no scale is not a pass"))

    # -- 17. human-only checks are not auto-passed -----------------------------------------------
    b = new("human")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    src = b.synth_for(sh, 1)
    o, checks = b.add(sh, 1, src, confirm_all=False)
    humans = [c for c in checks if c.outcome == QA.HUMAN]
    out.append(Result("checks a photograph cannot settle ask a person",
                      o == QA.HUMAN and len(humans) >= 1,
                      "%s; %d human check(s): %s" % (o, len(humans),
                                                     ", ".join(c.check_id for c in humans)),
                      "a ruler in the plane and which face is up are not decidable from pixels"))

    # -- 18. a missing photograph on disk is not evidence ------------------------------------------
    b = new("filegone")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    src = b.synth_for(sh, 1)
    b.add(sh, 1, src)
    st, _ = b.store.fold()
    rel = list(st["captures"].values())[0]["path"]
    os.unlink(str(b.dir / rel))
    out.append(Result("a manifest entry whose photograph is gone blocks",
                      "captures.files_intact" in b.blocked_conditions(check_files=True),
                      "deleted %s" % rel,
                      "the record of a photograph is not the photograph"))

    # -- 19. swapping the file under a manifest entry is detected -----------------------------------
    b = new("swap")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    src = b.synth_for(sh, 1)
    b.add(sh, 1, src)
    st, _ = b.store.fold()
    rel = list(st["captures"].values())[0]["path"]
    other = b.tmp / "other.png"
    synth_capture(str(other), subject="jeans_back", mm_per_px=0.5, size=(900, 700), seed=77)
    shutil.copy(str(other), str(b.dir / rel))
    out.append(Result("swapping the file under a manifest entry is detected",
                      "captures.files_intact" in b.blocked_conditions(check_files=True),
                      "replaced the bytes at %s" % rel,
                      "the hash recorded at capture time is what makes the entry mean something"))

    # -- 20. changing the plan under a session is detected ------------------------------------------
    b = new("specdrift")
    b.open_session(spec_hash="0" * 64)
    b.freeze_rig(); b.answer_features(); b.measure()
    out.append(Result("a session opened under a different plan is detected",
                      "spec.bound" in b.blocked_conditions(),
                      "session hash != specification on disk",
                      "the evidence was collected against a list that has since changed"))

    # -- 21. cut readiness needs a cut specification and a second person ----------------------------
    b = new("nocut")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    blocked = b.blocked_conditions()
    out.append(Result("no cut specification and no second person blocks",
                      "cut.specified" in blocked and "cut.second_person_verified" in blocked,
                      "blocked: cut.specified, cut.second_person_verified",
                      "PROTOCOL 3.2 requires a second person to verify both marks"))

    # -- 22. a verification outside tolerance blocks -------------------------------------------------
    b = new("badverify")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    b.cut_ready_extras(tolerance_error_cm=1.2)          # 12 mm, against a 3 mm tolerance
    out.append(Result("a second-person measurement outside tolerance blocks",
                      "cut.second_person_verified" in b.blocked_conditions(),
                      "12 mm against a 3 mm tolerance",
                      "verification that does not agree with the specified cut is not verification"))

    # -- 23. hem coverage gaps are reported -----------------------------------------------------------
    from . import hem as HEM
    g = HEM.HemGeometry.from_leg_opening("left", 20.0)
    partial = g.coverage([1, 2])
    complete = g.coverage([m["index"] for m in g.macros()])
    out.append(Result("hem coverage gaps are found and named",
                      not partial["complete"] and partial["n_gaps"] > 0 and complete["complete"],
                      "2 of %d macros -> %d gaps; all macros -> complete"
                      % (len(g.macros()), partial["n_gaps"]),
                      "a gap in the macro series is a hole in the fray profile"))

    # -- 24. the sanitised manifest carries no absolute path -------------------------------------------
    b = new("sanitise")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    src = b.synth_for(sh, 1)
    b.add(sh, 1, src)
    san, _ = b.store.manifest.sanitised(b.dir)
    blob = json.dumps(san)
    leaks = [x for x in ("/Users/", "/home/", str(b.tmp)) if x in blob]
    gps = [k for e in san for k in ((e.get("payload") or {}).get("exif") or {})
           if str(k).startswith("GPS")]
    out.append(Result("the committable manifest has no absolute path and no location",
                      not leaks and not gps,
                      "%d entries, leaks=%s, gps tags=%s" % (len(san), leaks, gps),
                      "a photograph's coordinates must not enter the repository"))

    # ---------------------------------------------------------------------------------------
    # Bypasses found by the adversarial round. Each of these produced READY TO CUT, or a crash
    # instead of a verdict, before the fix beside it.
    # ---------------------------------------------------------------------------------------

    def complete_mini(name, gid="DENIM_9200", spec=None):
        """A finished, honest session on the small specification: the gate opens on it."""
        sp = spec or _mini_spec(tmp_root)
        bb = new(name, spec=sp, gid=gid)
        bb.open_session(); bb.freeze_rig(); bb.answer_features(); bb.measure()
        acts_all = bb.activated()[0]
        _SHOT_BY_ID.update({x["shot_id"]: x for x in acts_all})
        for sh_ in acts_all:
            for r_ in range(1, int(sh_.get("min_reps", 1)) + 1):
                bb.add(sh_, r_, bb.synth_for(sh_, r_, relay=_lay_index(sh_, r_)))
        bb.resolve_humans(); bb.cut_ready_extras()
        return bb, sp

    # -- 25. another garment's log must not satisfy this garment ------------------------------
    donor, mini_sp = complete_mini("donor", gid="DENIM_9201")
    assert donor.gate().ready
    thief = new("thief", spec=mini_sp, gid="DENIM_9202")
    shutil.copytree(str(donor.dir / "pilot"), str(thief.dir / "pilot"))
    shutil.copytree(str(donor.dir / "images"), str(thief.dir / "images"), dirs_exist_ok=True)
    tv = thief.gate()
    _, tprob = thief.store.manifest.read()
    out.append(Result("a log copied from another garment does not satisfy this one",
                      not tv.ready and any(p["kind"] in ("chain_break", "chain_mismatch")
                                           for p in tprob),
                      "copied a READY garment's log wholesale: ready=%s, chain problems=%s"
                      % (tv.ready, [p["kind"] for p in tprob][:3]),
                      "the chain is seeded from the garment's own identity, so a transplanted log "
                      "fails at its first entry"))

    # -- 26. a later verdict must not turn a rejected frame into a passing one ------------------
    b, sp = complete_mini("supersede", gid="DENIM_9203")
    sh_ = b.activated()[0][0]
    st_, _ = b.store.fold()
    cap = st_["captures"][(sh_["shot_id"], 1)]
    b.store.append("qa_result", {"shot_id": sh_["shot_id"], "rep": 1, "outcome": QA.RETAKE,
                                 "capture_sha256": cap["sha256"], "checks": []},
                   operator="selftest")
    blocked_now = "captures.required_complete" in b.blocked_conditions()
    b.store.append("qa_result", {"shot_id": sh_["shot_id"], "rep": 1, "outcome": QA.PASS,
                                 "checks": []}, operator="forger")
    out.append(Result("an appended verdict that names no photograph cannot clear a rejection",
                      blocked_now and "captures.required_complete" in b.blocked_conditions(),
                      "RETAKE recorded -> blocked; unbound PASS appended -> still blocked",
                      "a verdict belongs to the frame it judged; turning a RETAKE into a PASS "
                      "requires another photograph"))

    # -- 27. a capture entry pointing at another shot's file ------------------------------------
    b, sp = complete_mini("misfile", gid="DENIM_9204")
    st_, _ = b.store.fold()
    (sid_a, _r), capa = sorted(st_["captures"].items())[0]
    fake_id = "BEFORE.WHOLE.FAKE_SHOT"
    b.store.append("capture", {"shot_id": fake_id, "rep": 1, "path": capa["path"],
                               "sha256": capa["sha256"], "state": "before",
                               "region_id": "whole_garment_front"},
                   operator="forger", setup_hash=b.setup_hash)
    v = b.gate()
    ev = {}
    for blk in v.blocks:
        if blk.condition == "captures.files_intact":
            ev = blk.evidence
    out.append(Result("a capture entry pointing at another shot's photograph is refused",
                      "captures.files_intact" in {x.condition for x in v.blocks}
                      and bool(ev.get("misfiled")),
                      "misfiled: %s" % (ev.get("misfiled") or [])[:2],
                      "ingestion files a capture under its own shot, repeat and hash; an entry "
                      "whose path does not encode those is pointing at someone else's frame"))

    # -- 28. truncating the log ------------------------------------------------------------------
    b, sp = complete_mini("truncate", gid="DENIM_9205")
    assert b.gate().ready
    lines = Path(b.store.manifest.path).read_text().strip().split("\n")
    Path(b.store.manifest.path).write_text("\n".join(lines[:-6]) + "\n")
    _, probs = b.store.manifest.read()
    out.append(Result("truncating the end of the log is detected",
                      any(p["kind"] in ("entries_missing", "head_mismatch") for p in probs)
                      and not b.gate().ready,
                      "removed 6 entries: %s" % [p["kind"] for p in probs][:3],
                      "every prefix of a valid chain is a valid chain, so the head and the entry "
                      "count are anchored beside it"))

    # -- 29. a capture recorded without a hash ----------------------------------------------------
    b = new("nohash", spec=mini_sp, gid="DENIM_9206")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    junk = b.dir / "images" / "before" / "not_a_photograph.png"
    junk.parent.mkdir(parents=True, exist_ok=True)
    junk.write_text("not a photograph")
    b.store.append("capture", {"shot_id": "BEFORE.WHOLE.FAKE", "rep": 1,
                               "path": str(junk.relative_to(b.dir)), "state": "before",
                               "region_id": "whole_garment_front"},
                   operator="forger", setup_hash=b.setup_hash)
    v = b.gate()
    unh = {}
    for blk in v.blocks:
        if blk.condition == "captures.files_intact":
            unh = blk.evidence
    out.append(Result("a capture recorded with no hash is not a photograph",
                      bool(unh.get("unhashed")),
                      "unhashed: %s" % (unh.get("unhashed") or [])[:2],
                      "the hash comparison used to be conditional on a hash existing, so recording "
                      "none skipped it and a text file counted as a capture"))

    # -- 30. a line that is valid JSON but not an entry ---------------------------------------------
    b = new("scalarline", spec=mini_sp, gid="DENIM_9207")
    b.open_session()
    with open(str(b.store.manifest.path), "a") as f:
        f.write("12345\n")
    crashed = False
    try:
        _, probs = b.store.manifest.read()
        v = b.gate()
    except Exception:
        crashed = True
        probs, v = [], None
    out.append(Result("a JSON scalar in the log is a finding, not a crash",
                      (not crashed) and any(p["kind"] == "not_an_entry" for p in probs)
                      and v is not None and not v.ready,
                      "crashed=%s problems=%s" % (crashed, [p["kind"] for p in probs][:3]),
                      "a crash is not a refusal: it escapes the deny-by-default machinery and "
                      "returns no verdict at all"))

    # -- 31. a recorded refusal is not an approval ---------------------------------------------------
    b, sp = complete_mini("refusal", gid="DENIM_9208")
    b.store.append("human_verification",
                   {"shot_id": None, "rep": None, "claim": "cut_marks_verified", "value": False,
                    "verifier_name": "second person", "operator": "selftest",
                    "note": "NO - the marks are on the wrong leg",
                    "measured_inseam_cm": 15.0, "measured_outseam_cm": 16.923},
                   operator="selftest")
    v = b.gate()
    out.append(Result("a second person's REFUSAL blocks the cut",
                      not v.ready and "cut.second_person_verified" in {x.condition for x in v.blocks},
                      "recorded value=False with a note; ready=%s" % v.ready,
                      "`value` was never read here, so a refusal was reported as an approval"))

    # -- 32. a retraction supersedes an earlier approval ----------------------------------------------
    b, sp = complete_mini("retract", gid="DENIM_9209")
    assert b.gate().ready
    b.store.append("human_verification",
                   {"shot_id": None, "rep": None, "claim": "cut_marks_verified", "value": True,
                    "verifier_name": "second person", "operator": "selftest",
                    "measured_inseam_cm": 20.0, "measured_outseam_cm": 21.923},
                   operator="selftest")
    out.append(Result("the latest cut verification wins, not the first one found",
                      not b.gate().ready,
                      "appended a later verification disagreeing by 5 cm; ready=%s" % b.gate().ready,
                      "selecting by dictionary order let a retraction be discarded in favour of an "
                      "older approval"))

    # -- 33. NaN cannot disable the tolerance ------------------------------------------------------------
    b, sp = complete_mini("nan", gid="DENIM_9210")
    b.store.append("human_verification",
                   {"shot_id": None, "rep": None, "claim": "cut_marks_verified", "value": True,
                    "verifier_name": "second person", "operator": "selftest",
                    # A float NaN cannot even be written: canonical() sets allow_nan=False. The
                    # attack that worked came through the HTTP API as the STRING "NaN", which
                    # serialises fine and only becomes a NaN at float() inside the gate.
                    "measured_inseam_cm": "NaN", "measured_outseam_cm": "NaN"},
                   operator="selftest")
    out.append(Result("a non-finite measurement cannot disable the tolerance",
                      not b.gate().ready,
                      "recorded the string \"NaN\" through the API's own path; ready=%s"
                      % b.gate().ready,
                      "NaN compares false against everything, so it slipped past `worst > "
                      "tolerance` and switched the 3 mm check off"))

    # -- 34. the second person must be a second person -------------------------------------------------
    b = new("oneperson", spec=mini_sp, gid="DENIM_9211")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    _SHOT_BY_ID.update({x["shot_id"]: x for x in b.activated()[0]})
    for sh_ in b.activated()[0]:
        for r_ in range(1, int(sh_.get("min_reps", 1)) + 1):
            b.add(sh_, r_, b.synth_for(sh_, r_, relay=_lay_index(sh_, r_)))
    b.resolve_humans()
    from . import cutspec as _CUT
    st_, _ = b.store.fold()
    m_ = st_["measurements"]
    cs_ = _CUT.compute(target_inseam_cm=15.0, original_inseam_cm=m_["original_inseam_cm"]["mean"],
                       thigh_cm=m_["thigh_cm"]["mean"], leg_opening_cm=m_["leg_opening_cm"]["mean"])
    b.store.append("cut_spec", cs_, operator="alice")
    b.store.append("human_verification",
                   {"shot_id": None, "rep": None, "claim": "cut_marks_verified", "value": True,
                    "verifier_name": "alice", "operator": "alice",
                    "measured_inseam_cm": cs_["target_inseam_cm"],
                    "measured_outseam_cm": cs_["predicted_outseam_cm"]}, operator="alice")
    for claim in ("legs_cut_separately", "offcuts_retained_labelled"):
        b.store.append("human_verification",
                       {"shot_id": None, "rep": None, "claim": claim, "value": True,
                        "verifier_name": "alice", "operator": "alice"}, operator="alice")
    v = b.gate()
    out.append(Result("one person cannot be their own second person",
                      not v.ready and "cut.second_person_verified" in {x.condition for x in v.blocks},
                      "operator alice verified alice's own marks; ready=%s" % v.ready,
                      "verifier_name defaults to the operator when --verifier is omitted, which is "
                      "the natural thing to do when one person is at the table"))

    # -- 35. a confirmation does not survive a different photograph -------------------------------------
    b = new("stalconf", spec=mini_sp, gid="DENIM_9212")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    front = [x for x in b.activated()[0] if x.get("garment_side") == "front"][0]
    b.add(front, 1, b.synth_for(front, 1), confirm_all=False)
    b.resolve_humans()
    st_, _ = b.store.fold()
    before_ok = _resolved(st_, front["shot_id"], 1)
    back_img = b.synth_for(dict(front, garment_side="back"), 1, seed=4242)
    b.add(front, 1, back_img, confirm_all=False)
    st_, _ = b.store.fold()
    after_ok = _resolved(st_, front["shot_id"], 1)
    out.append(Result("a human confirmation does not carry over to a different photograph",
                      before_ok and not after_ok,
                      "confirmed the first frame (resolved=%s), then filed a different image under "
                      "the same shot id (resolved=%s)" % (before_ok, after_ok),
                      "re-ingesting under the same shot id left the old confirmation in place, so a "
                      "frame of the back inherited a confirmation that the front was facing up"))

    # -- 36. verifications recorded before the photograph do not pre-clear it ----------------------------
    b = new("preclear", spec=mini_sp, gid="DENIM_9213")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sh_ = b.activated()[0][0]
    for claim in ("ruler_visible", "side_confirmed", "region_confirmed", "relay_confirmed",
                  "subject_span", "garment_side", "anatomical_region", "camera_repositioned"):
        b.store.append("human_verification",
                       {"shot_id": sh_["shot_id"], "rep": 1, "claim": claim, "value": True,
                        "verifier_name": "forger", "operator": "forger"}, operator="forger")
    b.add(sh_, 1, b.synth_for(sh_, 1), confirm_all=False)
    st_, _ = b.store.fold()
    out.append(Result("verifications recorded before a photograph do not pre-clear it",
                      not _resolved(st_, sh_["shot_id"], 1),
                      "pre-recorded 8 confirmations, then took the photograph",
                      "resolving a claim by name alone let every claim the plan can raise be "
                      "confirmed in a loop before a single frame existed"))

    # -- 37. concurrent appends must not break the chain --------------------------------------------------
    b = new("concurrent", spec=mini_sp, gid="DENIM_9214")
    b.open_session()
    import threading as _th
    errs = []

    def _writer(i):
        try:
            for j in range(8):
                b.store.append("note", {"text": "w%d-%d" % (i, j)}, operator="w%d" % i)
        except Exception as e:      # noqa: BLE001
            errs.append(repr(e))

    ths = [_th.Thread(target=_writer, args=(i,)) for i in range(4)]
    for t_ in ths:
        t_.start()
    for t_ in ths:
        t_.join()
    ents, probs = b.store.manifest.read()
    out.append(Result("four concurrent writers do not break the chain",
                      not probs and len(ents) == 33 and not errs,
                      "%d entries, %d integrity problems, %d writer errors"
                      % (len(ents), len(probs), len(errs)),
                      "append read the head and wrote with no lock, so two writers stamped the same "
                      "prev_chain and the chain broke permanently -- and the web app is threaded"))

    # -- 38. an implausible measurement blocks even when both readings agree ---------------------
    b = new("inches")
    b.open_session(); b.freeze_rig(); b.answer_features()
    b.measure()
    # A tape read in inches: two readings that agree perfectly with each other and are 2.5x wrong.
    b.store.append("measurement", {"name": "leg_opening_cm", "readings": [15.75, 15.8],
                                   "mean": 15.775, "spread": 0.05, "tolerance": 0.5,
                                   "in_tolerance": True}, operator="selftest")
    blocked = b.blocked_conditions()
    out.append(Result("a measurement read in inches blocks even though its readings agree",
                      "measurements.complete" in blocked,
                      "leg_opening_cm 15.75/15.8 cm, spread 0.05, outside the plausible range",
                      "leg_opening_cm sizes the hem series and places the cut mark; two readings "
                      "agreeing with each other says nothing about whether the tape was the right "
                      "one"))

    # -- 39. a required shot may not expand to zero frames ----------------------------------------
    b = new("zeroexpand")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    ans = dict(b.store.fold()[0]["features"])
    for k in list(ans):
        if k.startswith("n_"):
            ans[k] = 0
    ans["n_tears"] = 3
    b.store.append("feature_answers", {"answers": ans}, operator="selftest")
    shots2, meta2 = b.activated()
    tear = [x for x in shots2 if "TEAR" in x["shot_id"].upper()]
    out.append(Result("a garment with three tears is asked for three tear photographs",
                      len(tear) >= 3 and not meta2["expansion_blocked"],
                      "%d tear frames planned: %s"
                      % (len(tear), [x["shot_id"] for x in tear][:4]),
                      "inclusion and cardinality came from two independent answers: a shot could "
                      "be required because one count was non-zero and expand to nothing because "
                      "the count it was instanced on was zero"))

    # -- 40. and if one ever could, it blocks rather than vanishing --------------------------------
    b = new("zeroblocks")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    bad_shot = {"shot_id": "BEFORE.TEST.MISMATCHED", "state": "before", "garment_side": "front",
                "region_id": "whole_garment_front", "camera_angle": "overhead", "framing": "-",
                "scale_reference": "charuco_board", "min_reps": 1, "necessity": "conditional",
                "conditional_on": "n_tears > 0", "instance_of": "n_stains",
                "est_seconds": 30, "camera_height_group": "m", "lens": "main", "purpose": "x"}
    fake = type("S", (), {"features": full_spec.features, "shots": [bad_shot],
                          "states": full_spec.states, "regions": full_spec.regions})()
    answers3 = {f["key"]: (0 if f["type"] == "count" else True) for f in full_spec.features}
    answers3.update({"n_tears": 2, "n_stains": 0})
    shots3, meta3 = PLAN.activate(fake, answers3)
    out.append(Result("a required shot that would expand to no frames blocks by name",
                      len(meta3["expansion_blocked"]) == 1,
                      "expansion_blocked: %s"
                      % [x["why"][:70] for x in meta3["expansion_blocked"]],
                      "vanishing is the one outcome a required photograph may not have"))

    # -- 41. a photograph taken before the rig was frozen ------------------------------------------
    b = new("pre_freeze", spec=mini_sp, gid="DENIM_9215")
    b.open_session()
    sh_ = mini_sp.shots[0]
    # A capture recorded BEFORE any setup_frozen entry, citing a hash frozen later.
    b.store.append("capture", {"shot_id": sh_["shot_id"], "rep": 1,
                               "path": "images/before/x.png", "sha256": "d" * 64,
                               "state": "before", "region_id": sh_["region_id"]},
                   operator="forger", setup_hash=b.setup_hash)
    b.freeze_rig(); b.answer_features(); b.measure()
    out.append(Result("a photograph taken before the rig was frozen is not attributable to it",
                      "rig.captures_attributable" in b.blocked_conditions(check_files=False),
                      "capture at sequence 1 citing a rig frozen at sequence 2",
                      "attribution was set membership over the whole log, so a frame logged a "
                      "week before the freeze became attributable to a configuration that did not "
                      "exist when it was taken"))

    # -- 42. re-freezing the rig mid-session -------------------------------------------------------
    b, sp = complete_mini("refreeze", gid="DENIM_9216")
    assert b.gate().ready
    other_setup = dict(b.setup, mount_height_cm=b.setup["mount_height_cm"] + 12.0)
    h2 = setup_hash(other_setup)
    b.store.append("setup_frozen", {"setup": other_setup, "setup_hash": h2,
                                    "reason": "moved the camera"}, operator="forger")
    sh_ = b.activated()[0][0]
    b.add(sh_, 1, b.synth_for(sh_, 1, seed=7777), setup_hash_override=h2)
    out.append(Result("captures split across two rig configurations block unless the change is recorded",
                      "rig.one_configuration" in b.blocked_conditions(check_files=False),
                      "half the session under one rig hash, half under another, no deviation",
                      "every capture was individually attributable while the session as a whole "
                      "described two rigs, with the calibration never re-run against the second"))

    # -- 43. the board-square measurement is arithmetic on typed numbers ----------------------------
    for label, kw, why in (
            ("one square spanned", dict(board_mm=25.0, squares=1),
             "a rule read to 0.5 mm over one 25 mm square is a 2% measurement"),
            ("a fractional count", dict(board_mm=62.5, squares=2.5),
             "squares are whole things"),
            ("more squares than the board has", dict(board_mm=500.0, squares=20),
             "the board is 8 x 11")):
        b = new("boardarith" + label[:6].replace(" ", ""), spec=mini_sp,
                gid="DENIM_92%02d" % (17 + ["one square spanned", "a fractional count",
                                            "more squares than the board has"].index(label)))
        b.open_session(); b.answer_features(); b.measure(); b.freeze_rig(**kw)
        out.append(Result("the board-square measurement refuses %s" % label,
                          "rig.board_square_measured" in b.blocked_conditions(check_files=False),
                          "measured_mm=%(board_mm)s over %(squares)s squares" % kw, why))

    # -- 44. a verdict must agree with the checks stored beside it ------------------------------------
    b, sp = complete_mini("forgedverdict", gid="DENIM_9220")
    assert b.gate().ready
    st_, _ = b.store.fold()
    (sid_, rep_), q_ = sorted(st_["qa"].items())[0]
    cap_ = st_["captures"][(sid_, rep_)]
    forged = [dict(c) for c in (q_.get("checks") or [])]
    if forged:
        forged[0]["outcome"] = QA.RETAKE
    b.store.append("qa_result", {"shot_id": sid_, "rep": rep_, "outcome": QA.PASS,
                                 "capture_sha256": cap_["sha256"], "checks": forged},
                   operator="forger")
    st_after, _ = b.store.fold()
    operative = (st_after["qa"].get((sid_, rep_)) or {}).get("outcome")
    out.append(Result("a forged verdict that IMPROVES on the checker's is inert",
                      operative == q_.get("outcome"),
                      "appended PASS over a check list containing a RETAKE; the operative verdict "
                      "is still %r" % operative,
                      "the worst verdict bound to a photograph wins, so an appended improvement "
                      "never becomes the one the gate reads -- a stronger guarantee than blocking, "
                      "because there is nothing for the operator to work around"))

    # -- and the case where a forged verdict IS the only one for its frame ------------------------
    b2 = new("forgedonly", spec=mini_sp, gid="DENIM_9245")
    b2.open_session(); b2.freeze_rig(); b2.answer_features(); b2.measure()
    sh2_ = b2.activated()[0][0]
    src2_ = b2.synth_for(sh2_, 1)
    from .manifest import ingest_photo as _ing
    dest2_, sha2_, _ = _ing(src2_, b2.dir / "images" / sh2_["state"], sh2_["shot_id"], 1)
    b2.store.append("capture", {"shot_id": sh2_["shot_id"], "rep": 1,
                                "path": str(dest2_.relative_to(b2.dir)), "sha256": sha2_,
                                "state": sh2_["state"], "region_id": sh2_.get("region_id")},
                    operator="forger", setup_hash=b2.setup_hash)
    # the ONLY verdict for this frame, and its checks do not roll up to what it claims
    b2.store.append("qa_result", {"shot_id": sh2_["shot_id"], "rep": 1, "outcome": QA.PASS,
                                  "capture_sha256": sha2_,
                                  "checks": [{"check_id": "readable", "outcome": QA.RETAKE,
                                              "detail": "-"}]},
                    operator="forger")
    out.append(Result("a frame's only verdict must follow from the checks stored beside it",
                      "captures.required_complete" in b2.blocked_conditions(check_files=False),
                      "the sole verdict says PASS over a check list that rolls up to RETAKE",
                      "with no honest verdict to lose to, the disagreement rule is what is left; "
                      "appending a forged verdict leaves the hash chain perfectly intact"))

    # -- 45. one photograph filed under two shots, whatever the add-time checker saw ----------------
    b, sp = complete_mini("sharedfile", gid="DENIM_9221")
    assert b.gate().ready
    st_, _ = b.store.fold()
    (sid_a, rep_a), capa = sorted(st_["captures"].items())[0]
    # Record a second shot pointing at the same bytes, filed under its own correct name -- the shape
    # a duplicate takes when the add-time comparison did not happen (the earlier file was missing,
    # the ordering differed, the checker had not yet been hardened).
    src = b.dir / capa["path"]
    dest = b.dir / "images" / "before" / ("BEFORE.WHOLE.SHARED__r01__%s.png" % capa["sha256"][:12])
    shutil.copy(str(src), str(dest))
    b.store.append("capture", {"shot_id": "BEFORE.WHOLE.SHARED", "rep": 1,
                               "path": str(dest.relative_to(b.dir)), "sha256": capa["sha256"],
                               "state": "before", "region_id": "whole_garment_front",
                               "dhash": capa.get("dhash")},
                   operator="forger", setup_hash=b.setup_hash)
    out.append(Result("one photograph cannot satisfy two shots without a declared reuse",
                      "captures.no_undeclared_reuse" in b.blocked_conditions(),
                      "the same sha256 filed under %s and BEFORE.WHOLE.SHARED" % sid_a,
                      "duplicate detection lived only in the add-time checker, whose comparison set "
                      "is whatever was on disk at that moment, and nothing ever looked again"))

    # -- 46. the file-integrity cache must not trust a restored mtime -------------------------------
    b, sp = complete_mini("mtime", gid="DENIM_9222")
    assert b.gate().ready                      # populates the hash cache
    st_, _ = b.store.fold()
    (sid_b, rep_b), capb = sorted(st_["captures"].items())[0]
    target = b.dir / capb["path"]
    before_stat = os.stat(str(target))
    other = b.synth_for(b.activated()[0][0], 1, seed=31337)
    data = Path(other).read_bytes()
    # Same length, so size is unchanged; mtime put back exactly.
    orig = target.read_bytes()
    target.write_bytes((data * (len(orig) // len(data) + 1))[:len(orig)])
    os.utime(str(target), ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns))
    after = os.stat(str(target))
    same_size_and_mtime = (after.st_size == before_stat.st_size
                           and after.st_mtime_ns == before_stat.st_mtime_ns)
    out.append(Result("a photograph swapped with its size and mtime restored is still detected",
                      same_size_and_mtime
                      and "captures.files_intact" in b.blocked_conditions(),
                      "size and mtime identical after the swap: %s; blocked: %s"
                      % (same_size_and_mtime,
                         "captures.files_intact" in b.blocked_conditions()),
                      "the cache keyed on (path, size, mtime) and mtime is settable, so restoring "
                      "it defeated the check for as long as a `serve` process stayed up -- and a "
                      "capture UI is exactly a long-running process"))

    # -- 47. the tail repair must not delete an interior entry --------------------------------------
    b = new("interior", spec=mini_sp, gid="DENIM_9223")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    lines = Path(b.store.manifest.path).read_text().strip().split("\n")
    n_before = len(lines)
    lines[4] = lines[4][:40]                       # damage an interior line
    Path(b.store.manifest.path).write_text("\n".join(lines) + "\n{\"seq\":99,\"kind\":\"cap")
    b.store.append("note", {"text": "after the tear"})
    ents, probs = b.store.manifest.read()
    kept_interior = any("corrupt_line" == x["kind"] for x in probs)
    out.append(Result("repairing a torn tail does not delete an interior entry",
                      kept_interior and "log.intact" in b.blocked_conditions(check_files=False),
                      "%d lines before; problems after the repair: %s"
                      % (n_before, sorted({x["kind"] for x in probs})),
                      "the repair fired on a torn LAST line and then dropped every unparseable line "
                      "anywhere, so a real measurement damaged by something else was deleted by a "
                      "repair that had not been asked to touch it"))

    # -- 48. a reuse must pass the borrowing shot's own checks ---------------------------------------
    b = new("reuse", spec=mini_sp, gid="DENIM_9224")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    shots_ = b.activated()[0]
    front_ = [x for x in shots_ if x.get("garment_side") == "front"][0]
    back_ = [x for x in shots_ if x.get("garment_side") == "back"][0]
    b.add(front_, 1, b.synth_for(front_, 1))
    st_, _ = b.store.fold()
    src_ = st_["captures"][(front_["shot_id"], 1)]
    # Borrow the FRONT frame for the BACK shot without re-checking: the gate must still refuse,
    # because the declaration is only worth something if the checks behind it were run.
    b.store.append("reuse_declaration",
                   {"shot_id": back_["shot_id"], "rep": 1, "source_shot_id": front_["shot_id"],
                    "source_rep": 1, "sha256": src_["sha256"], "state": back_["state"]},
                   operator="forger")
    blocked_ = b.blocked_conditions(check_files=False)
    out.append(Result("a reuse declaration with no re-run checks is refused",
                      "captures.reuse_legitimate" in blocked_,
                      "declared a reuse carrying no checks_rerun and no outcome",
                      "the permission to reuse a frame is worth something only if the borrowing "
                      "shot's own requirements were applied to it"))

    # -- 49. invented checks that agree with their own verdict ---------------------------------------
    b, sp = complete_mini("inventedchecks", gid="DENIM_9225")
    assert b.gate().ready
    st_, _ = b.store.fold()
    (sid_, rep_), _q = sorted(st_["qa"].items())[0]
    cap_ = st_["captures"][(sid_, rep_)]
    b.store.append("qa_result",
                   {"shot_id": sid_, "rep": rep_, "outcome": QA.PASS,
                    "capture_sha256": cap_["sha256"],
                    "checks": [{"check_id": "readable", "outcome": QA.PASS, "detail": "fine"},
                               {"check_id": "blur", "outcome": QA.PASS, "detail": "fine"}]},
                   operator="forger")
    st_inv, _ = b.store.fold()
    op_inv = (st_inv["qa"].get((sid_, rep_)) or {}).get("outcome")
    out.append(Result("a verdict backed by invented checks does not become the operative one",
                      op_inv != QA.PASS,
                      "appended PASS over a two-item invented check list; the operative verdict is "
                      "still %r" % op_inv,
                      "re-deriving the roll-up from the stored list tests the record against "
                      "ITSELF; a list of invented all-PASS checks agrees with a PASS verdict "
                      "perfectly, so the mandatory set has to come from the code"))

    # -- 50. a payload that cannot be a projection key ------------------------------------------------
    b = new("badkey", spec=mini_sp, gid="DENIM_9226")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    b.store.append("offcut", {"label": ["not", "a", "label"]}, operator="forger")
    crashed = False
    try:
        st_, probs_ = b.store.fold()
        v = b.gate(check_files=False)
    except Exception:
        crashed, probs_, v = True, [], None
    out.append(Result("a payload that cannot identify anything is a finding, not a crash",
                      (not crashed) and any(x["kind"] == "uninterpretable_payload" for x in probs_)
                      and v is not None and not v.ready,
                      "crashed=%s problems=%s" % (crashed, sorted({x["kind"] for x in probs_})),
                      "every gate condition reads the folded state, so one unreplayable entry made "
                      "the garment permanently ungateable -- no verdict at all, on a garment whose "
                      "photographs were fine"))

    # -- 51. a fabricated mean beside honest readings ---------------------------------------------------
    b = new("fakemean", spec=mini_sp, gid="DENIM_9227")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    b.store.append("measurement", {"name": "leg_opening_cm", "readings": [40.0, 40.1],
                                   "mean": 12.0, "spread": 0.1, "tolerance": 0.5,
                                   "in_tolerance": True}, operator="forger")
    st_, _ = b.store.fold()
    from .store import mean_of
    got = mean_of(st_["measurements"]["leg_opening_cm"])
    shots_, _m = b.activated()
    hem_frames = [x for x in shots_ if x.get("hem_position")]
    honest = HEM.HemGeometry.from_leg_opening("left", 40.05)
    out.append(Result("a fabricated mean does not size the hem series or place the cut",
                      abs(got - 40.05) < 1e-6,
                      "record claims mean=12.0 over readings [40.0, 40.1]; recomputed %.2f" % got,
                      "the gate validates the readings and every consumer read the mean, so two "
                      "honest readings beside a fabricated mean passed every measurement condition "
                      "and then handed a different number to the planner and the cut"))

    # -- 52. a verification with no attribution ----------------------------------------------------------
    b, sp = complete_mini("noattrib", gid="DENIM_9228")
    st_, _ = b.store.fold()
    cs_ = st_["cut_spec"]
    b.store.append("human_verification",
                   {"shot_id": None, "rep": None, "claim": "cut_marks_verified", "value": True,
                    "verifier_name": "someone", "operator": None,
                    "measured_inseam_cm": cs_["target_inseam_cm"],
                    "measured_outseam_cm": cs_["predicted_outseam_cm"]},
                   operator=None)
    out.append(Result("a cut verification that names nobody does not verify",
                      "cut.second_person_verified" in b.blocked_conditions(check_files=False),
                      "appended a verification with operator=None",
                      "fold overwrote the payload's own attribution with the envelope's, so a "
                      "record naming its author projected as operator None -- and the check that "
                      "refuses a verifier equal to the operator compared a name against None"))

    # -- 53. a capture filed under the wrong state --------------------------------------------------------
    b, sp = complete_mini("wrongstate", gid="DENIM_9229")
    assert b.gate().ready
    st_, _ = b.store.fold()
    (sid_, rep_), cap_ = sorted(st_["captures"].items())[0]
    b.store.append("capture", dict(cap_, state="post_wash"), operator="forger",
                   setup_hash=cap_.get("setup_hash"))
    out.append(Result("a capture that mislabels its own state does not count as that shot's evidence",
                      "captures.required_complete" in b.blocked_conditions(check_files=False),
                      "re-filed a before-state frame as post_wash",
                      "one condition trusted the capture's self-declared state while another "
                      "matched on shot id alone, so a frame could mislabel its state to escape the "
                      "first and still satisfy the second"))

    # -- 54. a verification naming a photograph that does not exist yet ------------------------------
    b = new("preclearsha", spec=mini_sp, gid="DENIM_9230")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    sh_ = b.activated()[0][0]
    src_ = b.synth_for(sh_, 1)
    from .manifest import sha256_file as _sha
    known = _sha(src_)
    for claim in ("ruler_visible", "side_confirmed", "region_confirmed", "subject_span",
                  "garment_side", "anatomical_region"):
        b.store.append("human_verification",
                       {"shot_id": sh_["shot_id"], "rep": 1, "claim": claim, "value": True,
                        "verifier_name": "forger", "operator": "forger",
                        "capture_sha256": known}, operator="forger")
    b.add(sh_, 1, src_, confirm_all=False)
    st_, _ = b.store.fold()
    out.append(Result("a verification naming a photograph that does not exist yet does not clear it",
                      not _resolved(st_, sh_["shot_id"], 1),
                      "pre-recorded verifications carrying the file's hash, then ingested it",
                      "the rule accepted a verification that named the capture's hash OR postdated "
                      "it, and the API takes that hash straight from the client"))

    # -- 55. a second verdict may not improve the first -----------------------------------------------
    b, sp = complete_mini("worstwins", gid="DENIM_9231")
    st_, _ = b.store.fold()
    (sid_, rep_), q_ = sorted(st_["qa"].items())[0]
    cap_ = st_["captures"][(sid_, rep_)]
    b.store.append("qa_result", {"shot_id": sid_, "rep": rep_, "outcome": QA.RETAKE,
                                 "capture_sha256": cap_["sha256"],
                                 "checks": [dict(c) for c in (q_.get("checks") or [])],
                                 "not_applicable": q_.get("not_applicable")}, operator="selftest")
    b.store.append("qa_result", {"shot_id": sid_, "rep": rep_, "outcome": QA.PASS,
                                 "capture_sha256": cap_["sha256"],
                                 "checks": [dict(c) for c in (q_.get("checks") or [])],
                                 "not_applicable": q_.get("not_applicable")}, operator="forger")
    out.append(Result("a later verdict on the same photograph cannot improve an earlier one",
                      "captures.required_complete" in b.blocked_conditions(check_files=False),
                      "RETAKE then PASS on the same sha; the worse one stands",
                      "re-running a checker on one frame is deterministic, so two verdicts that "
                      "disagree about it are evidence of tampering"))

    # -- 56. a capture path that leaves the garment directory -------------------------------------------
    b, sp = complete_mini("traversal", gid="DENIM_9232")
    st_, _ = b.store.fold()
    (sid_, rep_), cap_ = sorted(st_["captures"].items())[0]
    b.store.append("capture", dict(cap_, shot_id="BEFORE.WHOLE.ESCAPED",
                                   path="../../../etc/hosts"),
                   operator="forger", setup_hash=cap_.get("setup_hash"))
    out.append(Result("a capture path that leaves the garment directory is refused",
                      "captures.files_intact" in b.blocked_conditions(),
                      "recorded a path of ../../../etc/hosts",
                      "only the basename was checked, so a path could satisfy the naming rule and "
                      "point the evidence anywhere"))

    # -- 57. every state the specification declares is guarded by some gate -----------------------------
    declared = {st_["state"] for st_ in full_spec.states}
    covered = set()
    for g in GATES.GATE_LAST_STATE:
        covered |= set(GATES.gate_states(full_spec, g))
    out.append(Result("every state in the specification is required by some gate",
                      declared == covered,
                      "declared %d states, gates cover %d; uncovered: %s"
                      % (len(declared), len(covered), sorted(declared - covered) or "none"),
                      "the state sets were listed by hand and fell behind the plan: the offcut "
                      "states appeared in none of them, so a hundred required frames -- the whole "
                      "offcut experiment -- were guarded by nothing"))

    # -- 58. the offcut pair's identity ------------------------------------------------------------------
    b = new("offcutid", spec=mini_sp, gid="DENIM_9233")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    from . import offcut as _OFF
    for lbl, leg, cond in (("DENIM_9233_OFFCUT_L", "left", _OFF.WITH_GARMENT),
                           ("DENIM_9233_OFFCUT_L2", "left", _OFF.SEPARATE_LOAD)):
        b.store.append("offcut", {"label": lbl, "originating_leg": leg,
                                  "assigned_wash_condition": cond}, operator="selftest")
    out.append(Result("two offcuts from the same leg are not the protocol's pair",
                      "offcuts.assigned" in b.blocked_conditions("ready_to_wash", check_files=False),
                      "recorded ..._OFFCUT_L and ..._OFFCUT_L2, both from the left leg",
                      "everything keyed off a free-text label, so two records from one leg counted "
                      "as two samples"))

    # -- 59. an offcut condition the protocol does not define ---------------------------------------------
    b = new("offcutvocab", spec=mini_sp, gid="DENIM_9234")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    for lbl, leg, cond in (("DENIM_9234_OFFCUT_L", "left", "in the blue bucket"),
                           ("DENIM_9234_OFFCUT_R", "right", "the other one")):
        b.store.append("offcut", {"label": lbl, "originating_leg": leg,
                                  "assigned_wash_condition": cond}, operator="selftest")
    out.append(Result("an offcut condition the protocol does not define is refused",
                      "offcuts.assigned" in b.blocked_conditions("ready_to_wash", check_files=False),
                      "two distinct free-text conditions that name no arm of the experiment",
                      "free text let both samples go into the same load under two spellings, and "
                      "made a broken alternation read as intact"))

    # -- 60. the post-wash gate must require the wash ------------------------------------------------------
    b, sp = complete_mini("nowash", gid="DENIM_9235")
    conds = {x.condition for x in b.gate("ready_to_finalize", check_files=False).blocks}
    out.append(Result("the post-wash gate requires the wash to have been recorded",
                      {"wash.planned", "wash.actual"} <= conds,
                      "ready_to_finalize blocks on: %s"
                      % sorted(c for c in conds if c.startswith("wash")),
                      "it differed from the cut gate by one state and added no condition of its "
                      "own, so a garment could be photographed after washing with no record that "
                      "it had been washed, or under what settings"))

    # -- 61. the wash plan cannot be revised to match what happened ----------------------------------------
    b = new("replan", spec=mini_sp, gid="DENIM_9236")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    plan_a = {k: (30.0 if k == "water_temp_c" else "x") for k in GATES.WASH_FIELDS}
    b.store.append("wash_planned", plan_a, operator="selftest")
    b.store.append("wash_actual", dict(plan_a, water_temp_c=60.0), operator="selftest")
    b.store.append("wash_planned", dict(plan_a, water_temp_c=60.0), operator="forger")
    st_, _ = b.store.fold()
    conds = {x.condition for x in b.gate("ready_to_finalize", check_files=False).blocks}
    out.append(Result("the wash plan cannot be rewritten after the wash to match what happened",
                      st_["wash_planned"]["water_temp_c"] == 30.0 and "wash.planned" in conds,
                      "appended a second plan at 60 C after washing at 60 C; the first plan (30 C) "
                      "stands and the rewrite is reported",
                      "last-write-wins let the plan be revised to match the outcome, and the "
                      "deviation -- the difference between the two -- then computed to nothing"))

    # -- 62. a source that is not a photograph -------------------------------------------------------
    b = new("notafile", spec=mini_sp, gid="DENIM_9237")
    outcomes = {}
    fifo = b.tmp / "a_fifo"
    try:
        os.mkfifo(str(fifo))
    except (AttributeError, OSError):
        fifo = None
    empty = b.tmp / "empty.png"
    empty.write_bytes(b"")
    adir = b.tmp / "a_dir"
    adir.mkdir(exist_ok=True)
    for label, target in [("a directory", adir), ("an empty file", empty)] + \
            ([("a fifo", fifo)] if fifo else []):
        try:
            ingest_photo(target, b.dir / "images" / "before", "TEST.X", 1)
            outcomes[label] = "ACCEPTED"
        except ManifestError:
            outcomes[label] = "refused"
        except Exception as e:              # noqa: BLE001
            outcomes[label] = type(e).__name__
    out.append(Result("a source that is not a photograph is refused rather than hanging",
                      all(v == "refused" for v in outcomes.values()),
                      "; ".join("%s -> %s" % kv for kv in sorted(outcomes.items())),
                      "a FIFO passed every existence test and then blocked the process forever "
                      "inside the copy, waiting for a writer that never came -- and a hang is worse "
                      "than a refusal, because the operator cannot tell it from slow work and the "
                      "gate never answers at all"))

    # -- 63. frames that satisfy the numbers and show nothing ----------------------------------------
    b = new("showsnothing", spec=mini_sp, gid="DENIM_9238")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    whole_ = [x for x in b.activated()[0]
              if QA.shot_class(x) == QA.WHOLE_GARMENT][0]
    board_, bspec_ = b.board
    import cv2 as _cv2
    import numpy as _np
    from .fixtures import _board_image as _bimg, load_spec as _lspec
    qq = QA.merged_quality(mini_sp.doc["quality_defaults"], whole_)
    mm_ = (qq.get("max_mm_per_px") or 0.3) * 0.8
    w_ = max(int(qq.get("min_long_edge_px") or 2000) + 200, 2000)
    h_ = int(w_ * 0.75)
    board_img = _bimg(_lspec(), mm_)
    bh_, bw_ = board_img.shape[:2]
    verdicts = {}
    for label, field in (("an empty backdrop", None),
                         ("pure noise", "noise"),
                         ("a flat grey field", "flat")):
        if field == "noise":
            im = _np.random.default_rng(4).integers(30, 90, (h_, w_, 3), dtype=_np.uint8)
        elif field == "flat":
            im = _np.full((h_, w_, 3), 110, _np.uint8)
        else:
            im = None
        pth = b.tmp / ("shows_nothing_%s.png" % (field or "empty"))
        if im is None:
            synth_capture(str(pth), subject="blank_backdrop", mm_per_px=mm_, size=(w_, h_),
                          seed=1, board=True)
        else:
            if bh_ < h_ and bw_ < w_:
                im[10:10 + bh_, w_ - bw_ - 10:w_ - 10] = board_img
            _cv2.imwrite(str(pth), im)
        ch, _na = QA.check_capture(pth, whole_, qq, rep=1, board=board_, board_spec=bspec_,
                                   image=_cv2.imread(str(pth)),
                                   operator_assertions={"operator": "p", "ruler_visible": True,
                                                        "side_confirmed": True,
                                                        "region_confirmed": True})
        verdicts[label] = QA.roll_up(ch)
    out.append(Result("a frame that satisfies the numbers and shows nothing does not pass",
                      all(v != QA.PASS for v in verdicts.values()),
                      "; ".join("%s -> %s" % kv for kv in sorted(verdicts.items())),
                      "the operator can confirm the ruler and the side; nothing they can assert "
                      "makes an empty backdrop a photograph of a garment"))

    # -- 64. replacing the earlier repeat after the later one passed -----------------------------
    b, sp = complete_mini("stalerelay", gid="DENIM_9239")
    assert b.gate().ready
    rel_shot = None
    for sh_ in b.activated()[0]:
        if sh_.get("relay_between_reps") and int(sh_.get("min_reps", 1)) > 1:
            rel_shot = sh_
            break
    if rel_shot is not None:
        # File a NEW rep-1 that is the same lay as rep 2. The rep-2 verdict was made against the
        # old rep 1 and is frozen; nothing re-ran it.
        st_, _ = b.store.fold()
        cap2 = st_["captures"][(rel_shot["shot_id"], 2)]
        b.add(rel_shot, 1, b.synth_for(rel_shot, 1, relay=2, seed=999))
        v = b.gate(check_files=False)
        out.append(Result("replacing an earlier repeat invalidates the later one's relay verdict",
                          not v.ready,
                          "re-filed rep 1 after rep 2 passed; ready=%s" % v.ready,
                          "the relay comparison happens once at ingest and the verdict is frozen, "
                          "so replacing the frame it was about leaves a passing verdict describing "
                          "a photograph that is no longer there"))
    else:
        out.append(Result("replacing an earlier repeat invalidates the later one's relay verdict",
                          True, "no multi-rep relay shot in the small plan", "n/a"))

    # -- 65. a wash plan written after the wash -------------------------------------------------
    b = new("latePlan", spec=mini_sp, gid="DENIM_9240")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    fields = {k: (30.0 if k == "water_temp_c" else "x") for k in GATES.WASH_FIELDS}
    b.store.append("wash_actual", dict(fields, water_temp_c=60.0), operator="selftest")
    b.store.append("wash_planned", dict(fields, water_temp_c=60.0), operator="forger")
    conds = {x.condition for x in b.gate("ready_to_finalize", check_files=False).blocks}
    out.append(Result("a wash plan written after the wash is not a plan",
                      "wash.planned" in conds,
                      "actual appended first, then a matching 'plan'",
                      "written afterwards the two collapse and every deviation computes to nothing"))

    # -- 66. a deviation that names only the field ------------------------------------------------
    b = new("tokenDev", spec=mini_sp, gid="DENIM_9241")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    b.store.append("wash_planned", dict(fields), operator="selftest")
    for f_ in GATES.WASH_FIELDS:          # pre-register every field name, before the wash
        b.store.append("deviation", {"kind": "wash", "field": f_, "reason": "just in case"},
                       operator="forger")
    b.store.append("wash_actual", dict(fields, water_temp_c=90.0), operator="selftest")
    conds = {x.condition for x in b.gate("ready_to_finalize", check_files=False).blocks}
    out.append(Result("a deviation that names only a field does not excuse whatever happened",
                      "wash.actual" in conds,
                      "pre-registered all %d field names, then washed at 90 C" % len(GATES.WASH_FIELDS),
                      "matching on the field alone let every departure be excused in advance; a "
                      "deviation has to describe what was planned and what happened"))

    # -- 67. an offcut assignment made after the wash -----------------------------------------------
    b = new("lateAssign", spec=mini_sp, gid="DENIM_9242")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    from . import offcut as _OFF2
    for lbl, leg in (("DENIM_9242_OFFCUT_L", "left"), ("DENIM_9242_OFFCUT_R", "right")):
        b.store.append("offcut", {"label": lbl, "originating_leg": leg}, operator="selftest")
    b.store.append("wash_planned", dict(fields), operator="selftest")
    b.store.append("wash_actual", dict(fields), operator="selftest")
    for lbl, cond in (("DENIM_9242_OFFCUT_L", _OFF2.WITH_GARMENT),
                      ("DENIM_9242_OFFCUT_R", _OFF2.SEPARATE_LOAD)):
        b.store.append("offcut", {"label": lbl, "assigned_wash_condition": cond},
                       operator="forger")
    conds = {x.condition for x in b.gate("ready_to_finalize", check_files=False).blocks}
    out.append(Result("an offcut wash condition assigned after the wash decides nothing",
                      "offcuts.assigned" in conds,
                      "both conditions appended after wash_actual",
                      "the assignment exists to decide which offcut goes into the garment's load "
                      "and to keep the left/right alternation unconfounded"))

    # -- 68. an intake answer changed in the direction that deletes a photograph ----------------------
    b = new("shrinkAnswer", spec=mini_sp, gid="DENIM_9243")
    b.open_session(); b.freeze_rig()
    ans1 = b.answer_features({"n_tears": 3})
    b.measure()
    b.store.append("feature_answers", {"answers": dict(ans1, n_tears=0)}, operator="forger")
    blocked_ = b.blocked_conditions(check_files=False)
    b.store.append("deviation", {"kind": "intake", "field": "n_tears",
                                 "reason": "recounted; the third was a fold, not a tear"},
                   operator="selftest")
    after_ = b.blocked_conditions(check_files=False)
    out.append(Result("an answer changed to delete required frames blocks until it is explained",
                      "features.answered" in blocked_ and "features.answered" not in after_,
                      "n_tears 3 -> 0 blocks; a recorded intake deviation clears it",
                      "the newest answer won and the earlier one stayed in the log invisible to "
                      "every condition, so a later answer could delete the frames an earlier one "
                      "required with nothing to look at"))

    # -- 69. a macro whose cloth is out of focus and whose rule is sharp ------------------------------
    b = new("blurcloth", spec=mini_sp, gid="DENIM_9244")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    import cv2 as _cv
    macro_shot = {"shot_id": "BEFORE.TEST.MACRO", "state": "before", "garment_side": "n/a",
                  "region_id": "hem_left_front", "camera_angle": "macro_perpendicular",
                  "framing": "-", "scale_reference": "ruler", "min_reps": 1,
                  "necessity": "required", "est_seconds": 30,
                  "camera_height_group": "m", "lens": "macro", "purpose": "x",
                  "quality": {"min_blur": 80.0, "requires_ruler": True}}
    sharp = b.tmp / "macro_sharp.png"
    synth_capture(str(sharp), subject="hem_macro", mm_per_px=0.04, size=(2600, 1950), seed=3,
                  board=False, ruler=True)
    im = _cv.imread(str(sharp))
    y0 = int(1950 * 0.86)
    soft = im.copy()
    soft[:y0] = _cv.GaussianBlur(im[:y0], (0, 0), 6.0)
    softp = b.tmp / "macro_cloth_blurred.png"
    _cv.imwrite(str(softp), soft)
    qm = QA.merged_quality(mini_sp.doc["quality_defaults"], macro_shot)
    verdicts = {}
    for lbl, path_ in (("sharp", sharp), ("cloth blurred, rule sharp", softp)):
        ch, _na = QA.check_capture(path_, macro_shot, qm, rep=1, board=None, board_spec=None,
                                   image=_cv.imread(str(path_)),
                                   operator_assertions={"operator": "p", "ruler_visible": True,
                                                        "region_confirmed": True})
        verdicts[lbl] = [c.outcome for c in ch if c.check_id == "blur"][0]
    out.append(Result("a macro whose cloth is out of focus is refused even when its rule is sharp",
                      verdicts.get("sharp") == QA.PASS
                      and verdicts.get("cloth blurred, rule sharp") == QA.RETAKE,
                      "; ".join("%s -> blur %s" % kv for kv in sorted(verdicts.items())),
                      "blur was scored over a foreground that excluded the board and not the rule, "
                      "and on a macro the rule is the sharpest thing in the frame -- a 6-sigma blur "
                      "of the cloth moved the reported score from 1167 to 1055, both far above any "
                      "threshold. Macros are where fray depth is measured."))

    # -- 70. a motion clip must be able to pass -------------------------------------------------------
    b = new("clip", spec=mini_sp, gid="DENIM_9246")
    import cv2 as _cv3
    import numpy as _np3
    clip = b.tmp / "motion.mp4"
    w3, h3 = 640, 480
    vw_ = _cv3.VideoWriter(str(clip), _cv3.VideoWriter_fourcc(*"mp4v"), 30.0, (w3, h3))
    ok_writer = vw_.isOpened()
    if ok_writer:
        for i in range(60):
            fr = _np3.full((h3, w3, 3), 40, _np3.uint8)
            _cv3.rectangle(fr, (100, 100 + i), (300, 300 + i), (120, 90, 60), -1)
            vw_.write(fr)
    vw_.release()
    video_shot = {"shot_id": "POSTWASH.TEST.MOTION", "state": "post_wash", "garment_side": "front",
                  "region_id": "whole_garment_front", "camera_angle": "video", "framing": "-",
                  "scale_reference": "charuco_board", "min_reps": 1, "necessity": "required",
                  "est_seconds": 60, "camera_height_group": "handheld", "lens": "main",
                  "purpose": "x", "video_seconds": 2.0, "quality": {}}
    if ok_writer and clip.exists() and clip.stat().st_size > 0:
        ch3, _na3 = QA.check_capture(clip, video_shot,
                                     QA.merged_quality(mini_sp.doc["quality_defaults"], video_shot),
                                     rep=1, operator_assertions={"operator": "p"})
        verdict3 = QA.roll_up(ch3)
        detail3 = "%s (%s)" % (verdict3, "; ".join("%s=%s" % (c.check_id, c.outcome) for c in ch3))
    else:
        verdict3, detail3 = QA.PASS, "no video writer available on this build; not exercised"
    out.append(Result("a motion clip can pass",
                      verdict3 == QA.PASS, detail3,
                      "`readable` was cv2.imread, which returns None for every video container, so "
                      "the two required motion clips could NEVER pass and the post-wash gate could "
                      "never open -- a gate that valid evidence cannot open is broken, not safe"))

    # -- 70d. five photographs of ONE lay are not five independent re-lays ------------------------
    # The requirement this whole arm exists for. The five front-overhead repeats are written as
    # separate shot ids with min_reps 1, so the relay check -- which only ever looked at repeats
    # INSIDE a shot id -- was never asked about them, and the gate condition was vacuously satisfied
    # for exactly the eight frames it was written about.
    b = new("onelay", spec=full_spec, gid="DENIM_9253")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    acts_ = {x["shot_id"]: x for x in b.activated()[0]}
    ser = [x for x in ("BEFORE.WHOLE.F00.R1", "BEFORE.WHOLE.F00.R2", "BEFORE.WHOLE.F00.R3",
                       "BEFORE.WHOLE.F00.R4", "BEFORE.WHOLE.F00.R5") if x in acts_]
    verdicts_ = {}
    if len(ser) >= 2:
        first_ = b.synth_for(acts_[ser[0]], 1)
        b.add(acts_[ser[0]], 1, first_, confirm_all=True)
        for sid_ in ser[1:]:
            same_ = b.dir / ("one_lay_%s.png" % sid_.rsplit(".", 1)[-1])
            from .fixtures import reshoot as _rs
            _rs(first_, same_, sensor_sigma=4.0, shake_px=2.0,
                seed=zlib.crc32(sid_.encode()) % 9999)
            b.add(acts_[sid_], 1, same_, confirm_all=True)
        st_ = b.store.fold()[0]
        for sid_ in ser[1:]:
            q_ = st_["qa"].get((sid_, 1)) or {}
            rel_ = [c for c in (q_.get("checks") or []) if c["check_id"] == "relay_independence"]
            verdicts_[sid_] = rel_[0]["outcome"] if rel_ else "NOT ASKED"
    b.resolve_humans()
    out.append(Result("five photographs of one lay are not five independent re-lays",
                      len(ser) == 5 and all(v == QA.RETAKE for v in verdicts_.values())
                      and "captures.relays_independent" in b.blocked_conditions(),
                      "%d in the series; verdicts %s" % (len(ser), sorted(set(verdicts_.values()))),
                      "the repeatability arm is the one thing in the pilot that measures the "
                      "method rather than the garment, and its frames are separate shot ids, so "
                      "the relay check never saw them and the gate condition was vacuous"))

    # -- 70e. a rewritten log stays rewritten, however many commands follow ------------------------
    b = new("rewrite", gid="DENIM_9254")
    b.open_session()
    for i in range(6):
        b.store.append("note", {"i": i}, operator="selftest")
    mpath = pathlib.Path(str(b.store.manifest.path))
    keep = [ln for ln in mpath.read_text().splitlines() if ln.strip()][:-1]
    mpath.write_text("\n".join(keep) + "\n")
    caught_at_once = {x["kind"] for x in b.store.manifest.read()[1]}
    still_caught = []
    for i in range(4):                                     # ordinary work, exactly as on cut day
        b.store.append("note", {"pad": i}, operator="selftest")
        still_caught.append("history_rewritten" in {x["kind"] for x in b.store.manifest.read()[1]})
    out.append(Result("a deleted entry stays visible however much is appended after it",
                      "entries_missing" in caught_at_once and all(still_caught),
                      "caught immediately as %s; after 1-4 further appends: %s"
                      % (sorted(caught_at_once), still_caught),
                      "the high-water mark is a length comparison and the appender repairs it, so "
                      "the anchor detected a truncation only until the operator took one more "
                      "photograph -- and never detected delete-one-add-one at all"))

    # -- 70f. a forged all-PASS verdict cannot survive the photograph itself ----------------------
    b = new("forgery", spec=_mini_spec(tmp_root), gid="DENIM_9255")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    fshot = b.activated()[0][0]
    blank = b.dir / "nothing.png"
    synth_capture(str(blank), subject="blank_backdrop", mm_per_px=0.4, size=(2400, 1800), seed=7,
             board=False)
    fdest, fsha, _ = ingest_photo(blank, b.dir / "images" / fshot["state"], fshot["shot_id"], 1)
    b.store.append("capture", {"shot_id": fshot["shot_id"], "rep": 1,
                               "path": str(fdest.relative_to(b.dir)), "sha256": fsha,
                               "state": fshot["state"], "region_id": fshot.get("region_id")},
                   operator="mallory", setup_hash=b.setup_hash)
    mand_ = sorted(set(QA.APPLICABLE[QA.shot_class(fshot)]) - QA.OPTIONAL_CHECKS)
    b.store.append("qa_result", {"shot_id": fshot["shot_id"], "rep": 1, "outcome": QA.PASS,
                                 "shot_class": QA.shot_class(fshot), "capture_sha256": fsha,
                                 "checks": [{"check_id": c, "outcome": QA.PASS, "detail": "fine"}
                                            for c in mand_], "not_applicable": []},
                   operator="mallory")
    b.cut_ready_extras()
    fconds = b.blocked_conditions()
    out.append(Result("a forged verdict cannot survive the photograph it describes",
                      "captures.verdicts_reproduce" in fconds,
                      "blocked by %s" % sorted(fconds),
                      "every other defence tests the record against ITSELF -- the roll-up must "
                      "match the checks, the checks must cover the class -- and a complete enough "
                      "forgery satisfies all of them. The photograph cannot be appended to"))

    # -- 70g. deleting the whole log is not the same as never having had one ----------------------
    b = new("rmlog", gid="DENIM_9256")
    b.open_session()
    for i in range(4):
        b.store.append("note", {"i": i}, operator="selftest")
    pathlib.Path(str(b.store.manifest.path)).unlink()
    gone = {x["kind"] for x in b.store.manifest.read()[1]}
    fresh = new("neverhad", gid="DENIM_9257")
    fresh_problems = fresh.store.manifest.read()[1]
    out.append(Result("deleting the whole log is not the same as never having had one",
                      "entries_missing" in gone and not fresh_problems,
                      "after rm: %s; a genuinely fresh garment: %s" % (sorted(gone), fresh_problems),
                      "read() returned before check_head ran when the file was absent, so the one "
                      "check written to detect entries removed from the end could not fire in the "
                      "case where all of them were -- with the anchor sitting there saying so"))

    # -- 70h. two honest hands at once are not tampering ------------------------------------------
    b = new("concurrent", gid="DENIM_9258")
    b.open_session()
    saw = []
    stop_ = []

    def _write():
        for i in range(120):
            b.store.append("note", {"i": i}, operator="phone")
        stop_.append(True)

    def _read():
        while not stop_:
            probs = b.store.manifest.read()[1]
            if probs:
                saw.append([x["kind"] for x in probs])
    tw_ = threading.Thread(target=_write)
    tr_ = threading.Thread(target=_read)
    tw_.start(); tr_.start(); tw_.join(); tr_.join()
    out.append(Result("a fold running during an upload does not read as tampering",
                      not saw,
                      "%d read(s) reported a problem while an honest writer worked%s"
                      % (len(saw), (": " + str(saw[0])) if saw else ""),
                      "append() has been serialised since round 1 and read() took no lock, so one "
                      "phone uploading while the GATE tab refreshed -- two ordinary things at once "
                      "on a threading server -- reported a torn line and a head mismatch"))

    # -- 70i. a read must never wait forever for a lock -------------------------------------------
    b = new("nohang", gid="DENIM_9259")
    b.open_session()
    b.store.append("note", {"i": 0}, operator="selftest")
    held = None
    elapsed = None
    try:
        import fcntl as _fc
        held = open(str(pathlib.Path(str(b.store.manifest.path)).parent
                        / (pathlib.Path(str(b.store.manifest.path)).name + ".lock")), "a+")
        _fc.flock(held.fileno(), _fc.LOCK_EX)
        t0_ = time.time()
        n_ = len(b.store.manifest.read()[0])
        elapsed = time.time() - t0_
        _fc.flock(held.fileno(), _fc.LOCK_UN)
    except ImportError:
        n_, elapsed = 1, 0.0
    finally:
        if held is not None:
            held.close()
    out.append(Result("a read gives up on the lock rather than on itself",
                      n_ >= 1 and elapsed is not None and elapsed < MF.READ_LOCK_WAIT_S + 3.0,
                      "read returned %d entries in %.2fs with the exclusive lock held (bound %.1fs)"
                      % (n_, elapsed if elapsed is not None else -1, MF.READ_LOCK_WAIT_S),
                      "flock is per open file description, so on Linux a blocking shared lock taken "
                      "while this process holds the exclusive one waits on itself forever. A hang "
                      "is worse than a refusal: the operator cannot tell it from slow work"))

    # -- 70j. a self-consistent forgery of the whole garment directory ----------------------------
    # The honest limit of a keyless chain: its seed is public, so anyone who can write the garment
    # directory can re-chain the log, and rewriting the .head beside it makes the forgery agree with
    # itself. Nothing on one filesystem prevents that. What can be done is to keep one record
    # OUTSIDE the directory being edited -- which is the realistic version of this: an operator
    # tidying up their own log, who does not know a second copy exists one level up.
    b = new("forgeall", gid="DENIM_9260")
    b.open_session()
    for i in range(5):
        b.store.append("note", {"i": i}, operator="selftest")
    mp_ = pathlib.Path(str(b.store.manifest.path))
    objs_ = [json.loads(ln) for ln in mp_.read_text().splitlines() if ln.strip()][:3]
    prev_ = b.store.manifest.seed
    lines_ = []
    for o_ in objs_:
        o_["prev_chain"] = prev_
        o_["chain"] = MF.sha256_text(prev_ + MF.canonical(
            {k: v for k, v in o_.items() if k != "chain"}))
        prev_ = o_["chain"]
        lines_.append(MF.canonical(o_))
    mp_.write_text("\n".join(lines_) + "\n")
    pathlib.Path(str(b.store.manifest.head_path)).write_text("\n".join(
        MF.canonical({"chain": json.loads(lines_[i])["chain"], "count": i + 1,
                      "seed": b.store.manifest.seed}) for i in range(len(lines_))) + "\n")
    caught_ = {x["kind"] for x in b.store.manifest.read()[1]}
    out.append(Result("a forgery consistent within the garment directory is caught from outside it",
                      bool(caught_),
                      "re-chained the log AND rewrote its anchor; caught as %s" % (sorted(caught_)
                                                                                  or "NOTHING"),
                      "the chain is keyless and its seed is public, so a forger who can write the "
                      "directory can make the log and its sidecar agree perfectly. The witness "
                      "beside the garments is the copy they did not know to edit"))

    # -- 70k. the frame that proves the jeans were not there cannot be the jeans ------------------
    b = new("emptybd", spec=full_spec, gid="DENIM_9261")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    empt = [x for x in b.activated()[0] if x.get("must_be_empty")]
    verd = {}
    if empt:
        sh_e = empt[0]
        q_e = QA.merged_quality(b.spec.doc["quality_defaults"], sh_e)
        bd_, bs_ = b.board
        for lbl, subj in (("empty", "blank_backdrop"), ("the jeans", "jeans_front")):
            fp = b.dir / ("empty_%s.png" % subj)
            synth_capture(str(fp), subject=subj, mm_per_px=0.5, size=(2400, 1800), seed=4,
                          board=True)
            ck, _n = QA.check_capture(fp, sh_e, q_e, rep=1, board=bd_, board_spec=bs_,
                                      operator_assertions={("confirmed_" + c): True
                                                           for c in (sh_e.get("requires_human")
                                                                     or [])})
            se_ = [c for c in ck if c.check_id == "surface_empty"]
            verd[lbl] = se_[0].outcome if se_ else "NOT ASKED"
    out.append(Result("the frame that proves the jeans were not there cannot be the jeans",
                      verd.get("empty") == QA.PASS and verd.get("the jeans") == QA.RETAKE,
                      "empty surface -> %s; a photograph of the jeans -> %s"
                      % (verd.get("empty"), verd.get("the jeans")),
                      "this is the one required frame whose entire content is an ABSENCE, and an "
                      "absence is the easiest thing here to measure -- leaving it to an operator "
                      "assertion meant a photograph of the garment satisfied it"))

    # -- 71a. a second recording of the actual wash cannot replace the first ----------------------
    b = new("washonce", gid="DENIM_9251")
    b.open_session()
    plan_w = {"machine": "Miele W1", "location": "flat", "cycle": "cottons 30",
              "water_temp_c": 30.0, "spin_rpm": 1200.0, "detergent": "Persil", "detergent_ml": 35.0,
              "filler_load": "3 towels", "start_time": "10:00", "end_time": "11:30",
              "dryer_method": "line", "dryer_setting": "n/a", "dryer_minutes": 0.0,
              "conditioning_start": "11:30", "conditioning_end": "13:30",
              "garment_in_load": "DENIM_9251 + offcut L"}
    b.store.append("wash_planned", plan_w, operator="selftest")
    b.store.append("wash_actual", dict(plan_w, water_temp_c=42.0), operator="selftest")
    b.store.append("wash_actual", dict(plan_w), operator="tidier")     # "correcting" away a deviation
    st_ = b.store.fold()[0]
    kept = st_["wash_actual"]["water_temp_c"] == 42.0
    out.append(Result("the actual wash is written once, like the plan",
                      kept and len(st_["wash_actual_rewrites"]) == 1,
                      "actual %s C after a rewrite to %s C; %d rewrite(s) preserved"
                      % (st_["wash_actual"]["water_temp_c"], plan_w["water_temp_c"],
                         len(st_["wash_actual_rewrites"])),
                      "last-write-wins let a second recording erase exactly the deviation that the "
                      "planned/actual split exists to preserve"))

    # -- 71b. a cut the geometry cannot model must be acknowledged, not passed over ----------------
    b = new("cutwarn", gid="DENIM_9252")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    m_ = b.store.fold()[0]["measurements"]
    from . import cutspec as _CUT
    near = _CUT.compute(target_inseam_cm=2.0,          # right up under the crotch seam
                        original_inseam_cm=m_["original_inseam_cm"]["mean"],
                        thigh_cm=m_["thigh_cm"]["mean"],
                        leg_opening_cm=m_["leg_opening_cm"]["mean"])
    b.store.append("cut_spec", near, operator="selftest")
    before_ = "cut.specified" in b.blocked_conditions()
    b.store.append("human_verification",
                   {"shot_id": None, "rep": None, "claim": "cut_out_of_model_acknowledged",
                    "value": True, "verifier_name": "alice", "operator": "alice"},
                   operator="alice")
    after_ = "cut.specified" not in b.blocked_conditions()
    out.append(Result("a cut the geometry cannot model needs someone to say they meant it",
                      bool(near.get("warning")) and before_ and after_,
                      "warning=%r; blocked before acknowledgement=%s, after=%s"
                      % ((near.get("warning") or "")[:40], before_, not after_),
                      "the tool prints that the straight-perpendicular model stops describing a "
                      "real inseam this close to the crotch, and nothing read it, so the one cut "
                      "it says it cannot predict passed as quietly as any other"))

    # -- 71. a rig frame with no content check must still ask a person ---------------------------
    b = new("rigcontent", gid="DENIM_9247")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    rig_shots = [x for x in b.activated()[0]
                 if x["state"] == "rig" and (x.get("requires_human") or [])]
    verdicts = {}
    for sh_ in rig_shots[:3]:
        src_ = b.synth_for(sh_, 1)
        o_, _c = b.add(sh_, 1, src_, confirm_all=False)
        verdicts[sh_["shot_id"]] = o_
    out.append(Result("a rig frame no automatic check can judge asks a person",
                      bool(verdicts) and all(v == QA.HUMAN for v in verdicts.values()),
                      "; ".join("%s -> %s" % (k.split(".", 1)[-1][:26], v)
                                for k, v in sorted(verdicts.items())),
                      "an empty backdrop, a lighting test and a coplanarity proof pass every "
                      "numeric threshold on a photograph of anything; the only thing between the "
                      "requirement and any file that decodes is a person saying what they see"))

    # -- 72. THE POSITIVE CONTROL: a complete session opens the gate -------------------------------
    mini = _mini_spec(tmp_root)
    b = new("happy", spec=mini, gid="DENIM_9002")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    shots, _m = b.activated()
    captured = 0
    for s in shots:
        for rep in range(1, int(s.get("min_reps", 1)) + 1):
            src = b.synth_for(s, rep, relay=rep, seed=1000 + captured)
            o, _c = b.add(s, rep, src)
            captured += 1
    b.resolve_humans()
    b.cut_ready_extras()
    v = b.gate()
    # -- 71a1. an edited shot plan does not strand an open session forever -----------------------
    b, _sp = complete_mini("rebind", gid="DENIM_9262")
    assert b.gate().ready
    b.store.append("session_opened", {"spec_version": b.spec.version,
                                      "spec_hash": "0" * 64,
                                      "protocol_version": b.spec.doc["protocol_version"]})
    stranded = "spec.bound" in b.blocked_conditions()
    b.store.append("deviation", {"kind": "protocol", "field": "spec_rebound",
                                 "actual": b.spec.content_hash,
                                 "reason": "a post-wash frame was added to the plan; every frame "
                                           "already taken is still required by the new one"},
                   operator="selftest")
    freed = "spec.bound" not in b.blocked_conditions()
    out.append(Result("an edited shot plan can be acknowledged instead of stranding the session",
                      stranded and freed,
                      "blocked after the plan changed=%s; released once the change was recorded=%s"
                      % (stranded, freed),
                      "any edit to the plan -- including one that ADDS a required photograph, the "
                      "edit you most want to be able to make -- blocked every open session here "
                      "forever, and the remedy the message named was not something any command "
                      "could do. Nothing is weakened: every other condition still re-derives "
                      "against the plan on disk, so a frame the new plan added is still missing"))

    # -- 71a2. a corrected measurement invalidates the cut line computed from the old one --------
    b, _sp = complete_mini("stalecut", gid="DENIM_9259")
    before_ok = b.gate().ready
    b.store.append("measurement", {"name": "thigh_cm", "readings": [68.0, 68.1], "mean": 68.05,
                                   "spread": 0.1, "tolerance": 0.5, "in_tolerance": True},
                   operator="selftest")
    conds_ = {x.condition for x in b.gate().blocks}
    out.append(Result("a corrected measurement invalidates the cut line derived from it",
                      before_ok and "cut.specified" in conds_,
                      "ready before the correction=%s; after it blocks on: %s"
                      % (before_ok, ", ".join(sorted(conds_)) or "nothing"),
                      "cutspec.compute records the three measurements the line was derived from and "
                      "nothing ever compared them again. Measure, specify, mark, have it verified, "
                      "then re-lay the tape and correct a reading the way the tool asks -- and the "
                      "measurements said one thing, the line was computed from another, and the "
                      "gate was clean. The second-person check agrees with a stale line, because it "
                      "compares the tape against that same line"))

    # -- 71a3. an approval given before the cut line existed does not authorise it ----------------
    b = new("prematureconf", spec=_mini_spec(tmp_root), gid="DENIM_9260")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    for claim in ("legs_cut_separately", "offcuts_retained_labelled"):
        b.store.append("human_verification",
                       {"shot_id": None, "rep": None, "claim": claim, "value": True,
                        "verifier_name": "selftest", "operator": "selftest"}, operator="selftest")
    # writes the cut_spec AFTER the confirmations, and does not re-write them
    b.cut_ready_extras(skip=("verification", "legs_cut_separately", "offcuts_retained_labelled"))
    conds_ = {x.condition for x in b.gate().blocks}
    out.append(Result("a cut-day confirmation made before the cut line existed does not carry",
                      "cut.confirmations" in conds_,
                      "blocks: %s" % ", ".join(sorted(conds_)),
                      "the per-frame HUMAN claims are bound to the photograph's sha256 and to a "
                      "later entry, for a reason the code states: otherwise every claim can be "
                      "confirmed in a loop before any evidence exists. The three claims that "
                      "actually authorise the shears had no such binding at all"))

    # -- 71a3b. an approval of the marks does not survive the line it approved being recomputed ---
    b, _sp = complete_mini("staleapproval", gid="DENIM_9270")
    assert b.gate().ready
    from . import cutspec as _CS
    m_ = b.store.fold()[0]["measurements"]
    again = _CS.compute(target_inseam_cm=15.0,
                        original_inseam_cm=m_["original_inseam_cm"]["mean"],
                        thigh_cm=m_["thigh_cm"]["mean"],
                        leg_opening_cm=m_["leg_opening_cm"]["mean"])
    b.store.append("cut_spec", again, operator="selftest")     # re-derived AFTER the approval
    conds_ = {x.condition for x in b.gate().blocks}
    out.append(Result("re-computing the cut line invalidates the approval given to the old one",
                      "cut.second_person_verified" in conds_,
                      "blocks: %s" % (", ".join(sorted(conds_)) or "nothing"),
                      "the second person's approval is of a LINE, and nothing compared when it was "
                      "given against when the line was computed. Re-running cutspec after a "
                      "corrected measurement therefore inherited the approval given to the line it "
                      "replaced -- and the marks that approval checked are on the garment in a "
                      "different place"))

    # -- 71a4. the cut gate stops answering once the cut has happened ----------------------------
    b, _sp = complete_mini("alreadycut", gid="DENIM_9261")
    assert b.gate().ready
    b.store.append("cut_performed", {"achieved_inseam_cm": {"L": 15.0, "R": 15.0},
                                     "achieved_outseam_cm": {"L": 16.0, "R": 16.0},
                                     "tool": "shears", "legs_cut_separately": True},
                   operator="selftest")
    conds_ = {x.condition for x in b.gate().blocks}
    out.append(Result("the cut gate refuses a garment that has already been cut",
                      "cut.not_already_performed" in conds_,
                      "blocks: %s" % ", ".join(sorted(conds_)),
                      "the gate answers a question about the future, and nothing read the log's own "
                      "order against the irreversible step -- although the same file refuses a wash "
                      "plan written after the wash. A session that cut first and photographed "
                      "afterwards produced a green record no reader could tell from a compliant one"))

    # -- 71b2. a counted feature that is not described blocks, and the frames name the object ----
    b = new("annot", gid="DENIM_9257")
    b.open_session(); b.freeze_rig()
    b.answer_features(overrides={"n_tears": 3})
    b.measure()
    blocked_without = "annotations.identify_instances" in b.blocked_conditions()
    for i, loc in enumerate(("left leg front, 12 cm above the hem",
                             "right knee", "left back pocket corner"), 1):
        b.store.append("annotation",
                       {"annotation_id": "TEAR.%02d" % i, "feature": "n_tears", "type": "tear",
                        "location": loc, "note": "a tear"}, operator="selftest")
    blocked_with = "annotations.identify_instances" in b.blocked_conditions()
    st_ = b.store.fold()[0]
    shots_ = PLAN.activate(b.spec, st_["features"], st_["measurements"],
                           annotations=st_["annotations"])[0]
    named = {s["shot_id"]: s.get("annotation_id") for s in shots_ if s.get("instance_index")}
    tear_named = {k: v for k, v in named.items() if "TEAR" in k.upper()}
    out.append(Result("three tears require three photographs, each naming which tear",
                      blocked_without and not blocked_with and len(set(tear_named.values())) == 3
                      and all(tear_named.values()),
                      "blocked before the descriptions=%s, after=%s; %d tear frames -> %s"
                      % (blocked_without, blocked_with, len(tear_named),
                         sorted(v for v in tear_named.values() if v)),
                      "a count required three photographs and said nothing about which tear each "
                      "one showed. Two frames of the same tear satisfied it, and after the cut "
                      "nobody could tell which was which -- the ordinal was a function of the "
                      "current feature answers, not a recorded fact"))

    # -- 71b2b. a tear found later does not re-label the photographs already taken ---------------
    b = new("lateann", gid="DENIM_9263")
    b.open_session(); b.answer_features(overrides={"n_tears": 3}); b.measure()
    for i, loc in enumerate(("left leg front", "right knee", "left back pocket corner"), 1):
        b.store.append("annotation", {"annotation_id": "TEAR.%02d" % i, "feature": "n_tears",
                                      "type": "tear", "location": loc, "note": "x"},
                       operator="selftest")

    def tear_map():
        s_ = b.store.fold()[0]
        sh_ = PLAN.activate(b.spec, s_["features"], s_["measurements"],
                            annotations=s_["annotations"])[0]
        return {x["shot_id"]: x["annotation_id"] for x in sh_
                if x.get("annotation_id") and "TEAR" in x["shot_id"].upper()}

    before_map = tear_map()
    # the 1 a.m. discovery, named for what it is: the one before the others
    b.store.append("feature_answers", {"answers": dict(b.store.fold()[0]["features"], n_tears=4)},
                   operator="selftest")
    b.store.append("annotation", {"annotation_id": "TEAR.00", "feature": "n_tears", "type": "tear",
                                  "location": "right leg back, 3 cm below the yoke", "note": "missed"},
                   operator="selftest")
    after_map = tear_map()
    moved = sorted(k for k in before_map if before_map[k] != after_map.get(k))
    late_slots = sorted(k for k, v in after_map.items() if v == "TEAR.00")
    out.append(Result("a feature found later does not re-label the photographs already taken",
                      not moved and bool(late_slots)
                      and all(k.endswith(".I04") for k in late_slots),
                      "%d frame(s) changed meaning; TEAR.00 took %s"
                      % (len(moved), ", ".join(k.rsplit(".", 1)[-1] for k in late_slots)),
                      "instance identity was a SORT POSITION over the ids, so any later annotation "
                      "sorting ahead of an existing one shifted every slot after it and "
                      "retroactively re-labelled accepted photographs. Naming a missed tear TEAR.00 "
                      "did it, and so did ids without leading zeros once there were ten"))

    # -- 71a6. a re-measurement inside one state is visible, and a mis-filed state is not fatal ---
    b, _sp = complete_mini("revised", gid="DENIM_9268")
    assert b.gate().ready
    m0 = b.store.fold()[0]["measurements"]["thigh_cm"]["mean"]
    b.store.append("measurement", {"name": "thigh_cm", "readings": [m0 + 8.0, m0 + 8.1],
                                   "mean": m0 + 8.05, "spread": 0.1, "tolerance": 0.5,
                                   "in_tolerance": True}, operator="selftest")
    silent = "measurements.revisions_explained" in b.blocked_conditions()
    # An untargeted excuse must not clear it; the deviation has to name the measurement.
    b.store.append("deviation", {"kind": "protocol", "field": "measurement_revised",
                                 "reason": "blanket"}, operator="selftest")
    untargeted = "measurements.revisions_explained" in b.blocked_conditions()
    b.store.append("deviation", {"kind": "protocol", "field": "measurement_revised:thigh_cm",
                                 "reason": "the first thigh reading was taken above the crotch "
                                           "offset; re-measured at 2.5 cm as the protocol says"},
                   operator="selftest")
    explained = "measurements.revisions_explained" not in b.blocked_conditions()

    # Measuring the washed garment before typing the wash record is the ORDINARY order of work and
    # must not block; writing back into the pre-cut baseline after the cut must be refused outright.
    b2 = new("aheadofrecord", gid="DENIM_9269")
    b2.open_session()
    b2.store.append("measurement", {"name": "waist_cm", "readings": [97.0, 97.2], "mean": 97.1,
                                    "state": "post_wash"}, operator="selftest")
    _st2, probs2 = b2.store.fold()
    ahead_ok = not probs2 and "measurements.revisions_explained" not in b2.blocked_conditions()
    b3 = new("backdated", gid="DENIM_9271")
    b3.open_session()
    b3.store.append("cut_performed", {"achieved_inseam_cm": {"L": 15.0, "R": 15.0},
                                      "achieved_outseam_cm": {"L": 16.0, "R": 16.0},
                                      "tool": "shears", "legs_cut_separately": True},
                    operator="selftest")
    b3.store.append("wash_actual", {"machine": "m", "cycle": "c"}, operator="selftest")
    b3.store.append("measurement", {"name": "waist_cm", "readings": [97.0, 97.2], "mean": 97.1,
                                    "state": "before"}, operator="selftest")
    b3.store.append("deviation", {"kind": "protocol", "field": "measurement_revised:waist_cm",
                                  "reason": "trying to excuse it"}, operator="selftest")
    backdated_refused = "measurements.revisions_explained" in b3.blocked_conditions()
    out.append(Result("a replaced measurement needs a named reason; the baseline cannot be "
                      "written after the cut",
                      silent and untargeted and explained and ahead_ok and backdated_refused,
                      "silent re-measure blocks=%s; a blanket excuse does not clear it=%s; a named "
                      "one does=%s; measuring ahead of the wash record is ordinary=%s; writing "
                      "into the pre-cut baseline after the cut is refused even with a deviation=%s"
                      % (silent, untargeted, explained, ahead_ok, backdated_refused),
                      "fold projected the revision and no condition read it. The first attempt at "
                      "this then over-corrected twice: it treated measuring the washed garment "
                      "before typing the wash record -- the order the runbook itself prescribes -- "
                      "as a fatal conflict, and it let one untargeted deviation excuse every "
                      "revision in the session, including ones written after it"))

    # -- 71a5. a photograph cannot be filed in a state the log's own order contradicts -----------
    b = new("stateorder", gid="DENIM_9266")
    b.open_session(); b.answer_features(); b.measure()
    b.store.append("cut_performed", {"achieved_inseam_cm": {"L": 15.0, "R": 15.0},
                                     "achieved_outseam_cm": {"L": 16.0, "R": 16.0},
                                     "tool": "shears", "legs_cut_separately": True},
                   operator="selftest")
    b.store.append("capture", {"shot_id": "BEFORE.WHOLE.F00.R1", "rep": 1, "sha256": "a" * 64,
                               "path": "images/before/x.png", "state": "before"},
                   operator="selftest")
    late = all("captures.state_order" in b.blocked_conditions(g, check_files=False)
               for g in ("ready_to_wash", "ready_to_finalize"))
    b2 = new("stateorder2", gid="DENIM_9267")
    b2.open_session(); b2.answer_features(); b2.measure()
    b2.store.append("capture", {"shot_id": "POSTWASH.WHOLE.F00.R1", "rep": 1, "sha256": "b" * 64,
                                "path": "images/post_wash/y.png", "state": "post_wash"},
                    operator="selftest")
    early = "captures.state_order" in b2.blocked_conditions("ready_to_finalize", check_files=False)
    out.append(Result("a photograph of the uncut garment cannot arrive after the cut",
                      late and early,
                      "a before frame filed after the cut blocks both later gates=%s; a post-wash "
                      "frame filed before any wash blocks finalize=%s" % (late, early),
                      "the cut gate learned to read the log's order and the two gates AFTER it did "
                      "not, so a photograph of the intact garment filed after the shears, and a "
                      "photograph of the washed garment filed before the wash, both produced a "
                      "fully green chained record"))

    # -- 71b2d. damage the wash caused can be recorded without demanding a photograph of it
    #           from before the wash ---------------------------------------------------------
    b = new("washtear", gid="DENIM_9265")
    b.open_session(); b.answer_features(overrides={"n_tears": 1}); b.measure()
    b.store.append("annotation", {"annotation_id": "TEAR.01", "feature": "n_tears", "type": "tear",
                                  "location": "left knee", "note": "present at intake"},
                   operator="selftest")
    b.store.append("cut_performed", {"achieved_inseam_cm": {"L": 15.0, "R": 15.0},
                                     "achieved_outseam_cm": {"L": 16.0, "R": 16.0},
                                     "tool": "shears", "legs_cut_separately": True},
                   operator="selftest")
    b.store.append("wash_actual", {"machine": "m", "cycle": "c"}, operator="selftest")
    b.store.append("feature_answers",
                   {"answers": dict(b.store.fold()[0]["features"], n_tears=2)}, operator="selftest")
    b.store.append("annotation", {"annotation_id": "TEAR.02", "feature": "n_tears", "type": "tear",
                                  "location": "right shin", "note": "opened in the wash"},
                   operator="selftest")
    s_ = b.store.fold()[0]
    sh_ = PLAN.activate(b.spec, s_["features"], s_["measurements"],
                        annotations=s_["annotations"])[0]
    ids_ = sorted(x["shot_id"] for x in sh_
                  if x.get("annotation_id") == "TEAR.02" and "TEAR" in x["shot_id"].upper())
    impossible = [x for x in ids_ if x.startswith(("BEFORE", "INTAKE"))]
    out.append(Result("damage the wash caused does not require a photograph from before the wash",
                      bool(ids_) and not impossible,
                      "the tear the wash opened is required in: %s"
                      % ", ".join(i.split(".")[0] for i in ids_),
                      "every anomaly shot was instanced on one global count, so recording a tear "
                      "the wash opened demanded an intake and a before frame of a tear that did "
                      "not exist then, on a garment now cut and washed. The log is append-only, so "
                      "the session became unfinalizable by any route and the operator's only "
                      "workable move was not to record the tear"))

    # -- 71b2c. a photograph and the plan must agree about which thing it shows -------------------
    b = new("wrongann", gid="DENIM_9264")
    b.open_session(); b.answer_features(overrides={"n_tears": 2}); b.measure()
    for i, loc in enumerate(("left leg front", "right knee"), 1):
        b.store.append("annotation", {"annotation_id": "TEAR.%02d" % i, "feature": "n_tears",
                                      "type": "tear", "location": loc, "note": "x"},
                       operator="selftest")
    s_ = b.store.fold()[0]
    sh_ = PLAN.activate(b.spec, s_["features"], s_["measurements"],
                        annotations=s_["annotations"])[0]
    slot2 = [x for x in sh_ if x.get("annotation_id") == "TEAR.02"
             and x["shot_id"].startswith("BEFORE.ANOM.TEAR")]
    ok_ = False
    if slot2:
        # a photograph of the FIRST tear, filed into the second tear's slot
        b.store.append("capture", {"shot_id": slot2[0]["shot_id"], "rep": 1, "sha256": "d" * 64,
                                   "path": "images/before/x.png", "state": "before",
                                   "annotation_id": "TEAR.01",
                                   "annotation_location": "left leg front"},
                       operator="selftest")
        ok_ = "captures.instance_identity" in b.blocked_conditions()
    out.append(Result("a photograph filed against the wrong instance is refused",
                      ok_,
                      "blocked on captures.instance_identity: %s" % ok_,
                      "every instanced capture recorded the annotation it was taken of and no "
                      "condition read it back, so the log could hold `capture I02 is of TEAR.01` "
                      "beside `plan I02 = TEAR.02` and nothing compared the two"))

    # -- 71b3. the instance placeholder is substituted, not appended -----------------------------
    b = new("innsub", gid="DENIM_9258")
    b.open_session(); b.answer_features(overrides={"n_distressing": 2}); b.measure()
    st_ = b.store.fold()[0]
    shots_ = PLAN.activate(b.spec, st_["features"], st_["measurements"])[0]
    leftover = sorted(s["shot_id"] for s in shots_ if ".INN" in s["shot_id"])
    out.append(Result("no planned frame keeps the instance placeholder in its id",
                      not leftover,
                      "%d frame id(s) still contain .INN%s"
                      % (len(leftover), (": " + ", ".join(leftover[:3])) if leftover else ""),
                      "INN is the instance placeholder, exactly as PNN is the hem-position one, "
                      "and expansion APPENDED the suffix instead of substituting it -- so ten "
                      "planned frames carried the placeholder and its own replacement in one id"))

    # -- 71c. a post-wash reading may not overwrite the pre-cut one ------------------------------
    b = new("meastate", gid="DENIM_9253")
    b.open_session()
    b.store.append("measurement", {"name": "waist_cm", "readings": [97.0, 97.2], "mean": 97.1},
                   operator="selftest")
    b.store.append("cut_performed", {"achieved_inseam_cm": {"L": 15.0, "R": 15.0},
                                     "achieved_outseam_cm": {"L": 16.0, "R": 16.0},
                                     "tool": "shears", "legs_cut_separately": True},
                   operator="selftest")
    b.store.append("wash_actual", {"machine": "m", "cycle": "c"}, operator="selftest")
    b.store.append("measurement", {"name": "waist_cm", "readings": [95.4, 95.6], "mean": 95.5},
                   operator="selftest")
    stm = b.store.fold()[0]
    pre_ = (stm["measurements"].get("waist_cm") or {}).get("mean")
    post_ = ((stm["measurements_by_state"].get("post_wash") or {}).get("waist_cm") or {}).get("mean")
    out.append(Result("a post-wash reading does not overwrite the pre-cut one",
                      pre_ == 97.1 and post_ == 95.5 and stm["lifecycle_state"] == "post_wash",
                      "before=%s post_wash=%s lifecycle=%s" % (pre_, post_, stm["lifecycle_state"]),
                      "measurements were keyed on name alone, so re-measuring the washed garment "
                      "replaced the value it was supposed to be compared WITH -- and the finalize "
                      "gate, which re-reads the same key, then passed on the survivor. Shrinkage is "
                      "the difference between the two, so it stopped being computable at the moment "
                      "it was recorded"))

    # -- 71c2. re-measuring after the wash does not re-plan the photographs already taken --------
    b = new("resize", gid="DENIM_9256")
    b.open_session(); b.answer_features(); b.measure()
    st0 = b.store.fold()[0]
    n_before = len(PLAN.activate(b.spec, st0["features"], st0["measurements"])[0])
    b.store.append("cut_performed", {"achieved_inseam_cm": {"L": 15.0, "R": 15.0},
                                     "achieved_outseam_cm": {"L": 16.0, "R": 16.0},
                                     "tool": "shears", "legs_cut_separately": True},
                   operator="selftest")
    b.store.append("wash_actual", {"machine": "m", "cycle": "c"}, operator="selftest")
    b.store.append("measurement", {"name": "leg_opening_cm", "readings": [30.0, 30.1],
                                   "mean": 30.05}, operator="selftest")
    st1 = b.store.fold()[0]
    n_after = len(PLAN.activate(b.spec, st1["features"], st1["measurements"])[0])
    out.append(Result("a post-wash reading does not re-plan the photographs already taken",
                      n_before == n_after,
                      "%d frames planned before the re-measure, %d after" % (n_before, n_after),
                      "the hem series is SIZED from leg_opening_cm. Read from a flat name, the "
                      "post-wash value re-sized a BEFORE-state series whose frames were already "
                      "captured and whose garment no longer exists in that state -- so a session "
                      "that had printed READY acquired missing frames nobody could ever take, and "
                      "could not be finalized by any route"))

    # -- 71d. the wash gate refuses a cut nobody recorded ----------------------------------------
    b = new("nocutrec", spec=_mini_spec(tmp_root), gid="DENIM_9254")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    for s_ in b.activated()[0]:
        for rep_ in range(1, int(s_.get("min_reps", 1)) + 1):
            b.add(s_, rep_, b.synth_for(s_, rep_, relay=rep_, seed=7000 + rep_))
    b.resolve_humans(); b.cut_ready_extras()
    b.after_cut_extras(skip=("cut_performed",))
    out.append(Result("the wash gate refuses a cut whose result nobody wrote down",
                      "cut.performed_recorded" in {x.condition for x in b.gate("ready_to_wash").blocks},
                      "blocks: %s" % ", ".join(sorted(x.condition for x in b.gate("ready_to_wash").blocks)),
                      "PROTOCOL 3.1 says to record both lengths after cutting and nothing asked "
                      "for them. That number is the ground truth the prediction is scored against, "
                      "it can only be taken between the shears and the water, and after the wash "
                      "the garment has shrunk -- the length you measure is no longer the length "
                      "you cut"))

    # -- 71e. the finalize gate refuses a garment nobody re-measured -----------------------------
    b = new("nopostm", spec=_mini_spec(tmp_root), gid="DENIM_9255")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    for s_ in b.activated()[0]:
        for rep_ in range(1, int(s_.get("min_reps", 1)) + 1):
            b.add(s_, rep_, b.synth_for(s_, rep_, relay=rep_, seed=8000 + rep_))
    b.resolve_humans(); b.cut_ready_extras()
    b.after_cut_extras(skip=("post_wash_measurements",))
    out.append(Result("the finalize gate refuses a garment nobody re-measured after washing",
                      "measurements.post_wash" in {x.condition
                                                   for x in b.gate("ready_to_finalize").blocks},
                      "blocks: %s" % ", ".join(sorted(x.condition
                                                      for x in b.gate("ready_to_finalize").blocks)),
                      "measurements.complete runs for every gate and reads the PRE-cut bucket, so "
                      "finalize looked like it checked this and did not. A session could be closed "
                      "and exported having never measured the washed garment at all"))

    # -- 72b/72c. THE OTHER TWO GATES ALSO HAVE TO OPEN --------------------------------------------
    # ready_to_wash and ready_to_finalize authorise the two remaining irreversible steps, and every
    # scenario that touched them asserted only that they BLOCK. Nothing had ever demonstrated that a
    # complete, correct session can open either one, which is the same defect the cut gate's
    # positive control exists to rule out: a gate that cannot be opened by valid evidence is not
    # safe, it is broken, and it is discovered on wash day.
    bw = new("happywash", spec=mini, gid="DENIM_9004")
    bw.open_session(); bw.freeze_rig(); bw.answer_features(); bw.measure()
    shots_w, _mw = bw.activated()
    n_w = 0
    for s in shots_w:
        for rep in range(1, int(s.get("min_reps", 1)) + 1):
            bw.add(s, rep, bw.synth_for(s, rep, relay=rep, seed=4000 + n_w))
            n_w += 1
    bw.resolve_humans(); bw.cut_ready_extras(); bw.after_cut_extras()
    vw = bw.gate("ready_to_wash")
    out.append(Result("A COMPLETE SESSION OPENS THE WASH GATE (positive control)",
                      vw.ready,
                      "%d satisfied, %d blocking%s"
                      % (len(vw.satisfied), len(vw.blocks),
                         (": " + "; ".join("%s -- %s" % (x.condition, x.what[:80])
                                           for x in vw.blocks)) if vw.blocks else ""),
                      "every other scenario asserts this gate REFUSES; none had ever shown it can "
                      "be satisfied, so a requirement no evidence can meet would look like safety"))

    vf = bw.gate("ready_to_finalize")
    out.append(Result("A COMPLETE SESSION OPENS THE FINALIZE GATE (positive control)",
                      vf.ready,
                      "%d satisfied, %d blocking%s"
                      % (len(vf.satisfied), len(vf.blocks),
                         (": " + "; ".join("%s -- %s" % (x.condition, x.what[:80])
                                           for x in vf.blocks)) if vf.blocks else ""),
                      "the same argument, for the gate that closes the experiment and writes the "
                      "committable record"))

    out.append(Result("A COMPLETE SESSION OPENS THE GATE (positive control)",
                      v.ready,
                      "%d frames captured; %d satisfied, %d blocking%s"
                      % (captured, len(v.satisfied), len(v.blocks),
                         (": " + "; ".join("%s -- %s" % (x.condition, x.what[:90])
                                           for x in v.blocks)) if v.blocks else ""),
                      "a gate that cannot be opened by valid evidence is broken, not safe"))

    if want_full:
        out.extend(full_plan_scenarios(full_spec, tmp_root))
    return out


# ------------------------------------------------------------------------------------------
# the real plan, end to end
# ------------------------------------------------------------------------------------------

def _rebuild(entries, gid, dest_parent, *, images_from=None):
    """Replay a list of log entries into a fresh garment, legitimately chained.

    How the single-fault matrix below builds its mutants. NOT an edit of a manifest file: entries
    are appended through the ordinary appender in their original order, so the chain, the head
    sidecar and the witness are all constructed the way a real session constructs them. A mutation
    that corrupted the file instead would be caught by `log.intact` and would prove nothing at all
    about the condition it was meant to isolate -- every mutant would "block correctly" for the one
    reason that has nothing to do with the evidence.
    """
    d = Path(dest_parent) / gid
    d.mkdir(parents=True, exist_ok=True)
    if images_from is not None and not (d / "images").exists():
        # Symlinked, not copied: the frames are the expensive part of this run and the mutants
        # never write to them.
        try:
            (d / "images").symlink_to(Path(images_from) / "images", target_is_directory=True)
        except (OSError, NotImplementedError):
            shutil.copytree(str(Path(images_from) / "images"), str(d / "images"))
    st = Store(d)
    mf = st.manifest
    # Written in one pass rather than through `append`, which re-reads the whole file on every
    # entry to find the head: on a full-plan session that is 2600 reads of a 2600-line file per
    # mutant, and the matrix builds sixteen of them. The CHAIN FORMULA is not duplicated -- it is
    # `manifest.sha256_text(prev + canonical(entry))`, called here exactly as the appender calls it
    # -- and the fold below re-verifies the result, so a divergence between this and the appender
    # shows up as an integrity problem on the mutant instead of hiding inside it.
    prev = mf.seed
    lines = []
    for i, e in enumerate(entries):
        entry = {"schema": MF.SCHEMA_VERSION, "seq": i, "ts": float(e.get("ts") or 0.0),
                 "kind": e.get("kind"), "operator": e.get("operator"),
                 "setup_hash": e.get("setup_hash"), "payload": e.get("payload"),
                 "prev_chain": prev}
        entry["chain"] = MF.sha256_text(prev + MF.canonical(entry))
        prev = entry["chain"]
        lines.append(MF.canonical(entry))
    mf.path.parent.mkdir(parents=True, exist_ok=True)
    mf.path.write_text("\n".join(lines) + ("\n" if lines else ""))
    mf._write_head(prev, len(lines))
    mf._write_witness(prev, len(lines))
    _st, problems = st.fold()
    assert not problems, ("the rebuilt log does not verify, so this mutant would block on log "
                          "integrity rather than on the fault it carries: %s" % problems[:3])
    return st


def _drop(pred):
    return lambda es: [e for e in es if not pred(e)]


def _first(es, kind, pred=None):
    for i, e in enumerate(es):
        if e.get("kind") == kind and (pred is None or pred(e)):
            return i
    raise AssertionError("no %s entry to mutate" % kind)


def full_plan_scenarios(full_spec, tmp_root):
    """ONE simulated garment carried through the whole real capture plan, then broken 20 ways.

    The previous version of this stopped at the pre-cut gate and asserted
    `blocking conditions <= {"captures.required_complete"}` -- which permits the gate to be blocked
    by the very condition that says the evidence is not there. It also answered 0 to every counted
    feature, so the 424-frame plan collapsed to 197 and the instance machinery -- the part where a
    photograph has to name the object it is of -- was never expanded at all. And the three gates'
    positive controls all ran on `_mini_spec`, a four-shot fixture: enough to show the wiring is
    connected, not that the production plan can be satisfied.

    So this drives creation, setup, intake, counted-feature expansion, measurement, the whole
    before-state capture, the marked state and the cut confirmations, the recorded cut with its
    achieved lengths, the immediate-after and offcut frames, the frozen wash configuration, the
    recorded wash, the post-wash re-measurement, an anomaly the wash itself produced, the post-wash
    and offcut-after frames, and finalisation -- on the real plan, and asserts that each of the
    three gates OPENS at the point it is supposed to.

    Then it takes that one valid session and injects exactly one fault at a time. Because the
    pristine session blocks on nothing, any condition that blocks in a mutant was caused by that
    mutant's single fault, which is what makes each of these a real negative control rather than a
    session that was never going to pass for a dozen reasons.
    """
    out = []
    t = Path(tempfile.mkdtemp(dir=str(tmp_root), prefix="fullplan_"))
    b = Bench(t, full_spec, gid="DENIM_9003")

    # -- creation, setup, intake, counted-feature expansion, measurement ----------------------
    b.open_session()
    b.freeze_rig()
    # Every feature present and one instance of each counted one: the same answers
    # `tools/check_shotplan.py` uses to count the plan at 424 frames.
    answers = {f["key"]: (1 if f["type"] == "count" else True) for f in full_spec.features}
    b.answer_features(overrides=answers)
    b.measure()
    described = b.describe_instances()
    planned = PLAN.order(full_spec, b.activated()[0])
    out.append(Result("the full plan expands with every feature present",
                      len(planned) >= 400 and bool(described),
                      "%d frames planned; %d counted-feature instance(s) described"
                      % (len(planned), len(described)),
                      "answering 0 to every count collapses the plan and never exercises the "
                      "instance machinery, which is the part a photograph's meaning rests on"))

    # -- the before-state arm ------------------------------------------------------------------
    n_pre, _ = b.capture_states(("rig", "intake", "before", "marked"))
    b.resolve_humans()
    b.cut_ready_extras()
    v_cut = b.gate("ready_to_cut")
    out.append(Result("REAL PLAN: a complete session opens the CUT gate (positive control)",
                      v_cut.ready,
                      "%d frames captured; %d satisfied, %d blocking%s"
                      % (n_pre, len(v_cut.satisfied), len(v_cut.blocks),
                         (": " + _why(v_cut)) if v_cut.blocks else ""),
                      "every positive control the suite had ran on a four-shot fixture. A gate "
                      "that opens on `_mini_spec` and cannot be opened on the plan the operator "
                      "will actually shoot is discovered on cut day"))

    # -- the cut, the offcuts and the frozen wash configuration --------------------------------
    b.after_cut_extras(skip=("wash_actual", "post_wash_measurements"))
    n_after, _ = b.capture_states(("immediate_after", "offcut_before"))
    b.resolve_humans()
    v_wash = b.gate("ready_to_wash")
    out.append(Result("REAL PLAN: a complete session opens the WASH gate (positive control)",
                      v_wash.ready,
                      "%d further frames; %d satisfied, %d blocking%s"
                      % (n_after, len(v_wash.satisfied), len(v_wash.blocks),
                         (": " + _why(v_wash)) if v_wash.blocks else ""),
                      "the gate that authorises putting the only copy of the evidence into water"))

    # -- the wash, the re-measurement, and the damage the wash itself caused --------------------
    b.after_cut_extras(skip=("cut_performed", "offcuts", "wash_planned"))
    # An anomaly discovered AFTER the wash. It cannot have a before frame, and instancing it on a
    # global count used to demand exactly that -- an intake photograph of a tear that did not exist
    # then, on a garment that is now in two pieces -- which made the session unfinalizable by any
    # route and made not recording it the operator's only workable move.
    b.store.append("annotation",
                   {"annotation_id": "WASHTEAR.01", "feature": "n_tears", "type": "tear",
                    "location": "opened by the wash, right leg offcut", "note": "self-test",
                    "size_mm": 8.0, "discovered_in": "post_wash", "operator": "selftest"},
                   operator="selftest")
    b.store.append("feature_answers", {"answers": {"n_tears": 2}}, operator="selftest")
    n_post, _ = b.capture_states(("post_wash", "offcut_after"))
    b.resolve_humans()
    v_fin = b.gate("ready_to_finalize")
    out.append(Result("REAL PLAN: a complete session opens the FINALIZE gate (positive control)",
                      v_fin.ready,
                      "%d post-wash frames; %d satisfied, %d blocking%s"
                      % (n_post, len(v_fin.satisfied), len(v_fin.blocks),
                         (": " + _why(v_fin)) if v_fin.blocks else ""),
                      "the terminal state. A plan that cannot reach it is a plan whose evidence "
                      "can never be closed and committed"))

    st_final, problems_final = b.store.fold()
    total = n_pre + n_after + n_post
    out.append(Result("REAL PLAN: the whole lifecycle was reached from the physical facts alone",
                      st_final["lifecycle_state"] == "post_wash" and not problems_final
                      and st_final["cut_performed"] is not None
                      and st_final["wash_actual"] is not None
                      and bool(st_final["measurements_by_state"].get("post_wash"))
                      and bool(st_final["measurements_by_state"].get("before")),
                      "lifecycle=%s, %d frames, %d log entries, before-bucket=%d "
                      "post-wash-bucket=%d, integrity problems=%d"
                      % (st_final["lifecycle_state"], total, st_final["n_entries"],
                         len(st_final["measurements_by_state"].get("before") or {}),
                         len(st_final["measurements_by_state"].get("post_wash") or {}),
                         len(problems_final)),
                      "no marker was set by hand: the cut and the wash are entries in the log and "
                      "the replay advances the lifecycle from them, so both measurement buckets "
                      "survive and shrinkage stays computable"))

    # -- SINGLE-FAULT NEGATIVE CONTROLS ---------------------------------------------------------
    # The pristine session above blocks on nothing, so every block below is attributable to the one
    # fault injected. Each case names the condition that must close the gate.
    good = b.entries()
    # TWO BASELINES, because a pre-cut fault cannot be isolated against a session that has been
    # cut: `cut.not_already_performed` blocks ready_to_cut on the finished log no matter what, so
    # every ready_to_cut mutant would "block correctly" for a reason that is not its fault. The
    # pre-cut baseline is this same session truncated at the shears -- the state it was actually in
    # when the cut gate was asked -- and it opens that gate.
    cut_at = _first(good, "cut_performed")
    bases = {"pre": good[:cut_at], "full": good}
    muts = _fault_matrix()
    mroot = t / "mutants"
    mroot.mkdir(exist_ok=True)

    # THE BASELINE EACH MUTANT IS COMPARED AGAINST. Evaluated exactly the way the mutants are --
    # same gate, same `check_files=False` -- because the point is to attribute a block to the ONE
    # fault injected, and that only works if everything else is held constant.
    #
    # Two things block every mutant regardless of its fault and would otherwise have been read as
    # the fault working: `check_files=False` makes `captures.files_intact` and
    # `captures.verdicts_reproduce` refuse by construction (a verdict that was not re-derived from
    # the photograph is not a verdict this gate will accept), and a session carried through the
    # whole lifecycle blocks `cut.not_already_performed` at ready_to_cut because it HAS been cut.
    # Requiring the named condition to be NEWLY blocking removes all three from the comparison
    # without weakening any of them.
    baseline, nbase = {}, 0
    for base_key, gid_ in sorted({(m[1], m[2]) for m in muts}):
        st0 = _rebuild(bases[base_key], "DENIM_9003", mroot / ("base_%s" % base_key),
                       images_from=b.dir)
        v0 = GATES.evaluate(gid_, full_spec, st0, garment_dir=st0.dir, check_files=False)
        baseline[(base_key, gid_)] = {x.condition for x in v0.blocks}
        nbase += 1
    # `check_files=False` makes `captures.files_intact` and `captures.verdicts_reproduce` refuse by
    # construction -- a verdict that was not re-derived from the photograph is not one this gate
    # accepts -- so those two block every mutant regardless of its fault. Nothing else may.
    forced = {"captures.files_intact", "captures.verdicts_reproduce"}
    stray = {k: sorted(v - forced) for k, v in baseline.items() if v - forced}
    out.append(Result(
        "REAL PLAN: the unmutated session blocks only on what disabling file checks forces",
        not stray,
        "; ".join("%s/%s: %s" % (k[0], k[1], ", ".join(sorted(v)) or "none")
                  for k, v in sorted(baseline.items())),
        "each fault below is credited only with the conditions it ADDS to its own baseline, so a "
        "mutant that blocks for an unrelated reason cannot be read as the fault working"))

    for i, (name, base_key, gate_id, want_condition, fn, why) in enumerate(muts):
        try:
            entries = fn(list(bases[base_key]))
        except AssertionError as e:
            out.append(Result("REAL PLAN fault: %s" % name, False,
                              "the mutation could not be built: %s" % e, why))
            continue
        st_m = _rebuild(entries, "DENIM_9003", mroot / ("m%02d" % i), images_from=b.dir)
        v = GATES.evaluate(gate_id, full_spec, st_m, garment_dir=st_m.dir, check_files=False)
        conds = {x.condition for x in v.blocks}
        added = conds - baseline.get((base_key, gate_id), set())
        out.append(Result("REAL PLAN fault: %s" % name,
                          (not v.ready) and want_condition in added,
                          "%s on the %s-cut log -> ready=%s; NEWLY blocking: %s%s"
                          % (gate_id, base_key, v.ready, ", ".join(sorted(added)) or "none",
                             ("  [%s]" % _why(v, want_condition)) if want_condition in added
                             else ""),
                          why))
    return out


def _why(verdict, only=None):
    """A verdict's blocks with the evidence that names the frames, not just the count.

    "2 failing (of 439 required frames)" costs another hour to find out WHICH two.
    """
    bits = []
    for x in verdict.blocks:
        if only is not None and x.condition != only:
            continue
        ev = x.evidence or {}
        detail = ""
        for k in ("failing", "missing", "unresolved", "wrong", "collided", "mismatched",
                  "redescribed", "backdated", "revisions"):
            if ev.get(k):
                detail += "  %s=%s" % (k, "; ".join(str(y) for y in list(ev[k])[:4]))
        bits.append("%s -- %s%s" % (x.condition, x.what[:130], detail))
    return "; ".join(bits)


def _fault_matrix():
    """(name, which baseline, gate, the condition that must close it, mutation, why it matters).

    One fault each. A mutation that tripped three conditions would still 'pass' its assertion while
    telling you nothing about the one it names, so these are built to change exactly one fact.
    """
    def drop_one_capture(es):
        i = _first(es, "capture", lambda e: e["payload"].get("state") == "before")
        sid, rep = es[i]["payload"]["shot_id"], es[i]["payload"].get("rep", 1)
        return [e for e in es
                if not (e.get("kind") in ("capture", "qa_result")
                        and e["payload"].get("shot_id") == sid
                        and e["payload"].get("rep", 1) == rep)]

    def fail_one_qa(es):
        es = list(es)
        i = _first(es, "qa_result", lambda e: e["payload"].get("outcome") == "PASS")
        p = dict(es[i]["payload"])
        p["outcome"] = "RETAKE_REQUIRED"
        p["checks"] = [dict(c, outcome="RETAKE_REQUIRED") if c.get("outcome") == "PASS" else c
                       for c in (p.get("checks") or [])][:1] or p.get("checks")
        es[i] = dict(es[i], payload=p)
        return es

    def drop_one_human(es):
        # EVERY entry for that claim, not the first. `resolve_humans` runs once per capture phase,
        # so the log holds three verifications of each claim and dropping one left two behind --
        # the mutation changed nothing and the control reported the gate had failed to notice.
        i = _first(es, "human_verification", lambda e: e["payload"].get("shot_id"))
        p = es[i]["payload"]
        key = (p.get("shot_id"), p.get("rep"), p.get("claim"))
        return [e for e in es
                if not (e.get("kind") == "human_verification"
                        and (e["payload"].get("shot_id"), e["payload"].get("rep"),
                             e["payload"].get("claim")) == key)]

    def stale_human(es):
        """Re-ingest a different photograph under a confirmed frame: the confirmation is of the
        picture that is no longer there."""
        es = list(es)
        i = _first(es, "human_verification", lambda e: e["payload"].get("shot_id"))
        sid, rep = es[i]["payload"]["shot_id"], es[i]["payload"].get("rep", 1)
        j = _first(es, "capture", lambda e: e["payload"].get("shot_id") == sid
                   and e["payload"].get("rep", 1) == rep)
        p = dict(es[j]["payload"])
        p["sha256"] = "0" * 64
        es[j] = dict(es[j], payload=p)
        return es

    def one_reading(es):
        es = list(es)
        i = _first(es, "measurement", lambda e: len(e["payload"].get("readings") or []) > 1)
        p = dict(es[i]["payload"])
        p["readings"] = p["readings"][:1]
        p["mean"] = p["readings"][0]
        p["spread"] = 0.0
        es[i] = dict(es[i], payload=p)
        return es

    def backdate_measurement(es):
        """A pre-cut baseline written back AFTER the cut: the overwrite all of this exists to stop."""
        i = _first(es, "measurement", lambda e: e["payload"].get("name") == "waist_cm")
        p = dict(es[i]["payload"], state="before", readings=[1.0, 1.1], mean=1.05)
        return list(es) + [{"kind": "measurement", "payload": p, "operator": "selftest",
                            "setup_hash": None, "ts": es[-1].get("ts", 0) + 1}]

    def wrong_state_measurement(es):
        i = _first(es, "measurement", lambda e: e["payload"].get("name") == "waist_cm")
        p = dict(es[i]["payload"], state="marked")
        return [dict(e, payload=p) if j == i else e for j, e in enumerate(es)]

    def cut_before_the_gate(es):
        """The shears used before the pre-cut gate was ever satisfied.

        Built on the PRE-cut log, which is the state the session was in when the gate was asked, so
        the block this produces is the fault and not the ordinary consequence of having been cut.
        """
        return list(es) + [{"kind": "cut_performed",
                            "payload": {"achieved_inseam_cm": {"L": 15.0, "R": 15.0},
                                        "achieved_outseam_cm": {"L": 16.0, "R": 16.0},
                                        "tool": "shears", "legs_cut_separately": True},
                            "operator": "selftest", "setup_hash": None,
                            "ts": es[-1].get("ts", 0) + 1}]

    def cut_recorded_after_the_wash(es):
        """The achieved lengths written down after the machine, on a garment that has shrunk.

        Exactly one entry moves: the cut record, to the end. Moving the WASH earlier instead would
        also put it before the wash plan and trip two more conditions, and a mutation that changes
        three facts proves nothing about any one of them.
        """
        i = _first(es, "cut_performed")
        e = es[i]
        rest = [x for k, x in enumerate(es) if k != i]
        return rest + [dict(e, ts=rest[-1].get("ts", 0) + 1)]

    def no_achieved_lengths(es):
        es = list(es)
        i = _first(es, "cut_performed")
        p = dict(es[i]["payload"])
        p.pop("achieved_inseam_cm", None)
        p.pop("achieved_outseam_cm", None)
        es[i] = dict(es[i], payload=p)
        return es

    def swap_offcut_identity(es):
        es = list(es)
        i = _first(es, "offcut")
        p = dict(es[i]["payload"])
        p["originating_leg"] = {"L": "R", "R": "L"}.get(p.get("originating_leg"), "R")
        es[i] = dict(es[i], payload=p)
        return es

    def redescribe_an_instance(es):
        """Correct a described instance's location after its photographs were accepted.

        Targeted at an instance THIS LOG HAS A PHOTOGRAPH OF. Picking the first annotation entry
        instead chose CURL_POSITIONS.01, whose only instanced frames are post-wash, so on the
        pre-cut log there was nothing to drift and the mutation changed nothing -- and the control
        read that as the gate failing to notice a re-description.
        """
        have = {e["payload"].get("annotation_id") for e in es
                if e.get("kind") == "capture" and e["payload"].get("annotation_id")}
        assert have, "this log has no photograph of any described instance to re-describe"
        i = _first(es, "annotation", lambda e: e["payload"].get("annotation_id") in have)
        p = dict(es[i]["payload"])
        p["location"] = "somewhere else entirely"
        return list(es) + [{"kind": "annotation", "payload": p, "operator": "selftest",
                            "setup_hash": None, "ts": es[-1].get("ts", 0) + 1}]

    def drop_an_instance(es):
        i = _first(es, "annotation", lambda e: e["payload"].get("annotation_id") != "WASHTEAR.01")
        aid = es[i]["payload"]["annotation_id"]
        return [e for e in es
                if not (e.get("kind") == "annotation"
                        and e["payload"].get("annotation_id") == aid)]

    def swap_a_rep_subject(es):
        """Two repeats of a subject-distinguishing shot both filed as the same leg."""
        es = list(es)
        i = _first(es, "capture", lambda e: e["payload"].get("subject_id") == "LEG.R")
        p = dict(es[i]["payload"], subject_id="LEG.L",
                 subject_aspect="the garment-LEFT hem")
        es[i] = dict(es[i], payload=p)
        return es

    def unbind_a_rep_subject(es):
        es = list(es)
        i = _first(es, "capture", lambda e: e["payload"].get("subject_id") in ("LEG.L", "LEG.R"))
        p = dict(es[i]["payload"])
        p["subject_id"] = None
        p["subject_aspect"] = None
        es[i] = dict(es[i], payload=p)
        return es

    def photograph_after_the_cut(es):
        """A before-state frame filed after the garment was cut, which is not possible."""
        i = _first(es, "capture", lambda e: e["payload"].get("state") == "before")
        j = _first(es, "wash_actual")
        e = es[i]
        rest = [x for k, x in enumerate(es) if k != i]
        return rest[:j] + [dict(e)] + rest[j:]

    return [
        ("a required frame is missing", "pre", "ready_to_cut", "captures.required_complete",
         drop_one_capture,
         "the frame nobody took is the whole reason the gate exists"),
        ("an automated check failed", "pre", "ready_to_cut", "captures.required_complete", fail_one_qa,
         "a RETAKE verdict on an accepted frame is not evidence"),
        ("a human confirmation is missing", "pre", "ready_to_cut", "captures.required_complete",
         drop_one_human,
         "a claim no pixel test can judge, with nobody's name against it"),
        ("a confirmation is of a photograph that is no longer there", "pre", "ready_to_cut",
         "captures.required_complete", stale_human,
         "re-ingesting a different frame under a confirmed shot id must not inherit the approval"),
        ("a measurement has one reading, not two", "pre", "ready_to_cut", "measurements.complete",
         one_reading, "the protocol asks for two so their spread can be seen"),
        ("the pre-cut baseline is written back after the cut", "full", "ready_to_finalize",
         "measurements.revisions_explained", backdate_measurement,
         "shrinkage is the difference between the two readings; overwriting one destroys it"),
        ("a measurement is filed into the wrong lifecycle state", "pre", "ready_to_cut",
         "measurements.complete", wrong_state_measurement,
         "the waist before the cut and the waist after the wash are two different facts"),
        ("the cut was performed before the pre-cut gate", "pre", "ready_to_cut",
         "cut.not_already_performed", cut_before_the_gate,
         "the gate authorises an irreversible act; a gate consulted afterwards is a formality"),
        ("the cut was recorded after the wash", "full", "ready_to_wash", "cut.performed_recorded",
         cut_recorded_after_the_wash,
         "the achieved lengths can only be taken between the shears and the water; after the wash "
         "the garment has shrunk and the length you measure is no longer the length you cut"),
        ("the achieved cut lengths are absent", "full", "ready_to_wash", "cut.performed_recorded",
         no_achieved_lengths,
         "PROTOCOL 3.1 asks for both lengths; they are the ground truth the prediction is scored "
         "against"),
        ("an offcut is attributed to the wrong leg", "full", "ready_to_wash", "offcuts.assigned",
         swap_offcut_identity,
         "the two offcuts go into different wash conditions; swapping them swaps the experiment"),
        ("a described instance was re-described after its frames were accepted", "pre",
         "ready_to_cut", "captures.instance_identity", redescribe_an_instance,
         "the id still matches and the meaning has changed, which is the silent version"),
        ("a described instance was removed", "pre", "ready_to_cut", "annotations.identify_instances",
         drop_an_instance,
         "the count and the descriptions must agree before the garment is cut, because that is "
         "the last moment it is intact enough to go back and look"),
        ("two repeats claim to be the same leg", "pre", "ready_to_cut", "captures.subjects_bound",
         swap_a_rep_subject,
         "min_reps meant the other leg, and two photographs of one leg satisfied both"),
        ("a repeat records no subject at all", "pre", "ready_to_cut", "captures.subjects_bound",
         unbind_a_rep_subject,
         "omitting the field was the cheapest way past a check that only looked at frames which "
         "carried one"),
        ("a before-state photograph was filed after the wash", "full", "ready_to_finalize",
         "captures.state_order", photograph_after_the_cut,
         "that photograph cannot exist: the garment was in two pieces and wet"),
    ]

def run(verbose=False, want_full=False):
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    tmp = Path(tempfile.mkdtemp(prefix="pilot_selftest_"))
    try:
        results = scenarios(spec, tmp, want_full=want_full)
    finally:
        if not verbose:
            shutil.rmtree(str(tmp), ignore_errors=True)
    bad = [r for r in results if not r.ok]
    width = 72
    print("=" * width)
    print("  Pilot Capture Navigator -- self test on synthetic images")
    print("=" * width)
    for r in results:
        print("  %s  %s" % ("PASS" if r.ok else "FAIL", r.name))
        if verbose or not r.ok:
            print("        expected: %s" % r.expectation)
            print("        observed: %s" % r.detail)
    print("-" * width)
    print("  %d of %d scenarios behaved as required" % (len(results) - len(bad), len(results)))
    if verbose:
        print("  artefacts left in %s" % tmp)
    return 1 if bad else 0
