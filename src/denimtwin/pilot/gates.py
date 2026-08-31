"""The gate. It answers one question -- may this garment be cut? -- and it answers no by default.

Everything else in this package exists to make the evidence collectable. This module exists to make
the answer unfalsifiable, and it is written against a specific failure: a gate that lists the things
it happens to check, rather than the things the experiment requires, and therefore passes a garment
whose missing evidence nobody encoded.

Three design rules follow, and they are the whole of it.

DENY BY DEFAULT. A condition contributes to readiness only by returning a positive result. Absence
of a finding is never a finding. There is no code path that skips a condition and no code path that
treats an empty collection as a satisfied one -- an empty required-shot list is itself a block,
because a plan that requires nothing is a plan that was not generated.

THE REQUIRED SET IS ENUMERATED FROM THE SPECIFICATION, NOT FROM THIS FILE. The shots that must exist
come from the shot-plan document filtered by the answered features. So adding a shot to the
specification automatically extends the gate, and this module cannot fall behind the protocol. The
one thing this file does hold is which CLASSES of evidence are required, and each is a condition
that must actively pass.

AN ERROR IS A BLOCK. Every condition runs inside a guard, and a condition that raises becomes a
block naming the exception. A gate that crashes into a pass is the exact defect this repository
found in three of its own guards (see the commits around tools/verify.py); a condition this code
cannot evaluate is a condition whose truth is unknown, and unknown is not permission.

The verdict lists every unmet condition with the action that would satisfy it, because "not ready"
without "and here is what is missing" is a gate people learn to route around.
"""
import math
import os
from pathlib import Path

from . import plan as PLAN
from . import qa as QA

#: Measurements the protocol requires before a garment may be cut, and how many independent readings
#: each needs. PROTOCOL.md 0.4 fixes two readings for the tape measurements and three spots for
#: thickness; they are listed here because the gate must enumerate them, and mirrored in the runbook.
REQUIRED_MEASUREMENTS = {
    "waist_cm": 2, "front_rise_cm": 2, "back_rise_cm": 2, "thigh_cm": 2,
    "original_inseam_cm": 2, "leg_opening_cm": 2, "fabric_thickness_mm": 3, "mass_grams": 1,
}
#: Two readings of the same dimension that disagree by more than this were not both measurements of
#: it. Tape measurements on cloth: 0.5 cm is about what a careful person reproduces on a flat-laid
#: garment; thickness with a caliper is finer.
MEASUREMENT_TOLERANCE = {"fabric_thickness_mm": 0.15, "mass_grams": 2.0, "_default_cm": 0.5}

#: Rig calibration readings that must exist and pass before any garment capture counts.
REQUIRED_SETUP_CHECKS = (
    "empty_backdrop", "board_verification", "board_square_measured", "lighting_test",
    "exposure_white_balance", "camera_height", "lens_selection", "backdrop_identified",
    "daylight_controlled", "board_garment_coplanar",
)
#: The printed board's squares, and how far off the print may be before the scale is wrong.
#: protocol/charuco_board.json declares 25.0 mm; a 0.5 mm error over one square is 2%, which is the
#: same order as the tilt bias EXP_0043 measured, so it is not a detail.
BOARD_SQUARE_MM = 25.0
BOARD_SQUARE_TOLERANCE_MM = 0.5

#: Second-person verification of the cut marks. PROTOCOL.md 3.2 sets this.
CUT_MARK_TOLERANCE_MM = 3.0


class Block(object):
    __slots__ = ("condition", "what", "fix", "evidence")

    def __init__(self, condition, what, fix, evidence=None):
        self.condition = condition
        self.what = what
        self.fix = fix
        self.evidence = evidence or {}

    def as_dict(self):
        return {"condition": self.condition, "what": self.what, "fix": self.fix,
                "evidence": self.evidence}

    def __repr__(self):
        return "<Block %s: %s>" % (self.condition, self.what)


