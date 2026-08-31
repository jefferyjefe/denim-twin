#!/usr/bin/env python3
"""Pilot Capture Navigator -- guided, verified evidence collection for one physical garment.

    tools/pilot.py setup                      freeze the rig, record the calibration readings
    tools/pilot.py new                        create the next DENIM_NNNN and open a session
    tools/pilot.py intake     GARMENT         answer the feature questionnaire
    tools/pilot.py measure    GARMENT         record the physical measurements
    tools/pilot.py plan       GARMENT         the ordered capture list and the time it will take
    tools/pilot.py next       GARMENT         the single best next action
    tools/pilot.py add        GARMENT SHOT F  ingest a photograph and check it
    tools/pilot.py confirm    GARMENT SHOT C  record a human verification
    tools/pilot.py cutspec    GARMENT --inseam N
    tools/pilot.py packet     GARMENT         the printable cut packet
    tools/pilot.py precut     GARMENT         THE GATE: may this garment be cut?
    tools/pilot.py wash       GARMENT         record planned and actual wash settings
    tools/pilot.py offcut     GARMENT         track the offcut samples
    tools/pilot.py hem        GARMENT         hem-loop coverage, gaps and the next macro
    tools/pilot.py status     GARMENT         coverage by state and region
    tools/pilot.py serve      [GARMENT]       the phone-friendly local app
    tools/pilot.py finalize   GARMENT         the post-wash gate and the sanitised manifest

The CLI is the whole workflow. The web app is a front end onto these same functions, which is what
makes "the CLI is the source of truth" a testable statement rather than a slogan: tests drive the
CLI, and the server's handlers call the same module functions.

Exit codes follow tools/verify.py: 0 the thing asked for holds, 1 it does not, 2 it could not be
determined because evidence is missing. `precut` uses all three, and a gate that cannot be evaluated
exits 2 -- never 0.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import cutspec as CUT          # noqa: E402
from denimtwin.pilot import gates as GATES          # noqa: E402
from denimtwin.pilot import hem as HEM              # noqa: E402
from denimtwin.pilot import plan as PLAN            # noqa: E402
from denimtwin.pilot import qa as QA                # noqa: E402
from denimtwin.pilot import spec as SPEC            # noqa: E402
from denimtwin.pilot.store import Store, setup_hash, diff_planned_actual   # noqa: E402
from denimtwin.pilot.manifest import ingest_photo, read_exif, exif_timestamp, sha256_file  # noqa: E402

GARMENTS = ROOT / "data" / "garments"
SPEC_PATH = ROOT / "protocol" / "shotplan" / "shotplan.json"
BOARD_PATH = ROOT / "protocol" / "charuco_board.json"
STATES = ["before", "marked", "immediate_after", "post_wash"]

OK, FAIL, UNAVAILABLE = 0, 1, 2


def load_spec():
    if not SPEC_PATH.exists():
        raise SystemExit("no shot-plan specification at %s\n"
                         "This is the document the gate enumerates from; without it nothing can be "
                         "required and therefore nothing can be verified." % SPEC_PATH)
    return SPEC.load(SPEC_PATH)


def garment_dir(gid):
    d = GARMENTS / gid
    if not d.exists():
        raise SystemExit("no such garment: %s (looked in %s)" % (gid, d))
    return d


def board():
    try:
        from denimtwin.capture.board import load_board
        return load_board(BOARD_PATH)
    except Exception as e:
        print("warning: calibration board unavailable (%s); board-dependent checks will report "
              "UNAVAILABLE_CHECK rather than passing" % e, file=sys.stderr)
        return None, None


def _fmt_time(seconds):
    m = int(round(seconds / 60.0))
    return "%dh %02dm" % (m // 60, m % 60) if m >= 60 else "%d min" % m


def _prompt(text, default=None, cast=str):
    suffix = " [%s]" % default if default is not None else ""
    while True:
        raw = input("%s%s: " % (text, suffix)).strip()
        if not raw and default is not None:
            return default
        if not raw:
            continue
        try:
            return cast(raw)
        except (ValueError, TypeError) as e:
            print("  not valid (%s)" % e)


def _bool(s):
    s = str(s).strip().lower()
    if s in ("y", "yes", "true", "1"):
        return True
    if s in ("n", "no", "false", "0"):
        return False
    raise ValueError("answer y or n")


# --------------------------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------------------------

def cmd_new(a):
    import subprocess
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "new_garment.py")],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(out.stderr or "new_garment.py failed")
    gid = out.stdout.strip()
    spec = load_spec()
    st = Store(GARMENTS / gid)
    st.append("session_opened", {"spec_version": spec.version, "spec_hash": spec.content_hash,
                                 "protocol_version": spec.doc["protocol_version"]})
    st.append("state_transition", {"to": "rig"})
    print(gid)
    print("session opened under shot plan %s (%s)" % (spec.version, spec.content_hash[:12]))
    print("photographs will be stored under %s -- gitignored, never uploaded"
          % (GARMENTS / gid / "images"))
    print("next: tools/pilot.py setup %s" % gid)
    return OK


def cmd_setup(a):
    spec = load_spec()
    gid = a.garment
    st = Store(garment_dir(gid))
    cfg = {}
    print("Freezing the rig. Every capture records this configuration's hash, so a change here is")
    print("visible later rather than silently mixing two setups.\n")
    cfg["camera_model"] = _prompt("camera / phone model", "iPhone")
    cfg["mount_height_cm"] = _prompt("camera height above the surface, cm", 80.0, float)
    cfg["lens"] = _prompt("lens for whole-garment frames (main/ultrawide/tele)", "main")
    cfg["backdrop"] = _prompt("backdrop (matte, dark, contrasting)", "dark green matte")
    cfg["lighting"] = _prompt("lighting (model / setting)", "two diffuse at 45 deg")
    cfg["leg_gap_cm"] = _prompt("frozen gap between the legs, cm", 4.0, float)
    cfg["exposure_locked"] = _prompt("exposure and white balance locked? (y/n)", "y", _bool)
    cfg["room"] = _prompt("room / location name", "studio")
    h = setup_hash(cfg)
    st.append("setup_frozen", {"setup": cfg, "setup_hash": h,
                               "reason": a.reason or "initial freeze"})
    print("\nrig frozen: %s\n" % h[:16])

    print("Calibration readings. Each must be recorded before any garment capture counts.\n")
    checks = {}
    n = _prompt("how many board squares did you span with the rule?", 8, int)
    mm = _prompt("total measured length of those %d squares, mm" % n, float(n) * 25.0, float)
    checks["board_square_measured"] = {"check": "board_square_measured", "squares_spanned": n,
                                       "measured_mm": mm, "outcome": QA.PASS}
    per = mm / float(n)
    off = abs(per - GATES.BOARD_SQUARE_MM)
    print("  -> %.2f mm per square (%.2f mm from the declared %.1f mm)%s"
          % (per, off, GATES.BOARD_SQUARE_MM,
             "" if off <= GATES.BOARD_SQUARE_TOLERANCE_MM else "  <-- OUT OF TOLERANCE"))
    for key, question in (
            ("empty_backdrop", "empty-backdrop photograph taken and stored"),
            ("board_verification", "ChArUco board photographed and detected"),
            ("lighting_test", "lighting test frame taken, no hotspots or shadows on the garment area"),
            ("exposure_white_balance", "grey/white reference frame taken with exposure and WB locked"),
            ("camera_height", "camera height measured and recorded"),
            ("lens_selection", "lens chosen and locked for the session"),
            ("backdrop_identified", "backdrop identified and will not change during the session"),
            ("daylight_controlled", "daylight excluded or constant (blinds down / no window)"),
            ("board_garment_coplanar", "board sits on the SAME surface plane as the garment")):
        ans = _prompt("  %s? (y/n)" % question, "y", _bool)
        checks[key] = {"check": key, "outcome": QA.PASS if ans else QA.RETAKE,
                       "confirmed_by": a.operator}
    for c in checks.values():
        st.append("setup_check", c, operator=a.operator, setup_hash=h)
    bad = [k for k, v in checks.items() if v["outcome"] != QA.PASS]
    print("\n%d/%d calibration readings pass%s"
          % (len(checks) - len(bad), len(checks), "" if not bad else "; outstanding: " + ", ".join(bad)))
    return OK if not bad and off <= GATES.BOARD_SQUARE_TOLERANCE_MM else FAIL


def cmd_intake(a):
    spec = load_spec()
    st = Store(garment_dir(a.garment))
    state, _ = st.fold()
    answers = dict(state["features"])
    print("Garment features. These decide which photographs the plan will require.\n"
          "An unanswered question that would REMOVE a photograph blocks the cut gate; one that\n"
          "would add a photograph does not, because the safe reading of 'I don't know' is 'it might\n"
          "be there, so photograph it'.\n")
    for f in spec.features:
        k = f["key"]
        cur = answers.get(k)
        if f["type"] == "bool":
            v = _prompt("%s (y/n)" % f["prompt"], "y" if cur else ("n" if cur is False else
                                                                   ("y" if f["unanswered_means"] == "present" else "n")), _bool)
        elif f["type"] == "count":
            v = _prompt("%s (number)" % f["prompt"], cur if cur is not None else 0, int)
        elif f["type"] == "number":
            v = _prompt(f["prompt"], cur if cur is not None else f.get("default"), float)
        elif f["type"] == "enum":
            v = _prompt("%s %s" % (f["prompt"], f.get("options")), cur or f.get("default"))
        else:
            v = _prompt(f["prompt"], cur or f.get("default", ""))
        answers[k] = v
    st.append("feature_answers", {"answers": answers}, operator=a.operator)
    shots, meta = PLAN.activate(spec, answers, state.get("measurements"))
    ordered = PLAN.order(spec, shots)
    print("\n%d shots activated, %d frames including repeats, estimated %s"
          % (len(shots), len(ordered), _fmt_time(PLAN.estimate_seconds(spec, ordered))))
    return OK


def cmd_measure(a):
    st = Store(garment_dir(a.garment))
    print("Physical measurements. Each reading is taken INDEPENDENTLY -- lay the tape again,\n"
          "do not copy the first number. Readings that disagree beyond tolerance block the cut.\n")
    for name, n in sorted(GATES.REQUIRED_MEASUREMENTS.items()):
        tol = GATES.MEASUREMENT_TOLERANCE.get(name, GATES.MEASUREMENT_TOLERANCE["_default_cm"])
        readings = []
        for i in range(n):
            readings.append(_prompt("  %s reading %d of %d" % (name, i + 1, n), cast=float))
        spread = max(readings) - min(readings)
        mean = sum(readings) / len(readings)
        flag = "" if spread <= tol else "  <-- readings differ by %.2f, tolerance %.2f" % (spread, tol)
        print("    mean %.2f%s" % (mean, flag))
        st.append("measurement", {"name": name, "readings": readings, "mean": mean,
                                  "spread": spread, "tolerance": tol,
                                  "in_tolerance": spread <= tol}, operator=a.operator)
    return OK


def cmd_plan(a):
    spec = load_spec()
    st = Store(garment_dir(a.garment))
    state, _ = st.fold()
    shots, meta = PLAN.activate(spec, state["features"], state["measurements"])
    ordered = PLAN.order(spec, shots, state=a.state)
    done = st.done_keys()
    print("%s -- %d frames, %s remaining\n"
          % (a.garment, len(ordered), _fmt_time(PLAN.estimate_seconds(
              spec, [e for e in ordered if (e["shot_id"], e["rep"]) not in done]))))
    cur = None
    for e in ordered:
        grp = (e["state"], PLAN.ORIENTATION.get(e["garment_side"], "either"),
               e["relay_generation"], e.get("camera_height_group"), e.get("lens"))
        if grp != cur:
            cur = grp
            print("\n-- %s | %s | lay %d | %s | %s lens" % grp)
        mark = "x" if (e["shot_id"], e["rep"]) in done else " "
        print("  [%s] %-46s r%d/%d  %-9s %3ds  %s"
              % (mark, e["shot_id"], e["rep"], e["rep_of"], e["necessity"],
                 e.get("est_seconds", 0), e.get("region_id", "")))
    return OK


def cmd_next(a):
    spec = load_spec()
    st = Store(garment_dir(a.garment))
    state, _ = st.fold()
    shots, _m = PLAN.activate(spec, state["features"], state["measurements"])
    ordered = PLAN.order(spec, shots, state=a.state)
    done = st.done_keys()
    e = PLAN.next_action(spec, ordered, done)
    if e is None:
        print("nothing left in this order. Run `precut` to see whether the gate opens.")
        return OK
    remaining = [x for x in ordered if (x["shot_id"], x["rep"]) not in done]
    print("NEXT: %s   (repeat %d of %d)" % (e["shot_id"], e["rep"], e["rep_of"]))
    print("  state          %s" % e["state"])
    print("  region         %s" % e.get("region_id"))
    print("  side up        %s" % e["garment_side"])
    print("  camera         %s, %s lens, height group %s"
          % (e["camera_angle"], e.get("lens"), e.get("camera_height_group")))
    if e.get("camera_position"):
        print("  stand          %s" % e["camera_position"])
    print("  framing        %s" % e["framing"])
    print("  scale          %s%s" % (e["scale_reference"],
                                     " -- " + e["scale_placement"] if e.get("scale_placement") else ""))
    if e.get("needs_relay_before"):
        print("  ** LIFT the garment clear, shake it out and lay it again before this frame. **")
    if e.get("needs_camera_reposition_before"):
        print("  ** Take the phone off the mount and remount it before this frame. **")
    if e.get("needs_second_person"):
        print("  ** needs a second person **")
    print("  why            %s" % e["purpose"])
    print("\n  %d frames left, about %s" % (len(remaining), _fmt_time(
        PLAN.estimate_seconds(spec, remaining))))
    print("  add it with: tools/pilot.py add %s %s <file> --rep %d"
          % (a.garment, e["shot_id"], e["rep"]))
    return OK


def _compare_set(spec, st_state, gdir, shot_id, rep, shot):
    """Captures this one must be compared against: every accepted frame, plus the previous repeat."""
    from denimtwin.pilot import qa_primitives as Q
    import cv2
    out = []
    for (sid, r), c in sorted(st_state["captures"].items()):
        if (sid, r) == (shot_id, rep):
            continue
        p = gdir / (c.get("path") or "")
        if not p.exists():
            continue
        img = cv2.imread(str(p))
        out.append({"shot_id": sid, "rep": r, "path": str(p), "sha256": c.get("sha256"),
                    "image": img, "pose": Q.garment_pose(img) if img is not None else None,
                    "exif_ts": c.get("exif_ts"),
                    "is_previous_rep": (sid == shot_id and r == rep - 1)})
    return out


def cmd_add(a):
    spec = load_spec()
    gdir = garment_dir(a.garment)
    st = Store(gdir)
    state, problems = st.fold()
    shots, _m = PLAN.activate(spec, state["features"], state["measurements"])
    by_id = {s["shot_id"]: s for s in shots}
    shot = by_id.get(a.shot)
    if shot is None:
        raise SystemExit("%s is not an activated shot for this garment. `plan` lists what is."
                         % a.shot)
    dest_dir = gdir / "images" / shot["state"]
    dest, sha, already = ingest_photo(a.file, dest_dir, a.shot, a.rep)
    rel = str(dest.relative_to(gdir))
    exif = read_exif(dest)
    ts = exif_timestamp(exif)
    import cv2
    img = cv2.imread(str(dest))
    h, w = (img.shape[:2] if img is not None else (None, None))
    st.append("capture", {"shot_id": a.shot, "rep": a.rep, "path": rel, "sha256": sha,
                          "exif": exif, "exif_ts": ts, "width": w, "height": h,
                          "state": shot["state"], "region_id": shot.get("region_id"),
                          "already_present": already},
              operator=a.operator, setup_hash=state["setup_hash"])
    b, bspec = board()
    quality = PLAN.__dict__ and QA.merged_quality(spec.doc["quality_defaults"], shot)
    cmp_ = _compare_set(spec, state, gdir, a.shot, a.rep, shot)
    for c in cmp_:
        c["self_sha256"] = sha
        c["this_exif_ts"] = ts
    assertions = {"operator": a.operator}
    for k in (a.confirm or []):
        assertions[k] = True
    checks = QA.check_capture(dest, shot, quality, board=b, board_spec=bspec, image=img,
                              compare_to=cmp_, operator_assertions=assertions)
    outcome = QA.roll_up(checks)
    st.append("qa_result", {"shot_id": a.shot, "rep": a.rep, "outcome": outcome,
                            "checks": [c.as_dict() for c in checks]}, operator=a.operator)
    print("%s r%d -> %s" % (a.shot, a.rep, outcome))
    print("  stored %s%s" % (rel, "  (already present, unchanged)" if already else ""))
    for c in checks:
        if c.outcome != QA.PASS:
            print("  %-22s %-28s %s" % (c.check_id, c.outcome, c.detail))
            if c.fix:
                print("  %-22s   fix: %s" % ("", c.fix))
    return OK if outcome == QA.PASS else FAIL


def cmd_confirm(a):
    st = Store(garment_dir(a.garment))
    if not a.operator:
        raise SystemExit("--operator is required: a human verification without a name is not one")
    st.append("human_verification",
              {"shot_id": a.shot, "rep": a.rep, "claim": a.claim, "value": not a.deny,
               "note": a.note, "verifier_name": a.verifier or a.operator,
               "measured_inseam_cm": a.measured_inseam, "measured_outseam_cm": a.measured_outseam},
              operator=a.operator)
    print("recorded: %s = %s by %s" % (a.claim, not a.deny, a.operator))
    return OK


def cmd_cutspec(a):
    st = Store(garment_dir(a.garment))
    state, _ = st.fold()
    m = state["measurements"]

    def need(k):
        v = (m.get(k) or {}).get("mean")
        if v is None:
            raise SystemExit("%s has not been measured; run `measure` first" % k)
        return v
    s = CUT.compute(target_inseam_cm=a.inseam, original_inseam_cm=need("original_inseam_cm"),
                    thigh_cm=need("thigh_cm"), leg_opening_cm=need("leg_opening_cm"))
    st.append("cut_spec", s, operator=a.operator)
    for line in CUT.packet_lines(a.garment, s):
        print(line)
    return OK


def cmd_packet(a):
    st = Store(garment_dir(a.garment))
    state, _ = st.fold()
    if not state["cut_spec"]:
        raise SystemExit("no cut has been specified; run `cutspec --inseam N` first")
    lines = CUT.packet_lines(a.garment, state["cut_spec"])
    text = "\n".join(lines) + "\n"
    if a.out:
        Path(a.out).write_text(text)
        print("wrote %s" % a.out)
    else:
        print(text)
    return OK


def _print_verdict(v):
    width = 66
    print("=" * width)
    head = "READY" if v.ready else "NOT READY"
    print("  %s -- %s" % (v.gate_id.replace("_", " ").upper(), head))
    print("=" * width)
    if v.ready:
        print("\n  %d conditions satisfied:\n" % len(v.satisfied))
        for s in v.satisfied:
            print("    OK   %-34s %s" % (s["condition"], s["what"]))
    else:
        print("\n  %d condition(s) block this, %d satisfied.\n"
              % (len(v.blocks), len(v.satisfied)))
        for b in v.blocks:
            print("    BLOCK  %s" % b.condition)
            print("           %s" % b.what)
            if b.fix:
                print("           -> %s" % b.fix)
            print("")
    return v


def cmd_precut(a):
    spec = load_spec()
    gdir = garment_dir(a.garment)
    v = GATES.evaluate("ready_to_cut", spec, Store(gdir), garment_dir=gdir,
                       check_files=not a.no_file_check)
    _print_verdict(v)
    if a.json:
        Path(a.json).write_text(json.dumps(v.as_dict(), indent=1) + "\n")
    if v.ready:
        print("\n  Every required photograph, measurement, calibration reading, hash, cut")
        print("  specification and human verification is present and valid. You may cut.\n")
        return OK
    unavail = any("could not be evaluated" in b.what for b in v.blocks)
    return UNAVAILABLE if unavail else FAIL


def cmd_gate(a):
    spec = load_spec()
    gdir = garment_dir(a.garment)
    v = GATES.evaluate(a.gate, spec, Store(gdir), garment_dir=gdir)
    _print_verdict(v)
    return OK if v.ready else FAIL


def cmd_hem(a):
    st = Store(garment_dir(a.garment))
    state, _ = st.fold()
    lo = (state["measurements"].get("leg_opening_cm") or {}).get("mean")
    if lo is None:
        raise SystemExit("leg_opening_cm has not been measured; the hem loop's length is unknown, "
                         "so its coverage cannot be computed. That is UNAVAILABLE, not complete.")
    done = st.done_keys()
    for leg in ("left", "right"):
        g = HEM.HemGeometry.from_leg_opening(leg, lo)
        captured = []
        for (sid, rep) in done:
            if ".HEM." in sid and leg.upper() in sid and ".MACRO." in sid:
                tail = sid.rsplit(".", 1)[-1]
                if tail.startswith("P") and tail[1:].isdigit():
                    captured.append(int(tail[1:]))
        cov = g.coverage(captured)
        print("%s leg: circumference %.0f mm, %d positions every %.0f mm, %d macros needed"
              % (leg, g.circumference_mm, cov["n_positions"], g.position_spacing_mm,
                 len(g.macros())))
        print("  covered %d/%d (%.0f%%)%s"
              % (cov["n_covered"], cov["n_positions"], 100 * cov["fraction"],
                 "" if cov["complete"] else "   GAPS at positions " +
                 ", ".join(str(i) for i in cov["gap_positions"][:12])))
        nxt = g.next_macro(captured)
        if nxt:
            print("  next macro: %s covering arc %.0f-%.0f mm (positions %s)"
                  % (nxt["shot_suffix"], nxt["usable_start_mm"], nxt["usable_end_mm"],
                     ", ".join(str(i) for i in nxt["supports_positions"])))
    return OK


def cmd_wash(a):
    st = Store(garment_dir(a.garment))
    state, _ = st.fold()
    which = "wash_actual" if a.actual else "wash_planned"
    if a.actual and not state["wash_planned"]:
        raise SystemExit("record the PLANNED wash first; actual settings never replace planned "
                         "ones, and a deviation is the difference between the two")
    rec = {}
    fields = [("machine", str, "washing machine make/model"), ("location", str, "location"),
              ("cycle", str, "cycle name"), ("water_temp_c", float, "water temperature, C"),
              ("spin_rpm", float, "spin, rpm"), ("detergent", str, "detergent brand"),
              ("detergent_ml", float, "detergent, ml"), ("filler_load", str, "filler load"),
              ("start_time", str, "start time (HH:MM)"), ("end_time", str, "end time (HH:MM)"),
              ("dryer_method", str, "dryer method (line/tumble/flat)"),
              ("dryer_setting", str, "dryer setting"), ("dryer_minutes", float, "dryer minutes"),
              ("conditioning_start", str, "conditioning start (HH:MM)"),
              ("conditioning_end", str, "conditioning end (HH:MM)"),
              ("garment_in_load", str, "which samples were in this load")]
    base = state["wash_planned"] or {}
    for key, cast, label in fields:
        rec[key] = _prompt("  %s" % label, base.get(key) if a.actual else None, cast)
    st.append(which, rec, operator=a.operator)
    if a.actual:
        d = diff_planned_actual(state["wash_planned"], rec)
        if d:
            print("\n%d deviation(s) from the plan -- recorded, not overwritten:" % len(d))
            for x in d:
                print("  %-20s planned %-16s actual %s" % (x["field"], x["planned"], x["actual"]))
            for x in d:
                st.append("deviation", {"kind": "wash", "field": x["field"],
                                        "planned": x["planned"], "actual": x["actual"]},
                          operator=a.operator)
        else:
            print("\nno deviation from the planned wash")
    return OK


def cmd_offcut(a):
    st = Store(garment_dir(a.garment))
    state, _ = st.fold()
    label = "%s_OFFCUT_%s" % (a.garment, a.leg.upper()[0])
    rec = {"label": label, "originating_leg": a.leg.lower()}
    if a.assign:
        rec["assigned_wash_condition"] = a.assign
    if a.actual_wash:
        rec["actual_wash_condition"] = a.actual_wash
    for k, v in (("length_cm", a.length), ("width_cm", a.width), ("mass_g", a.mass)):
        if v is not None:
            rec[("after_" if a.after_wash else "before_") + k] = v
    st.append("offcut", rec, operator=a.operator)
    print("recorded %s: %s" % (label, json.dumps({k: v for k, v in rec.items() if k != "label"})))
    return OK


def cmd_status(a):
    spec = load_spec()
    gdir = garment_dir(a.garment)
    st = Store(gdir)
    state, problems = st.fold()
    shots, meta = PLAN.activate(spec, state["features"], state["measurements"])
    ordered = PLAN.order(spec, shots)
    done = st.done_keys()
    print("%s   state=%s   spec=%s   rig=%s"
          % (a.garment, state["state"], (state["spec_hash"] or "-")[:12],
             (state["setup_hash"] or "-")[:12]))
    print("photographs: %s" % (gdir / "images"))
    if problems:
        print("\n!! the capture log reports %d integrity problem(s)" % len(problems))
        for p in problems[:4]:
            print("   %s: %s" % (p["kind"], p["detail"]))
    print("")
    by_state = {}
    for e in ordered:
        s = by_state.setdefault(e["state"], {"n": 0, "done": 0, "req": 0, "req_done": 0})
        s["n"] += 1
        d = (e["shot_id"], e["rep"]) in done
        s["done"] += d
        if e["necessity"] != "optional":
            s["req"] += 1
            s["req_done"] += d
    print("  %-18s %-16s %-16s %s" % ("state", "required", "all frames", "remaining"))
    for stn in [x["state"] for x in sorted(spec.states, key=lambda x: x["order"])]:
        s = by_state.get(stn)
        if not s:
            continue
        rem = [e for e in ordered if e["state"] == stn and (e["shot_id"], e["rep"]) not in done]
        print("  %-18s %4d/%-11d %4d/%-11d %s"
              % (stn, s["req_done"], s["req"], s["done"], s["n"],
                 _fmt_time(PLAN.estimate_seconds(spec, rem)) if rem else "done"))
    outcomes = {}
    for q in state["qa"].values():
        outcomes[q.get("outcome")] = outcomes.get(q.get("outcome"), 0) + 1
    if outcomes:
        print("\n  quality: " + "  ".join("%s=%d" % (k, v) for k, v in sorted(outcomes.items())))
    print("  measurements: %d/%d   deviations: %d   human verifications: %d"
          % (len(state["measurements"]), len(GATES.REQUIRED_MEASUREMENTS),
             len(state["deviations"]), len(state["verifications"])))
    v = GATES.evaluate("ready_to_cut", spec, st, garment_dir=gdir, check_files=False)
    print("\n  cut gate: %s%s" % ("READY" if v.ready else "NOT READY",
                                  "" if v.ready else "  (%d blocks; run `precut` for the list)"
                                  % len(v.blocks)))
    e = PLAN.next_action(spec, ordered, done)
    if e:
        print("  next: %s r%d -- %s" % (e["shot_id"], e["rep"], e["framing"][:70]))
    return OK


def cmd_serve(a):
    from denimtwin.pilot import webapp
    return webapp.run(root=ROOT, garments=GARMENTS, spec_path=SPEC_PATH, board_path=BOARD_PATH,
                      garment=a.garment, port=a.port, lan=a.lan, open_browser=not a.no_open)


def cmd_finalize(a):
    spec = load_spec()
    gdir = garment_dir(a.garment)
    st = Store(gdir)
    v = GATES.evaluate("ready_to_finalize", spec, st, garment_dir=gdir)
    _print_verdict(v)
    out = gdir / "pilot" / "manifest.sanitised.json"
    try:
        sanitised, problems = st.manifest.sanitised(ROOT)
    except Exception as e:
        print("\nrefusing to write the committable manifest: %s" % e)
        return FAIL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sanitised, indent=1, sort_keys=True) + "\n")
    print("\nwrote %s (%d entries, absolute paths and location EXIF removed)"
          % (out.relative_to(ROOT), len(sanitised)))
    return OK if v.ready else FAIL


def cmd_selftest(a):
    """Run the whole workflow against synthetic images in a temporary tree."""
    from denimtwin.pilot import selftest
    return selftest.run(verbose=a.verbose)


def main(argv=None):
    p = argparse.ArgumentParser(prog="pilot.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--operator", default=os.environ.get("PILOT_OPERATOR") or os.environ.get("USER"))
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, garment=True, **kw):
        s = sub.add_parser(name, help=(fn.__doc__ or "").strip().split("\n")[0], **kw)
        if garment:
            s.add_argument("garment")
        s.set_defaults(fn=fn)
        return s

    sub.add_parser("new", help="create the next garment and open a session").set_defaults(fn=cmd_new)
    s = add("setup", cmd_setup)
    s.add_argument("--reason", default=None)
    add("intake", cmd_intake)
    add("measure", cmd_measure)
    s = add("plan", cmd_plan)
    s.add_argument("--state", default=None)
    s = add("next", cmd_next)
    s.add_argument("--state", default=None)
    s = add("add", cmd_add)
    s.add_argument("shot")
    s.add_argument("file")
    s.add_argument("--rep", type=int, default=1)
    s.add_argument("--confirm", action="append",
                   help="record an operator assertion, e.g. --confirm ruler_visible")
    s = add("confirm", cmd_confirm)
    s.add_argument("claim")
    s.add_argument("--shot", default=None)
    s.add_argument("--rep", type=int, default=None)
    s.add_argument("--deny", action="store_true")
    s.add_argument("--note", default=None)
    s.add_argument("--verifier", default=None)
    s.add_argument("--measured-inseam", type=float, default=None, dest="measured_inseam")
    s.add_argument("--measured-outseam", type=float, default=None, dest="measured_outseam")
    s = add("cutspec", cmd_cutspec)
    s.add_argument("--inseam", type=float, required=True)
    s = add("packet", cmd_packet)
    s.add_argument("--out", default=None)
    s = add("precut", cmd_precut)
    s.add_argument("--json", default=None)
    s.add_argument("--no-file-check", action="store_true", dest="no_file_check")
    s = add("gate", cmd_gate)
    s.add_argument("gate", choices=sorted(GATES.GATE_STATES))
    add("hem", cmd_hem)
    s = add("wash", cmd_wash)
    s.add_argument("--actual", action="store_true")
    s = add("offcut", cmd_offcut)
    s.add_argument("leg", choices=["left", "right"])
    s.add_argument("--assign", default=None)
    s.add_argument("--actual-wash", default=None, dest="actual_wash")
    s.add_argument("--length", type=float, default=None)
    s.add_argument("--width", type=float, default=None)
    s.add_argument("--mass", type=float, default=None)
    s.add_argument("--after-wash", action="store_true", dest="after_wash")
    add("status", cmd_status)
    add("finalize", cmd_finalize)
    s = sub.add_parser("serve", help="run the phone-friendly local app")
    s.add_argument("garment", nargs="?", default=None)
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--lan", action="store_true",
                   help="also accept connections from the local network (token required)")
    s.add_argument("--no-open", action="store_true")
    s.set_defaults(fn=cmd_serve)
    s = sub.add_parser("selftest", help="run the whole workflow on synthetic images")
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(fn=cmd_selftest)

    a = p.parse_args(argv)
    return a.fn(a) or OK


if __name__ == "__main__":
    sys.exit(main())
