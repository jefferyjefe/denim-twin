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
import zlib
from pathlib import Path

from . import gates as GATES
from . import hem as HEM
from . import plan as PLAN
from . import qa as QA
from . import spec as SPEC
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
        return PLAN.activate(self.spec, st["features"], st["measurements"], st.get("cut_spec"))

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

    def add(self, shot, rep, src, *, confirm_all=True, setup_hash_override="__default__"):
        from .manifest import read_exif, exif_timestamp
        from . import qa_primitives as Q
        import cv2
        dest, sha, already = ingest_photo(src, self.dir / "images" / shot["state"],
                                          shot["shot_id"], rep)
        rel = str(dest.relative_to(self.dir))
        exif = read_exif(dest)
        ts = exif_timestamp(exif) or (time.time() + rep * 120)
        img = cv2.imread(str(dest))
        sh = self.setup_hash if setup_hash_override == "__default__" else setup_hash_override
        self.store.append("capture",
                          {"shot_id": shot["shot_id"], "rep": rep, "path": rel, "sha256": sha,
                           "exif": exif, "exif_ts": ts,
                           "width": img.shape[1] if img is not None else None,
                           "height": img.shape[0] if img is not None else None,
                           "dhash": Q.dhash_bits(img).hex() if img is not None else None,
                           "state": shot["state"], "region_id": shot.get("region_id")},
                          operator="selftest", setup_hash=sh)
        st, _ = self.store.fold()
        board, bspec = self.board
        compare = []
        for (sid, r), c in sorted(st["captures"].items()):
            if (sid, r) == (shot["shot_id"], rep):
                continue
            p = self.dir / (c.get("path") or "")
            present = p.exists()
            prev = (sid == shot["shot_id"] and r == rep - 1)
            oimg = cv2.imread(str(p)) if (prev and present) else None
            compare.append({"shot_id": sid, "rep": r, "sha256": c.get("sha256"),
                            "self_sha256": sha, "image": oimg,
                            "path": str(p) if present else None,
                            "undecodable": not present,
                            "dhash": c.get("dhash"),
                            "pose": Q.garment_pose_of(oimg, board, bspec) if oimg is not None else None,
                            "exif_ts": c.get("exif_ts"), "this_exif_ts": ts,
                            "is_previous_rep": prev})
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
        """Record a verification for every claim a check referred to a person."""
        st, _ = self.store.fold()
        n = 0
        for (sid, rep), q in sorted(st["qa"].items()):
            for c in (q.get("checks") or []):
                if c.get("outcome") == QA.HUMAN:
                    cap = st["captures"].get((sid, rep)) or {}
                    self.store.append("human_verification",
                                      {"shot_id": sid, "rep": rep, "claim": c["check_id"],
                                       "value": True, "verifier_name": "selftest",
                                       "operator": "selftest",
                                       "capture_sha256": cap.get("sha256")},
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
        for sh_ in bb.activated()[0]:
            for r_ in range(1, int(sh_.get("min_reps", 1)) + 1):
                bb.add(sh_, r_, bb.synth_for(sh_, r_, relay=r_))
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
    for sh_ in b.activated()[0]:
        for r_ in range(1, int(sh_.get("min_reps", 1)) + 1):
            b.add(sh_, r_, b.synth_for(sh_, r_, relay=r_))
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
    b = new("backdated", spec=mini_sp, gid="DENIM_9215")
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
                      "attribution was set membership over the whole log, so a frame back-dated a "
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
    out.append(Result("A COMPLETE SESSION OPENS THE GATE (positive control)",
                      v.ready,
                      "%d frames captured; %d satisfied, %d blocking%s"
                      % (captured, len(v.satisfied), len(v.blocks),
                         (": " + "; ".join("%s -- %s" % (x.condition, x.what[:90])
                                           for x in v.blocks)) if v.blocks else ""),
                      "a gate that cannot be opened by valid evidence is broken, not safe"))

    if want_full:
        # The full plan driven end to end. What this can and cannot assert needs stating, because
        # the honest version is narrower than "the gate opens".
        #
        # The synthetic garment is one silhouette on one backdrop. It cannot render 290 different
        # FRAMINGS -- a frame written as "the hem edge filling the width" is a different photograph
        # from a whole-garment overhead, and the fixture draws the same jeans for both. So a frame
        # can fail a framing requirement here for a reason that says nothing about the system.
        #
        # What this run therefore asserts is the part that IS about the system: that no GATE
        # CONDITION -- log integrity, feature answers, plan expansion, rig attribution, measurement
        # completeness, relay independence, reposition records, image reuse, file integrity, cut
        # specification, second-person verification -- blocks a session in which all of those were
        # supplied. Frames the fixture cannot render are reported separately and counted.
        b = new("happyfull", spec=full_spec, gid="DENIM_9003")
        b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
        shots, _m = b.activated()
        req = [s for s in shots if s["state"] in ("rig", "intake", "before", "marked")
               and s["necessity"] != "optional"]
        n = 0
        for s in req:
            for rep in range(1, int(s.get("min_reps", 1)) + 1):
                b.add(s, rep, b.synth_for(s, rep, relay=rep))
                n += 1
        b.resolve_humans()
        b.cut_ready_extras()
        v = b.gate()
        conditions = {x.condition for x in v.blocks}
        fixture_only = conditions <= {"captures.required_complete"}
        st_, _ = b.store.fold()
        fixture_frames = sorted(
            "%s r%d" % k for k, q in st_["qa"].items() if q.get("outcome") != QA.PASS
            and all(c.get("check_id") in ("subject_span", "resolution", "scale", "subject_extent",
                                          "duplicate_content", "camera_tilt")
                    for c in (q.get("checks") or []) if c.get("outcome") != QA.PASS))
        out.append(Result(
            "on the FULL plan, no gate condition blocks a complete session",
            fixture_only,
            "%d frames captured; blocking conditions: %s; %d frame(s) the synthetic garment "
            "cannot frame (%s)"
            % (n, ", ".join(sorted(conditions)) or "none", len(fixture_frames),
               ", ".join(fixture_frames[:4]) or "-"),
            "every condition about evidence, integrity and verification is satisfiable on the real "
            "plan; only per-frame framing requirements the fixture cannot render may remain"))
    return out


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