class Verdict(object):
    def __init__(self, gate_id, blocks, satisfied, evidence=None):
        self.gate_id = gate_id
        self.blocks = blocks
        self.satisfied = satisfied
        self.evidence = evidence or {}

    @property
    def ready(self):
        return not self.blocks

    def as_dict(self):
        return {"gate": self.gate_id, "ready": self.ready,
                "blocks": [b.as_dict() for b in self.blocks],
                "satisfied": self.satisfied, "evidence": self.evidence}

    def __repr__(self):
        return "<Verdict %s ready=%s blocks=%d>" % (self.gate_id, self.ready, len(self.blocks))


def _guard(blocks, satisfied, condition, fn):
    """Run one condition. Anything other than an explicit pass is a block, exceptions included."""
    try:
        ok, what, fix, ev = fn()
    except Exception as e:                     # noqa: BLE001 -- deliberately broad; see module docs
        blocks.append(Block(condition,
                            "this condition could not be evaluated: %s: %s"
                            % (type(e).__name__, e),
                            "fix the error above, then re-run the gate. A condition whose truth is "
                            "unknown is not permission.",
                            {"exception": type(e).__name__}))
        return
    if ok:
        satisfied.append({"condition": condition, "what": what, "evidence": ev or {}})
    else:
        blocks.append(Block(condition, what, fix, ev))


#: Which states' captures must be complete before each gate opens.
GATE_STATES = {
    "ready_to_cut": ("rig", "intake", "before", "marked"),
    "ready_to_wash": ("rig", "intake", "before", "marked", "immediate_after"),
    "ready_to_finalize": ("rig", "intake", "before", "marked", "immediate_after", "post_wash"),
}


def evaluate(gate_id, spec, store, *, garment_dir=None, check_files=True):
    """Evaluate one gate. Returns a Verdict. Never raises for a data problem -- that is a block."""
    if gate_id not in GATE_STATES:
        raise ValueError("unknown gate %r" % gate_id)
    blocks, satisfied = [], []
    state, problems = store.fold()
    garment_dir = Path(garment_dir or store.dir)
    states = GATE_STATES[gate_id]

    # --- the plan itself ------------------------------------------------------------------
    activated = None
    try:
        activated, meta = PLAN.activate(spec, state["features"])
    except Exception as e:
        blocks.append(Block("plan.generated",
                            "no shot plan could be generated: %s" % e,
                            "answer the intake questionnaire (`pilot.py intake`)"))
        meta = {"features": state["features"], "assumed_present": [], "unevaluatable_conditions": []}

    def required_here():
        if activated is None:
            raise RuntimeError("no plan")
        req = [s for s in activated
               if s["state"] in states and s["necessity"] in ("required", "conditional")]
        if not req:
            raise RuntimeError("the plan requires no shots in states %s, which means it was not "
                               "generated rather than that nothing is needed" % (states,))
        return req

    # --- specification binding ------------------------------------------------------------
    def c_spec_bound():
        if not state["spec_hash"]:
            return False, "this session never recorded which shot plan it was opened under", \
                   "run `pilot.py new` / `pilot.py open` to bind the session to a specification", {}
        if state["spec_hash"] != spec.content_hash:
            return False, ("the session was opened under shot plan %s but the specification on disk "
                           "now hashes to %s -- the plan changed underneath the evidence"
                           % (state["spec_hash"][:12], spec.content_hash[:12])), \
                   "re-run the gate against the specification version the session used, or " \
                   "re-validate every capture against the new plan", \
                   {"session": state["spec_hash"], "on_disk": spec.content_hash}
        return True, "bound to shot plan %s v%s" % (spec.content_hash[:12], spec.version), None, {}

    _guard(blocks, satisfied, "spec.bound", c_spec_bound)

    # --- log integrity --------------------------------------------------------------------
    def c_log_intact():
        if problems:
            return False, ("the capture log does not verify: %s"
                           % "; ".join("%s at line/seq %s" % (p["kind"], p.get("line_no", p.get("seq")))
                                       for p in problems[:4])), \
                   "the log has been edited, truncated or damaged. Do not cut. Recover from the " \
                   "phone's own copies and re-ingest.", {"problems": problems[:8]}
        if state["unknown_kinds"]:
            return False, "the log contains entries this version cannot interpret", \
                   "upgrade the tool to the version that wrote this log", \
                   {"unknown": state["unknown_kinds"][:5]}
        return True, "log verifies: %d entries, hash chain intact" % state["n_entries"], None, {}

    _guard(blocks, satisfied, "log.intact", c_log_intact)

    # --- features -------------------------------------------------------------------------
    def c_features():
        if not state["features"]:
            return False, "the garment feature questionnaire has not been answered", \
                   "run `pilot.py intake`", {}
        missing_absent = []
        for f in spec.features:
            if f["key"] in state["features"] and state["features"][f["key"]] is not None:
                continue
            if f["unanswered_means"] == "absent":
                # This is the dangerous direction: an unanswered question that defaults to absent
                # silently deletes the shots it gates, so it must be answered explicitly.
                missing_absent.append(f["key"])
        if missing_absent:
            return False, ("%d question(s) whose silence would DROP a required capture are still "
                           "unanswered: %s" % (len(missing_absent), ", ".join(sorted(missing_absent)[:8]))), \
                   "answer them in `pilot.py intake`; an unanswered question that defaults to " \
                   "'absent' would remove a photograph from the plan", {"keys": missing_absent}
        return True, "%d feature answers recorded (%d assumed present pending answer)" % (
            len(state["features"]), len(meta.get("assumed_present") or [])), None, \
            {"assumed_present": meta.get("assumed_present") or []}

    _guard(blocks, satisfied, "features.answered", c_features)

    # --- rig ------------------------------------------------------------------------------
    def c_setup_frozen():
        if not state["setup_hash"]:
            return False, "the rig configuration has not been frozen", \
                   "run `pilot.py setup` and freeze it", {}
        return True, "rig frozen as %s" % state["setup_hash"][:12], None, \
               {"setup_hash": state["setup_hash"], "changes": len(state["setup_history"])}

    def c_setup_checks():
        have = state["setup_checks"]
        missing = [c for c in REQUIRED_SETUP_CHECKS if c not in have]
        failed = [c for c, v in have.items() if v.get("outcome") not in (None, QA.PASS)]
        if missing or failed:
            return False, ("rig calibration incomplete: %d missing (%s), %d not passing (%s)"
                           % (len(missing), ", ".join(missing[:6]) or "-",
                              len(failed), ", ".join(failed[:4]) or "-")), \
                   "run `pilot.py setup` and complete every calibration reading", \
                   {"missing": missing, "failed": failed}
        return True, "all %d rig calibration checks recorded and passing" % len(REQUIRED_SETUP_CHECKS), \
               None, {}

    def c_board_square():
        m = state["setup_checks"].get("board_square_measured") or {}
        v = m.get("measured_mm")
        n = m.get("squares_spanned")
        if v is None or n in (None, 0):
            return False, "the printed board's square size has not been measured", \
                   "measure a run of squares with a steel rule and record it in `pilot.py setup`", {}
        per = float(v) / float(n)
        off = abs(per - BOARD_SQUARE_MM)
        if off > BOARD_SQUARE_TOLERANCE_MM:
            return False, ("the printed squares measure %.2f mm, not %.1f mm (%.2f mm out) -- every "
                           "scale derived from this board would carry that error"
                           % (per, BOARD_SQUARE_MM, off)), \
                   "reprint the board at 100%% scale (no 'fit to page') and measure again", \
                   {"measured_mm_per_square": per}
        return True, "printed squares measure %.2f mm across %s squares" % (per, n), None, \
               {"mm_per_square": per}

    def c_captures_carry_setup():
        known = {h["setup_hash"] for h in state["setup_history"] if h.get("setup_hash")}
        bad = [k for k, c in state["captures"].items()
               if not c.get("setup_hash") or c["setup_hash"] not in known]
        if bad:
            return False, ("%d capture(s) are not attributable to a frozen rig configuration"
                           % len(bad)), \
                   "these were taken before the rig was frozen, or under a configuration that was " \
                   "never recorded. Re-take them, or record the configuration they were taken " \
                   "under as a deviation.", \
                   {"examples": ["%s r%d" % (s, r) for s, r in sorted(bad)[:6]]}
        return True, "all %d captures carry a known rig hash" % len(state["captures"]), None, {}

    _guard(blocks, satisfied, "rig.frozen", c_setup_frozen)
    _guard(blocks, satisfied, "rig.calibrated", c_setup_checks)
    _guard(blocks, satisfied, "rig.board_square_measured", c_board_square)
    _guard(blocks, satisfied, "rig.captures_attributable", c_captures_carry_setup)

    # --- measurements ---------------------------------------------------------------------
    def c_measurements():
        missing, thin, inconsistent = [], [], []
        for name, n_required in sorted(REQUIRED_MEASUREMENTS.items()):
            m = state["measurements"].get(name)
            if not m:
                missing.append(name)
                continue
            readings = [r for r in (m.get("readings") or []) if r is not None]
            if len(readings) < n_required:
                thin.append("%s (%d of %d readings)" % (name, len(readings), n_required))
                continue
            tol = MEASUREMENT_TOLERANCE.get(name, MEASUREMENT_TOLERANCE["_default_cm"])
            spread = max(readings) - min(readings)
            if spread > tol:
                inconsistent.append("%s (readings differ by %.2f, tolerance %.2f)"
                                    % (name, spread, tol))
        if missing or thin or inconsistent:
            parts = []
            if missing:
                parts.append("%d not measured (%s)" % (len(missing), ", ".join(missing)))
            if thin:
                parts.append("%d with too few readings (%s)" % (len(thin), "; ".join(thin)))
            if inconsistent:
                parts.append("%d whose readings disagree (%s)"
                             % (len(inconsistent), "; ".join(inconsistent)))
            return False, "measurements incomplete: " + "; ".join(parts), \
                   "run `pilot.py measure`; each dimension needs its readings taken independently, " \
                   "not copied", {"missing": missing, "thin": thin, "inconsistent": inconsistent}
        return True, "all %d required measurements recorded with independent readings in tolerance" \
               % len(REQUIRED_MEASUREMENTS), None, {}

    _guard(blocks, satisfied, "measurements.complete", c_measurements)

    # --- captures -------------------------------------------------------------------------
    def c_required_captures():
        req = required_here()
        done = store.done_keys()
        missing, failing, unresolved = [], [], []
        for s in req:
            for rep in range(1, int(s.get("min_reps", 1)) + 1):
                key = (s["shot_id"], rep)
                if key not in done:
                    missing.append("%s r%d" % key)
                    continue
                q = state["qa"].get(key)
                if not q:
                    unresolved.append("%s r%d (never checked)" % key)
                    continue
                out = q.get("outcome")
                if out == QA.PASS:
                    continue
                if out == QA.HUMAN:
                    if not _human_resolved(state, s["shot_id"], rep, q):
                        unresolved.append("%s r%d (awaiting human verification)" % key)
                    continue
                failing.append("%s r%d (%s)" % (key[0], key[1], out))
        if missing or failing or unresolved:
            return False, ("required captures incomplete: %d missing, %d failing, %d unresolved "
                           "(of %d required frames)"
                           % (len(missing), len(failing), len(unresolved),
                              sum(int(s.get("min_reps", 1)) for s in req))), \
                   "the app's next action names the first of these; work through them", \
                   {"missing": missing[:12], "failing": failing[:12], "unresolved": unresolved[:12],
                    "n_missing": len(missing), "n_failing": len(failing),
                    "n_unresolved": len(unresolved)}
        return True, "all %d required frames captured and passing" % \
               sum(int(s.get("min_reps", 1)) for s in req), None, {}

    def c_files_present():
        if not check_files:
            return False, "file integrity was not checked", \
                   "re-run without --no-file-check", {}
        missing, changed = [], []
        for (sid, rep), c in sorted(state["captures"].items()):
            rel = c.get("path")
            if not rel:
                missing.append("%s r%d (no path)" % (sid, rep))
                continue
            p = garment_dir / rel
            if not p.exists():
                missing.append("%s r%d -> %s" % (sid, rep, rel))
                continue
            want = c.get("sha256")
            if want:
                from .manifest import sha256_file
                if sha256_file(p) != want:
                    changed.append("%s r%d -> %s" % (sid, rep, rel))
        if missing or changed:
            return False, ("%d recorded photograph(s) are missing from disk and %d no longer match "
                           "the hash recorded for them" % (len(missing), len(changed))), \
                   "restore them from the phone, or re-capture. A manifest entry whose file is " \
                   "gone is not evidence.", {"missing": missing[:8], "changed": changed[:8]}
        return True, "all %d recorded photographs present and hash-matched" % len(state["captures"]), \
               None, {}

    _guard(blocks, satisfied, "captures.required_complete", c_required_captures)
    _guard(blocks, satisfied, "captures.files_intact", c_files_present)

    def c_relays():
        req = required_here()
        need = [s for s in req if s.get("relay_between_reps") and int(s.get("min_reps", 1)) > 1]
        bad = []
        for s in need:
            for rep in range(2, int(s["min_reps"]) + 1):
                q = state["qa"].get((s["shot_id"], rep)) or {}
                rc = None
                for c in (q.get("checks") or []):
                    if c.get("check_id") == "relay_independence":
                        rc = c
                if rc is None:
                    bad.append("%s r%d (relay independence never assessed)" % (s["shot_id"], rep))
                elif rc.get("outcome") != QA.PASS:
                    bad.append("%s r%d (%s)" % (s["shot_id"], rep, rc.get("outcome")))
        if bad:
            return False, ("%d repeat capture(s) are not established as independent re-lays"
                           % len(bad)), \
                   "each repeat must follow the garment being lifted clear and laid out again; " \
                   "confirm the re-lay in the app or re-take the repeat", {"failing": bad[:10]}
        return True, "%d repeat capture(s) established as independent re-lays" % \
               sum(int(s["min_reps"]) - 1 for s in need), None, {}

    _guard(blocks, satisfied, "captures.relays_independent", c_relays)

    def c_reuse_legitimate():
        bad = []
        for r in state["reuse"]:
            if not r.get("source_shot_id") or not r.get("checks_rerun"):
                bad.append(r.get("shot_id"))
                continue
            if r.get("outcome") != QA.PASS:
                bad.append(r.get("shot_id"))
        if bad:
            return False, ("%d image reuse declaration(s) do not record that the borrowed image was "
                           "re-checked against the borrowing shot's own requirements" % len(bad)), \
                   "an image may satisfy a second shot only when every requirement of that shot " \
                   "passes on it; re-run the check or capture the shot properly", {"shots": bad[:8]}
        return True, "%d image reuse declaration(s), each re-checked" % len(state["reuse"]), None, {}

    _guard(blocks, satisfied, "captures.reuse_legitimate", c_reuse_legitimate)

    # --- the cut itself -------------------------------------------------------------------
    if gate_id == "ready_to_cut":
        def c_cut_spec():
            cs = state["cut_spec"]
            if not cs:
                return False, "no cut has been specified", \
                       "run `pilot.py cutspec` to define the target inseam and generate the " \
                       "digital cut line and its predicted outseam offset", {}
            need = ("target_inseam_cm", "predicted_outseam_cm", "cut_path_frame", "cut_angle_deg")
            gaps = [k for k in need if cs.get(k) is None]
            if gaps:
                return False, "the cut specification is missing %s" % ", ".join(gaps), \
                       "re-run `pilot.py cutspec`", {"missing": gaps}
            return True, "cut specified: inseam %.1f cm, predicted outseam %.1f cm" % (
                float(cs["target_inseam_cm"]), float(cs["predicted_outseam_cm"])), None, \
                {"cut_spec": {k: cs.get(k) for k in need}}

        def c_second_person():
            v = None
            for (sid, rep, claim), rec in state["verifications"].items():
                if claim == "cut_marks_verified":
                    v = rec
            if not v:
                return False, "no second person has verified the cut marks", \
                       "a second person measures both marks with a tape and records the reading; " \
                       "PROTOCOL.md 3.2 requires it before cutting", {}
            for k in ("verifier_name", "measured_inseam_cm", "measured_outseam_cm"):
                if not v.get(k):
                    return False, "the second-person verification is missing %s" % k, \
                           "re-record the verification with all fields", {"have": sorted(v.keys())}
            cs = state["cut_spec"] or {}
            errs = {}
            for field, target in (("measured_inseam_cm", cs.get("target_inseam_cm")),
                                  ("measured_outseam_cm", cs.get("predicted_outseam_cm"))):
                if target is None:
                    return False, "cannot check the verification against a cut spec that is absent", \
                           "run `pilot.py cutspec` first", {}
                errs[field] = abs(float(v[field]) - float(target)) * 10.0     # cm -> mm
            worst = max(errs.values())
            if worst > CUT_MARK_TOLERANCE_MM:
                return False, ("the second person's measurements differ from the specified cut by "
                               "%.1f mm, beyond the %.1f mm tolerance"
                               % (worst, CUT_MARK_TOLERANCE_MM)), \
                       "re-mark the garment and verify again", {"errors_mm": errs}
            return True, "%s verified both marks within %.1f mm" % (v["verifier_name"], worst), \
                   None, {"errors_mm": errs, "verifier": v["verifier_name"], "at": v.get("ts")}

        def c_cut_confirmations():
            need = {"legs_cut_separately": "confirm the legs will be cut one at a time",
                    "offcuts_retained_labelled": "confirm both offcuts will be kept and labelled "
                                                 "<GARMENT>_OFFCUT_L / _R"}
            missing = []
            for claim, how in need.items():
                found = any(c == claim and rec.get("value") is True
                            for (_, _, c), rec in state["verifications"].items())
                if not found:
                    missing.append((claim, how))
            if missing:
                return False, "%d cut-day confirmation(s) not recorded: %s" % (
                    len(missing), ", ".join(c for c, _ in missing)), \
                    "; ".join(h for _, h in missing), {"missing": [c for c, _ in missing]}
            return True, "cut-day confirmations recorded", None, {}

        _guard(blocks, satisfied, "cut.specified", c_cut_spec)
        _guard(blocks, satisfied, "cut.second_person_verified", c_second_person)
        _guard(blocks, satisfied, "cut.confirmations", c_cut_confirmations)

    ev = {"n_captures": len(state["captures"]), "n_required": None,
          "features": len(state["features"]), "states_covered": list(states),
          "deviations": len(state["deviations"])}
    if activated is not None:
        ev["n_required"] = sum(int(s.get("min_reps", 1)) for s in activated
                               if s["state"] in states and s["necessity"] != "optional")
    return Verdict(gate_id, blocks, satisfied, ev)


def _human_resolved(state, shot_id, rep, qa_record):
    """A HUMAN outcome counts only when every claim it raised has a recorded verification.

    Not "someone clicked ok once" -- each check that asked for a person names a claim, and each
    claim needs its own answer, recorded with who gave it. Otherwise one confirmation would clear a
    frame that raised three separate questions.
    """
    claims = [c.get("check_id") for c in (qa_record.get("checks") or [])
              if c.get("outcome") == QA.HUMAN]
    if not claims:
        return False
    for claim in claims:
        rec = state["verifications"].get((shot_id, rep, claim))
        if not rec or rec.get("value") is not True or not rec.get("operator"):
            return False
    return True
