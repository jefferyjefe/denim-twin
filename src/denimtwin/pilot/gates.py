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

#: Plausible ranges for an adult pair of jeans, as the conventions in record.json define them --
#: waist, thigh and leg opening are FULL circumferences (measured flat and doubled).
#:
#: Agreement between two readings is not enough on its own, and leg_opening_cm shows why: it is the
#: measurement that SIZES a required series (the hem macro count comes from it) and PLACES the cut
#: (the outseam offset is computed from it). An operator reading the tape in inches records two
#: readings that agree perfectly with each other and are 2.5x wrong, which halves the fray series
#: and moves the cut mark by centimetres -- and every other check passes, because everything
#: downstream believes the number.
MEASUREMENT_RANGE = {
    "waist_cm": (55.0, 150.0),
    "front_rise_cm": (15.0, 45.0),
    "back_rise_cm": (20.0, 55.0),
    "thigh_cm": (35.0, 95.0),
    "original_inseam_cm": (50.0, 105.0),
    "leg_opening_cm": (20.0, 80.0),
    "fabric_thickness_mm": (0.3, 3.0),
    "mass_grams": (200.0, 1400.0),
}

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
#: A steel rule reads to about 0.5 mm. Over one 25 mm square that is a 2% measurement, which is
#: worse than the scale error the tilt gate is set to catch; over eight squares it is 0.25%.
MIN_BOARD_SQUARES_SPANNED = 4
#: The board is 8 x 11 squares (protocol/charuco_board.json), so a run cannot exceed 11.
BOARD_MAX_SQUARES = 11

#: Every field the wash record carries, planned and actual alike. PROTOCOL.md 4 fixes the cycle.
WASH_FIELDS = ("machine", "location", "cycle", "water_temp_c", "spin_rpm", "detergent",
               "detergent_ml", "filler_load", "start_time", "end_time", "dryer_method",
               "dryer_setting", "dryer_minutes", "conditioning_start", "conditioning_end")

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


#: The LAST state each gate is responsible for. Everything at or below it in the specification's own
#: ordering is required.
#:
#: The states were listed by hand before, and the list fell behind the plan: the specification
#: declares eight states and the three tuples between them named six. offcut_before and
#: offcut_after appeared in none, so a hundred required frames -- a fifth of the plan, and the whole
#: offcut experiment -- were required by no gate at all. Deriving the set means adding a state to
#: the document cannot leave it unguarded.
GATE_LAST_STATE = {
    "ready_to_cut": "marked",
    "ready_to_wash": "offcut_before",
    "ready_to_finalize": "offcut_after",
}


def gate_states(spec, gate_id):
    """Every state at or below the one this gate guards, in the specification's own order."""
    order = {st["state"]: st["order"] for st in spec.states}
    last = GATE_LAST_STATE[gate_id]
    if last not in order:
        raise ValueError("the specification declares no state %r, which %s guards"
                         % (last, gate_id))
    cutoff = order[last]
    return tuple(st["state"] for st in sorted(spec.states, key=lambda x: x["order"])
                 if st["order"] <= cutoff)


def evaluate(gate_id, spec, store, *, garment_dir=None, check_files=True, rehash=False):
    """Evaluate one gate. Returns a Verdict. Never raises for a data problem -- that is a block."""
    if gate_id not in GATE_LAST_STATE:
        raise ValueError("unknown gate %r" % gate_id)
    blocks, satisfied = [], []
    # "AN ERROR IS A BLOCK" is this module's rule, and its own first line broke it: the fold ran
    # above every guard, so anything the log or the replay raised escaped the gate entirely and
    # returned a traceback instead of a verdict. A gate that cannot answer must still answer no.
    try:
        state, problems = store.fold()
    except Exception as e:                     # noqa: BLE001
        return Verdict(gate_id, [Block("log.readable",
                                       "the capture log could not be read at all: %s: %s"
                                       % (type(e).__name__, e),
                                       "the log is damaged beyond replay. Do not cut. Recover from "
                                       "the phone's own copies and re-ingest; a log this code "
                                       "cannot read is not evidence.",
                                       {"exception": type(e).__name__})], [],
                       {"fold_failed": True})
    garment_dir = Path(garment_dir or store.dir)
    states = gate_states(spec, gate_id)

    # --- the plan itself ------------------------------------------------------------------
    # Screen the measurements the plan is SIZED from before handing them to it. A leg opening of
    # 10^7 is refused by c_measurements, but c_measurements runs after the plan does, and expanding
    # a hem series from it builds millions of frames first -- the gate never reaches the condition
    # that would have refused the number.
    safe_measurements = {}
    for name, m in (state["measurements"] or {}).items():
        lo_hi = MEASUREMENT_RANGE.get(name)
        val = None
        try:
            from .store import mean_of
            val = mean_of(m)
        except Exception:                       # noqa: BLE001
            val = None
        if lo_hi and (val is None or not (lo_hi[0] <= val <= lo_hi[1])):
            continue                            # c_measurements reports it; the plan never sees it
        safe_measurements[name] = m

    activated = None
    try:
        activated, meta = PLAN.activate(spec, state["features"], safe_measurements,
                                        state.get("cut_spec"))
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
        shrinking = []
        for ch in state["feature_changes"]:
            was, now = ch["was"], ch["now"]
            try:
                shrank = (was is True and now is False) or \
                         (not isinstance(was, bool) and not isinstance(now, bool)
                          and float(now) < float(was))
            except (TypeError, ValueError):
                shrank = True
            if shrank:
                shrinking.append("%s: %r -> %r" % (ch["key"], was, now))
        excused_keys = {d.get("field") for d in state["deviations"]
                        if d.get("kind") == "intake"}
        shrinking = [x for x in shrinking if x.split(":")[0] not in excused_keys]
        if shrinking:
            # The newest answer wins and the older one stays in the log, invisible to every
            # condition -- so a later answer could delete the frames an earlier one required with
            # nothing to look at. An answer that ADDS work needs no explanation; one that removes
            # a photograph does.
            return False, ("%d intake answer(s) were later changed in the direction that REMOVES "
                           "required photographs: %s"
                           % (len(shrinking), "; ".join(shrinking[:5]))), \
                   "an answer that adds work needs no explanation; one that deletes a required " \
                   "frame does. Record why with `pilot.py deviation --kind intake`, or restore " \
                   "the earlier answer.", {"changes": shrinking[:8]}
        return True, "%d feature answers recorded (%d assumed present pending answer)" % (
            len(state["features"]), len(meta.get("assumed_present") or [])), None, \
            {"assumed_present": meta.get("assumed_present") or []}

    _guard(blocks, satisfied, "features.answered", c_features)

    def c_plan_expanded():
        stuck = (meta.get("expansion_blocked") or []) if isinstance(meta, dict) else []
        if stuck:
            return False, ("%d templated shot series could not be expanded into frames: %s"
                           % (len(stuck), "; ".join("%s (%s)" % (x["shot_id"], x["why"])
                                                    for x in stuck[:3]))), \
                   "supply the measurement the series is sized from, then re-run. An unexpanded " \
                   "series is not an empty requirement -- it is an unknown one.", \
                   {"blocked": stuck[:8]}
        return True, "every templated series expanded into frames", None, {}

    _guard(blocks, satisfied, "plan.fully_expanded", c_plan_expanded)

    # --- rig ------------------------------------------------------------------------------
    def c_setup_frozen():
        if not state["setup_hash"]:
            return False, "the rig configuration has not been frozen", \
                   "run `pilot.py setup` and freeze it", {}
        return True, "rig frozen as %s" % state["setup_hash"][:12], None, \
               {"setup_hash": state["setup_hash"], "changes": len(state["setup_history"])}

    def c_setup_checks():
        # Only readings taken against the CURRENT rig count. Keyed on the check name alone, a
        # re-freeze inherited the previous configuration's calibration wholesale -- so the rig could
        # be moved and every reading about the old one still read as certifying the new.
        cur = state["setup_hash"]
        # A reading that does not say which rig it was taken against has not established anything
        # about the current one. Admitting None was an escape hatch that re-opened exactly the hole
        # the keying closed.
        have = {k: v for k, v in state["setup_checks"].items()
                if v.get("setup_hash") == cur} if cur else {}
        missing = [c for c in REQUIRED_SETUP_CHECKS if c not in have]
        # An explicit PASS, or nothing. `not in (None, QA.PASS)` treated a reading with NO outcome
        # at all as satisfied, so a calibration record posted with the check's name and no verdict
        # counted as a passing calibration -- absence wearing the costume of a result, in the one
        # place the whole session's scale comes from.
        failed = [c for c in REQUIRED_SETUP_CHECKS
                  if c in have and have[c].get("outcome") != QA.PASS]
        unknown = [c for c in have if c not in REQUIRED_SETUP_CHECKS]
        if missing or failed:
            return False, ("rig calibration incomplete: %d missing (%s), %d recorded without an "
                           "explicit pass (%s)"
                           % (len(missing), ", ".join(missing[:6]) or "-",
                              len(failed), ", ".join(failed[:4]) or "-")), \
                   "run `pilot.py setup` and complete every calibration reading", \
                   {"missing": missing, "failed": failed, "unrecognised": unknown[:6]}
        return True, "all %d rig calibration checks recorded and passing" % len(REQUIRED_SETUP_CHECKS), \
               None, {"unrecognised": unknown[:6]}

    def c_board_square():
        m = state["setup_checks"].get("board_square_measured") or {}
        if state["setup_hash"] and m.get("setup_hash") != state["setup_hash"]:
            return False, ("the board-square measurement was taken against rig %s, not the one in "
                           "effect (%s)" % (str(m.get("setup_hash"))[:8],
                                            str(state["setup_hash"])[:8])), \
                   "re-measure the board against the current rig", {}
        v = m.get("measured_mm")
        n = m.get("squares_spanned")
        if v is None or n in (None, 0):
            return False, "the printed board's square size has not been measured", \
                   "measure a run of squares with a steel rule and record it in `pilot.py setup`", {}
        # It is a quotient of two numbers a person typed, and only the quotient was checked. A
        # single square spanned, a fractional count, a negative length -- all divided to something
        # near 25 and passed. A one-square measurement is also below what a steel rule resolves:
        # 0.5 mm read over 25 mm is 2%, and over 200 mm it is 0.25%.
        try:
            v, n = float(v), float(n)
        except (TypeError, ValueError):
            return False, "the board-square measurement is not numeric", "re-record it", {}
        if not (math.isfinite(v) and math.isfinite(n)):
            return False, "the board-square measurement is not a finite number", "re-record it", {}
        if n != int(n) or n < MIN_BOARD_SQUARES_SPANNED:
            return False, ("the board-square measurement spans %g squares; measure a run of at "
                           "least %d whole squares, because a rule read to 0.5 mm over one 25 mm "
                           "square is a 2%% measurement"
                           % (n, MIN_BOARD_SQUARES_SPANNED)), \
                   ("span at least %d whole squares with the rule and record the total"
                    % MIN_BOARD_SQUARES_SPANNED), {"squares_spanned": n}
        if n > BOARD_MAX_SQUARES:
            return False, ("the measurement claims %g squares, but the board only has %d in its "
                           "longest direction" % (n, BOARD_MAX_SQUARES)), \
                   "re-count the squares the rule spans", {"squares_spanned": n}
        if v <= 0:
            return False, "the measured length is not positive", "re-measure", {"measured_mm": v}
        per = v / n
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
        # Set membership was not enough. `known` was every rig hash appearing ANYWHERE in the log,
        # so a photograph taken (or back-dated) a week before the rig was frozen became attributable
        # to a configuration that did not exist when it was taken -- attribution by coincidence of
        # spelling. Resolve each capture against the freeze IN EFFECT AT ITS OWN POSITION in the log.
        freezes = sorted(((h.get("seq"), h.get("setup_hash")) for h in state["setup_history"]
                          if h.get("setup_hash")), key=lambda x: (x[0] is None, x[0]))
        bad, premature = [], []
        for k, c in sorted(state["captures"].items()):
            h = c.get("setup_hash")
            seq = c.get("seq")
            if not h:
                bad.append("%s r%d (no rig hash)" % k)
                continue
            in_effect = None
            for fseq, fh in freezes:
                if fseq is None or seq is None or fseq < seq:
                    in_effect = fh
            if in_effect is None:
                premature.append("%s r%d" % k)
            elif h != in_effect:
                premature.append("%s r%d (cites %s, rig in effect was %s)"
                                 % (k[0], k[1], str(h)[:8], str(in_effect)[:8]))
        if bad or premature:
            return False, ("%d capture(s) carry no rig hash and %d cite a configuration that was "
                           "not the one in effect when they were taken"
                           % (len(bad), len(premature))), \
                   "these were taken before the rig was frozen, or under a configuration recorded " \
                   "later. Re-take them, or record the configuration they were taken under as a " \
                   "deviation.", {"no_hash": bad[:6], "wrong_rig": premature[:6]}
        return True, "all %d captures carry the rig hash in effect when they were taken" \
               % len(state["captures"]), None, {}

    def c_one_rig():
        """The gated states must have been captured under ONE rig, or the change must be recorded.

        The rig could be re-frozen mid-session: half the captures under one configuration and half
        under another, the calibration never re-run against the new one, and nothing saying the
        camera had moved. Every capture was individually 'attributable', and the session as a whole
        described two rigs.
        """
        # Resolved from the PLAN, not from the capture's own claim about itself. Reading the
        # self-reported state let a frame mislabel itself out of this condition while still counting
        # as evidence for the condition next door.
        in_scope = {(sh["shot_id"], rep) for sh in required_here()
                    for rep in range(1, int(sh.get("min_reps", 1)) + 1)}
        used = {}
        for k, c in state["captures"].items():
            if k in in_scope and c.get("setup_hash"):
                used.setdefault(c["setup_hash"], []).append("%s r%d" % k)
        if len(used) <= 1:
            return True, "one rig configuration across %d captures" % len(state["captures"]), \
                   None, {}
        recorded = {d.get("field") for d in state["deviations"] if d.get("kind") == "rig"}
        if not recorded:
            return False, ("the captures in these states were taken under %d different rig "
                           "configurations and no rig deviation was recorded"
                           % len(used)), \
                   "re-freeze deliberately with `pilot.py setup --reason ...`, which records what " \
                   "changed, or re-take the frames from the earlier configuration", \
                   {"configurations": {h[:8]: v[:3] for h, v in used.items()}}
        return True, "%d rig configurations, with the change recorded as a deviation" % len(used), \
               None, {"configurations": sorted(h[:8] for h in used)}

    _guard(blocks, satisfied, "rig.frozen", c_setup_frozen)
    _guard(blocks, satisfied, "rig.calibrated", c_setup_checks)
    _guard(blocks, satisfied, "rig.board_square_measured", c_board_square)
    _guard(blocks, satisfied, "rig.captures_attributable", c_captures_carry_setup)
    _guard(blocks, satisfied, "rig.one_configuration", c_one_rig)

    # --- measurements ---------------------------------------------------------------------
    def c_measurements():
        missing, thin, inconsistent, implausible = [], [], [], []
        for name, n_required in sorted(REQUIRED_MEASUREMENTS.items()):
            m = state["measurements"].get(name)
            if not m:
                missing.append(name)
                continue
            readings = [r for r in (m.get("readings") or []) if r is not None]
            if len(readings) < n_required:
                thin.append("%s (%d of %d readings)" % (name, len(readings), n_required))
                continue
            if any(not isinstance(r, (int, float)) or not math.isfinite(float(r))
                   for r in readings):
                implausible.append("%s (a reading is not a finite number)" % name)
                continue
            lo, hi = MEASUREMENT_RANGE.get(name, (None, None))
            mean = sum(readings) / len(readings)
            if lo is not None and not (lo <= mean <= hi):
                implausible.append("%s = %.2f, outside the plausible %.0f-%.0f for an adult "
                                   "garment (a tape read in inches gives two readings that agree "
                                   "perfectly and are 2.5x wrong)" % (name, mean, lo, hi))
                continue
            tol = MEASUREMENT_TOLERANCE.get(name, MEASUREMENT_TOLERANCE["_default_cm"])
            spread = max(readings) - min(readings)
            if spread > tol:
                inconsistent.append("%s (readings differ by %.2f, tolerance %.2f)"
                                    % (name, spread, tol))
        if missing or thin or inconsistent or implausible:
            parts = []
            if missing:
                parts.append("%d not measured (%s)" % (len(missing), ", ".join(missing)))
            if thin:
                parts.append("%d with too few readings (%s)" % (len(thin), "; ".join(thin)))
            if inconsistent:
                parts.append("%d whose readings disagree (%s)"
                             % (len(inconsistent), "; ".join(inconsistent)))
            if implausible:
                parts.append("%d outside a plausible range (%s)"
                             % (len(implausible), "; ".join(implausible)))
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
                q = state["qa"].get(key)
                cap = state["captures"].get(key)
                if cap is not None and cap.get("state") and cap["state"] != s["state"]:
                    # Two projections disagreed about what a capture's state means: the one-rig
                    # condition trusts the capture's self-declared state while this one matched on
                    # shot id alone, so a frame could mislabel its state to escape the first and
                    # still count as the second's evidence.
                    failing.append("%s r%d (filed under state %r, but the shot belongs to %r)"
                                   % (key[0], key[1], cap.get("state"), s["state"]))
                    continue
                if key not in done:
                    # `done` excludes frames the checker rejected, so "not done" covers two very
                    # different situations and the operator's next move differs: take the
                    # photograph, versus look at why the one you took was refused.
                    if q and q.get("outcome") == QA.RETAKE:
                        failing.append("%s r%d (%s)" % (key[0], key[1], q.get("outcome")))
                    else:
                        missing.append("%s r%d" % key)
                    continue
                if not q:
                    unresolved.append("%s r%d (never checked)" % key)
                    continue
                out = q.get("outcome")
                # The record must contain the checks its own shot class can support. Re-deriving the
                # roll-up from the stored list tests the record against ITSELF: a list of invented
                # all-PASS checks rolls up to PASS and agrees with a PASS verdict perfectly. So the
                # MANDATORY set comes from the code -- what this class of frame is checkable for --
                # and anything absent has to be justified by the record's own not_applicable notes.
                present = {c.get("check_id") for c in (q.get("checks") or [])}
                # An excuse is honoured only when the code would itself have written it. The list
                # is free text from the same record the rule is meant to constrain.
                excused = {x.get("check_id") for x in (q.get("not_applicable") or [])
                           if QA.excuse_is_valid(s, x.get("check_id"),
                                                 x.get("not_applicable_to"))}
                mandatory = set(QA.APPLICABLE.get(QA.shot_class(s), ())) - QA.OPTIONAL_CHECKS
                absent = sorted(mandatory - present - excused)
                if absent:
                    failing.append("%s r%d (its record is missing %d check(s) this kind of frame "
                                   "is checkable for: %s)"
                                   % (key[0], key[1], len(absent), ", ".join(absent[:4])))
                    continue
                recomputed = QA.roll_up([QA.Check(c.get("check_id", "?"), c.get("outcome", QA.UNAVAILABLE),
                                                  c.get("detail", ""))
                                         for c in (q.get("checks") or [])])
                if recomputed != out:
                    # The verdict is a roll-up of the checks stored beside it. If the two disagree,
                    # the outcome was written by something other than the checker, and appending a
                    # forged one leaves the hash chain perfectly intact.
                    failing.append("%s r%d (recorded %s, but its own checks roll up to %s)"
                                   % (key[0], key[1], out, recomputed))
                    continue
                if out == QA.PASS:
                    continue
                if out == QA.HUMAN:
                    if not _human_resolved(state, s["shot_id"], rep, q,
                                           state["captures"].get(key)):
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
            return False, ("file integrity was not verified in this view, so whether every recorded "
                           "photograph is still on disk and unchanged is unknown"), \
                   "unknown is not permission: run `pilot.py precut` (or open the GATE tab), which " \
                   "hashes every file", {}
        missing, changed, unhashed, misfiled = [], [], [], []
        for (sid, rep), c in sorted(state["captures"].items()):
            rel = c.get("path")
            if not rel:
                missing.append("%s r%d (no path)" % (sid, rep))
                continue
            if not c.get("sha256"):
                # The hash comparison used to be conditional on a hash having been recorded, so an
                # entry that recorded none skipped it entirely and a 12-byte text file counted as a
                # photograph while the gate reported "present and hash-matched".
                unhashed.append("%s r%d" % (sid, rep))
                continue
            # Ingestion files a capture as <shot>__r<NN>__<sha12>.<ext>. An entry whose path does
            # not encode its own shot, repeat and hash is pointing at some other shot's file, which
            # is how a photograph that was never taken passed by pure append.
            # The BASENAME was all that was checked, so "../../other/NAME" and an absolute path
            # both satisfied it while pointing the evidence somewhere else entirely. Containment
            # first, and through realpath, so a symlink cannot lead out either.
            if os.path.isabs(rel) or ".." in Path(rel).parts:
                misfiled.append("%s r%d -> %s (path escapes the garment directory)" % (sid, rep, rel))
                continue
            try:
                real = Path(os.path.realpath(str(garment_dir / rel)))
                real.relative_to(Path(os.path.realpath(str(garment_dir))))
            except (ValueError, OSError):
                misfiled.append("%s r%d -> %s (resolves outside the garment directory)"
                                % (sid, rep, rel))
                continue
            base = os.path.basename(rel)
            safe = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in str(sid))
            want = "%s__r%02d__%s" % (safe, int(rep), str(c["sha256"])[:12])
            if not base.startswith(want):
                misfiled.append("%s r%d -> %s" % (sid, rep, base))
                continue
            p = garment_dir / rel
            if not p.exists():
                missing.append("%s r%d -> %s" % (sid, rep, rel))
                continue
            want = c.get("sha256")
            if want and _hash_changed(p, want, use_cache=not rehash):
                changed.append("%s r%d -> %s" % (sid, rep, rel))
        if missing or changed or unhashed or misfiled:
            return False, ("%d recorded photograph(s) missing from disk, %d no longer matching "
                           "their recorded hash, %d recorded without a hash at all, %d filed under "
                           "a name that is not their own shot and hash"
                           % (len(missing), len(changed), len(unhashed), len(misfiled))), \
                   "restore them from the phone, or re-capture. A manifest entry whose file is " \
                   "gone, unhashed, or pointing at another shot's photograph is not evidence.", \
                   {"missing": missing[:8], "changed": changed[:8], "unhashed": unhashed[:8],
                    "misfiled": misfiled[:8]}
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
                else:
                    # The verdict was made against a particular earlier frame. If that frame has
                    # since been replaced, the verdict describes a photograph that is no longer
                    # there -- so two frames of the same lay can sit under reps 1 and 2 with a
                    # passing relay verdict between them.
                    against = (rc.get("evidence") or {}).get("compared_against_sha256")
                    prev_cap = state["captures"].get((s["shot_id"], rep - 1)) or {}
                    if not against:
                        bad.append("%s r%d (its relay verdict does not name the frame it was "
                                   "compared against)" % (s["shot_id"], rep))
                    elif prev_cap.get("sha256") and against != prev_cap["sha256"]:
                        bad.append("%s r%d (compared against a frame that has since been replaced)"
                                   % (s["shot_id"], rep))
        if bad:
            return False, ("%d repeat capture(s) are not established as independent re-lays"
                           % len(bad)), \
                   "each repeat must follow the garment being lifted clear and laid out again; " \
                   "confirm the re-lay in the app or re-take the repeat", {"failing": bad[:10]}
        return True, "%d repeat capture(s) established as independent re-lays" % \
               sum(int(s["min_reps"]) - 1 for s in need), None, {}

    _guard(blocks, satisfied, "captures.relays_independent", c_relays)

    def c_repositions():
        req = required_here()
        need = [s for s in req if s.get("reposition_camera_between_reps")
                and int(s.get("min_reps", 1)) > 1]
        bad = []
        for s in need:
            for rep in range(2, int(s["min_reps"]) + 1):
                q = state["qa"].get((s["shot_id"], rep)) or {}
                rc = None
                for c in (q.get("checks") or []):
                    if c.get("check_id") == "camera_repositioned":
                        rc = c
                if rc is None:
                    bad.append("%s r%d (never asked)" % (s["shot_id"], rep))
                elif rc.get("outcome") != QA.PASS:
                    if not _human_resolved(state, s["shot_id"], rep, q,
                                           state["captures"].get((s["shot_id"], rep))):
                        bad.append("%s r%d (%s)" % (s["shot_id"], rep, rc.get("outcome")))
        if bad:
            return False, ("%d repeat capture(s) do not record that the camera was actually "
                           "repositioned" % len(bad)), \
                   "these repeats measure mounting variance only if the phone came off the mount; " \
                   "confirm it in the app or re-shoot", {"failing": bad[:10]}
        return True, "%d repeat capture(s) recorded a camera reposition" % \
               sum(int(s["min_reps"]) - 1 for s in need), None, {}

    _guard(blocks, satisfied, "captures.repositions_recorded", c_repositions)

    def c_reuse_legitimate():
        """A reuse declaration is judged exactly as a verdict is: re-derived, not asserted.

        Round 1 stopped trusting a bare `outcome` on a qa_result. The identical field on the
        neighbouring entry kind kept its trust, so one appended declaration could assert PASS and
        clear the shot it named.
        """
        bad = []
        by_shot = {sh["shot_id"]: sh for sh in (activated or [])}
        for r in state["reuse"]:
            sid = r.get("shot_id")
            if not r.get("source_shot_id") or not r.get("checks_rerun"):
                bad.append("%s (names no source, or records no re-run checks)" % sid)
                continue
            if r.get("outcome") != QA.PASS:
                bad.append("%s (recorded outcome %s)" % (sid, r.get("outcome")))
                continue
            shot = by_shot.get(sid)
            if shot is None:
                bad.append("%s (not an activated shot)" % sid)
                continue
            rerun = set(r.get("checks_rerun") or [])
            mandatory = set(QA.APPLICABLE.get(QA.shot_class(shot), ())) - QA.OPTIONAL_CHECKS
            missing = sorted(mandatory - rerun)
            if missing:
                bad.append("%s (did not re-run %s)" % (sid, ", ".join(missing[:4])))
        if bad:
            return False, ("%d image reuse declaration(s) do not establish that the borrowed image "
                           "was re-checked against the borrowing shot's own requirements"
                           % len(bad)), \
                   "an image may satisfy a second shot only when every requirement of that shot " \
                   "passes on it; run `pilot.py reuse`, which re-runs them, or capture the shot", \
                   {"shots": bad[:8]}
        return True, "%d image reuse declaration(s), each re-checked" % len(state["reuse"]), None, {}

    _guard(blocks, satisfied, "captures.reuse_legitimate", c_reuse_legitimate)

    def c_no_undeclared_reuse():
        """No two accepted captures may be the same photograph unless the reuse is declared.

        Duplicate detection lived only in the add-time checker, whose comparison set is built from
        the files present on disk at that moment. Anything that made a comparison not happen -- an
        earlier file temporarily missing, an ingest ordering, a checker that had not yet been
        hardened -- left the duplicate accepted, and nothing ever looked again. This is the same
        question asked of the DURABLE record, where the hashes are, so it does not depend on what
        could be read at the time.
        """
        # An exemption is honoured only when the log backs it: the source must be a capture that
        # exists, the borrowed frame must be the same bytes, and the borrowing shot must carry its
        # own verdict over those bytes. Otherwise a bare declaration naming any pair of shot ids
        # removed them from duplicate detection whatever they actually held.
        # An exemption covers a PAIR of keys, not a key. Removing keys before grouping meant a
        # declaration naming a capture as its own source satisfied every backing test trivially and
        # deleted that key from the bucket -- leaving the genuine other user of the same bytes as a
        # singleton, and the condition reporting the positive claim.
        covered = set()
        for r in state["reuse"]:
            try:
                tgt = (r.get("shot_id"), int(r.get("rep", 1)))
                srck = (r.get("source_shot_id"), int(r.get("source_rep", 1)))
            except (TypeError, ValueError):
                continue
            if tgt == srck:
                continue                       # a frame is not its own source
            src_cap = state["captures"].get(srck)
            tgt_cap = state["captures"].get(tgt)
            tgt_qa = state["qa"].get(tgt)
            if not src_cap or not tgt_cap:
                continue
            if not src_cap.get("sha256") or src_cap["sha256"] != tgt_cap.get("sha256"):
                continue
            if r.get("sha256") and r["sha256"] != src_cap["sha256"]:
                continue
            if not tgt_qa or tgt_qa.get("capture_sha256") != src_cap["sha256"] \
                    or tgt_qa.get("outcome") != QA.PASS:
                continue
            covered.add(frozenset((tgt, srck)))
        by_sha = {}
        for key, c in sorted(state["captures"].items()):
            sha = c.get("sha256")
            if not sha:
                continue
            by_sha.setdefault(sha, []).append(key)
        dupes = {}
        for sha, ks in by_sha.items():
            if len(ks) < 2:
                continue
            # Every pair sharing these bytes must be covered by a declaration of its own.
            uncovered = [(a, b) for i, a in enumerate(ks) for b in ks[i + 1:]
                         if frozenset((a, b)) not in covered]
            if uncovered:
                dupes[sha] = ks
        if dupes:
            eg = []
            for sha, ks in sorted(dupes.items())[:4]:
                eg.append("%s used for %s" % (sha[:12],
                                              ", ".join("%s r%d" % k for k in ks[:3])))
            return False, ("%d photograph(s) are filed under more than one shot without a recorded "
                           "reuse declaration" % len(dupes)), \
                   "one frame may satisfy a second shot only when every requirement of that shot " \
                   "passes on it and the reuse is recorded; otherwise capture the shot properly", \
                   {"duplicates": eg}
        return True, "no photograph satisfies two shots without a declared reuse", None, {}

    _guard(blocks, satisfied, "captures.no_undeclared_reuse", c_no_undeclared_reuse)

    # --- the cut itself -------------------------------------------------------------------
    if gate_id in ("ready_to_wash", "ready_to_finalize"):
        def c_offcuts():
            from . import offcut as OFF
            gid = garment_dir.name
            want = {"%s_OFFCUT_L" % gid, "%s_OFFCUT_R" % gid}
            oc = state["offcuts"]
            # Identity first. Everything below keys off the label, which is free text, so two
            # records labelled ..._OFFCUT_L and ..._OFFCUT_L2 were two samples as far as the count
            # was concerned and one leg as far as the experiment was concerned.
            if set(oc) != want:
                return False, ("the offcut records are %s; this garment's two samples are %s"
                               % (", ".join(sorted(oc)) or "none", ", ".join(sorted(want)))), \
                       "run `pilot.py offcut plan --assign auto`, which writes both labels", \
                       {"have": sorted(oc), "want": sorted(want)}
            legs = {str(v.get("originating_leg", ""))[:1].lower() for v in oc.values()}
            if legs != {"l", "r"}:
                return False, ("both offcut records name the same leg (%s); they are two samples "
                               "from two legs" % ", ".join(sorted(legs))), \
                       "correct the originating_leg on the offcut records", {"legs": sorted(legs)}
            assigned = [v for v in oc.values() if v.get("assigned_wash_condition")]
            if len(assigned) < 2:
                return False, "both offcuts must have a wash condition assigned before the wash", \
                       "run `pilot.py offcut plan --assign auto`", {}
            unknown = [v.get("assigned_wash_condition") for v in assigned
                       if OFF.classify(v.get("assigned_wash_condition")) is None]
            if unknown:
                return False, ("an offcut is assigned a condition this protocol does not define: "
                               "%s" % ", ".join(repr(u) for u in unknown[:3])), \
                       "the conditions are %s" % ", ".join(OFF.CONDITIONS), {"unknown": unknown}
            # Distinctness over the ASSIGNED records only. Built over every record, one bare extra
            # entry with no condition put a None into the set and made two identical conditions
            # look like two.
            standard = [v for v in assigned
                        if OFF.classify(v["assigned_wash_condition"]) == "standard"]
            if len(standard) != 1:
                # Distinct is not enough. PROTOCOL.md 7 is specific: ONE offcut follows the standard
                # protocol in the same load as the garment. Two distinct non-standard conditions
                # are two samples and no control.
                return False, ("%d of the two offcuts follow the standard protocol; exactly one "
                               "must" % len(standard)), \
                       "one offcut goes in with the garment under the standard protocol and the " \
                       "other into a separate load; `pilot.py offcut plan --assign auto` writes " \
                       "that pair", {"conditions": sorted(v["assigned_wash_condition"]
                                                          for v in assigned)}
            conds = {v["assigned_wash_condition"] for v in assigned}
            if len(conds) < 2:
                return False, ("both offcuts are assigned the same condition (%s), so the pair "
                               "measures nothing" % ", ".join(sorted(conds))), \
                       "the two offcuts exist to be washed differently; re-assign", \
                       {"conditions": sorted(conds)}
            wa_ = state["wash_actual"]
            if wa_ and wa_.get("seq") is not None:
                late = [lbl for lbl, v in oc.items()
                        if (v.get("_seq") or {}).get("assigned_wash_condition") is not None
                        and int((v["_seq"])["assigned_wash_condition"]) > int(wa_["seq"])]
                if late:
                    return False, ("the wash condition for %s was assigned AFTER the wash was "
                                   "recorded" % ", ".join(sorted(late))), \
                           "the assignment decides which offcut goes into the garment's load and " \
                           "keeps the left/right alternation unconfounded; recorded afterwards it " \
                           "decides nothing", {"late": sorted(late)}
            alt = OFF.check_alternation(garment_dir.parent)
            if alt.get("unclassified"):
                return False, ("%d sibling garment(s) record an offcut condition this code cannot "
                               "classify, so whether the alternation holds is unknown: %s"
                               % (len(alt["unclassified"]),
                                  ", ".join(u["garment_id"] for u in alt["unclassified"][:3]))), \
                       ("record those conditions in the protocol's vocabulary (%s)"
                        % ", ".join(OFF.CONDITIONS)), {"unclassified": alt["unclassified"][:3]}
            if not alt["alternating"]:
                excused = any(d.get("kind") == "offcut_alternation" for d in state["deviations"])
                if not excused:
                    return False, ("the left/right alternation is broken across garments (%s): leg "
                                   "and wash condition are confounded"
                                   % "".join(alt["sequence"])), \
                           "PROTOCOL.md 7 alternates which leg goes in with the garment; if it " \
                           "cannot be fixed, record it deliberately as a deviation of kind " \
                           "'offcut_alternation'", {"breaks": alt["breaks"][:3]}
                return True, ("the alternation is broken (%s) and the departure is recorded as a "
                              "deviation" % "".join(alt["sequence"])), None, \
                       {"breaks": alt["breaks"][:3]}
            return True, "two offcuts, two legs, two conditions, alternation intact (%s)" % \
                   "".join(alt["sequence"]), None, {}

        _guard(blocks, satisfied, "offcuts.assigned", c_offcuts)

        def c_wash_planned():
            wp = state["wash_planned"]
            if not wp:
                return False, "no wash has been planned", \
                       "run `pilot.py wash <GARMENT>` before the load goes in", {}
            missing = [k for k in WASH_FIELDS if wp.get(k) in (None, "")]
            if missing:
                return False, "the wash plan is missing %s" % ", ".join(missing[:6]), \
                       "re-record the plan with every field", {"missing": missing}
            wa_ = state["wash_actual"]
            if wa_ and wp.get("seq") is not None and wa_.get("seq") is not None \
                    and int(wp["seq"]) > int(wa_["seq"]):
                return False, ("the wash plan was written AFTER the wash it is supposed to have "
                               "planned, so the two collapse and every deviation computes to "
                               "nothing"), \
                       "the plan is what the actual settings are measured against; it has to " \
                       "exist before them", {"plan_seq": wp.get("seq"), "actual_seq": wa_.get("seq")}
            if state["wash_plan_rewrites"]:
                return False, ("the wash plan was written %d more time(s) after the first; the "
                               "planned settings are what the deviation is measured against and "
                               "cannot be revised to match what happened"
                               % len(state["wash_plan_rewrites"])), \
                       "the first plan stands. Record the difference as a deviation instead.", \
                       {"rewrites": [r["seq"] for r in state["wash_plan_rewrites"]][:5]}
            return True, "wash planned: %s, %s" % (wp.get("machine"), wp.get("cycle")), None, {}

        _guard(blocks, satisfied, "wash.planned", c_wash_planned)

    if gate_id == "ready_to_finalize":
        def c_wash_actual():
            """The wash actually happened, and its deviations from the plan are recorded.

            ready_to_finalize differed from ready_to_wash by one state and added no condition of its
            own, so a garment could be photographed after washing with no record that it had been
            washed, under what settings, or how far those departed from the plan. The whole
            experiment is one wash.
            """
            wa, wp = state["wash_actual"], state["wash_planned"]
            if not wa:
                return False, "no actual wash settings were recorded", \
                       "run `pilot.py wash <GARMENT> --actual` with what really happened", {}
            missing = [k for k in WASH_FIELDS if wa.get(k) in (None, "")]
            if missing:
                return False, "the actual wash record is missing %s" % ", ".join(missing[:6]), \
                       "re-record it with every field", {"missing": missing}
            from .store import diff_planned_actual
            devs = diff_planned_actual(wp, wa)

            def _same(a, b):
                if isinstance(a, float) or isinstance(b, float):
                    try:
                        return abs(float(a) - float(b)) < 1e-9
                    except (TypeError, ValueError):
                        return False
                return a == b

            # A deviation has to DESCRIBE the departure, not merely name the field. Matching on the
            # field alone meant pre-registering all fifteen field names before the wash excused
            # whatever happened afterwards.
            unrecorded = []
            for d in devs:
                if not any(x.get("kind") == "wash" and x.get("field") == d["field"]
                           and _same(x.get("planned"), d["planned"])
                           and _same(x.get("actual"), d["actual"])
                           for x in state["deviations"]):
                    unrecorded.append("%s (%s -> %s)" % (d["field"], d["planned"], d["actual"]))
            if unrecorded:
                return False, ("%d wash setting(s) departed from the plan without a deviation "
                               "that describes the departure: %s"
                               % (len(unrecorded), "; ".join(unrecorded[:5]))), \
                       "record each departure with what was planned and what happened; a " \
                       "deviation that only names the field excuses any value", \
                       {"unrecorded": unrecorded}
            return True, "wash recorded, %d deviation(s) from the plan, all recorded" % len(devs), \
                   None, {"deviations": [d["field"] for d in devs]}

        _guard(blocks, satisfied, "wash.actual", c_wash_actual)

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
            # The LATEST record, by time. Selecting by dictionary iteration order meant a retraction
            # appended after an approval could be discarded in favour of the approval.
            cands = [rec for (sid, rep, claim), rec in state["verifications"].items()
                     if claim == "cut_marks_verified"]
            # By log POSITION. `ts` comes from the payload on any path that sets it, so ordering by
            # it let a future-dated approval outrank a real retraction appended after it.
            v = max(cands, key=lambda r: (r.get("seq") if r.get("seq") is not None else -1)) \
                if cands else None
            if v is not None and v.get("value") is not True:
                # `value` was never read here, so a recorded REFUSAL -- a second person writing
                # "no, the marks are on the wrong leg" -- was reported as an approval.
                return False, ("the second person did not approve the marks: %s"
                               % (v.get("note") or "recorded as not verified")), \
                       "re-mark the garment and have it verified again", \
                       {"verifier": v.get("verifier_name"), "at": v.get("ts")}
            if not v:
                return False, "no second person has verified the cut marks", \
                       "a second person measures both marks with a tape and records the reading; " \
                       "PROTOCOL.md 3.2 requires it before cutting", {}
            for k in ("verifier_name", "measured_inseam_cm", "measured_outseam_cm"):
                if not v.get(k):
                    return False, "the second-person verification is missing %s" % k, \
                           "re-record the verification with all fields", {"have": sorted(v.keys())}
            if not (v.get("operator") or "").strip() or not (v.get("verifier_name") or "").strip():
                return False, ("the cut-mark verification does not name both the operator and the "
                               "person who verified"), \
                       "re-record it with --verifier NAME; a verification with no attribution is " \
                       "not one", {"operator": v.get("operator"),
                                   "verifier": v.get("verifier_name")}
            if (v.get("verifier_name") or "").strip().lower() == \
                    (v.get("operator") or "").strip().lower():
                # PROTOCOL.md 3.2 asks for a SECOND person. verifier_name defaults to the operator
                # when --verifier is omitted, which is the natural thing to do when one person is at
                # the table -- and then the check was one person agreeing with themselves.
                return False, ("the cut marks were verified by %r, who is the operator; the "
                               "protocol requires a second person"
                               % v.get("verifier_name")), \
                       "have someone else measure both marks and record it with --verifier NAME", \
                       {"operator": v.get("operator")}
            cs = state["cut_spec"] or {}
            errs = {}
            for field, target in (("measured_inseam_cm", cs.get("target_inseam_cm")),
                                  ("measured_outseam_cm", cs.get("predicted_outseam_cm"))):
                if target is None:
                    return False, "cannot check the verification against a cut spec that is absent", \
                           "run `pilot.py cutspec` first", {}
                try:
                    got = float(v[field])
                except (TypeError, ValueError):
                    return False, "the verification's %s is not a number" % field, \
                           "re-record the verification", {"value": v.get(field)}
                if not math.isfinite(got) or not math.isfinite(float(target)):
                    # NaN compares false against everything, so a NaN reading slipped past
                    # `worst > tolerance` and disabled the 3 mm tolerance entirely.
                    return False, ("the verification's %s is not a finite measurement (%r), so the "
                                   "%.0f mm tolerance cannot be applied to it"
                                   % (field, v.get(field), CUT_MARK_TOLERANCE_MM)), \
                           "re-measure and record a real number", {"value": v.get(field)}
                errs[field] = abs(got - float(target)) * 10.0     # cm -> mm
            worst = max(errs.values())
            if not math.isfinite(worst) or worst > CUT_MARK_TOLERANCE_MM:
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
                recs = [rec for (_, _, c), rec in state["verifications"].items() if c == claim]
                latest = max(recs, key=lambda r: (r.get("seq") if r.get("seq") is not None else -1)) \
                    if recs else None
                if latest is None or latest.get("value") is not True:
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


#: Re-hashing every photograph on every screen refresh is wasteful and skipping the check is not
#: acceptable, so the result is cached on the file's identity. The first version keyed the cache on
#: (path, size, mtime) and asserted that a file whose size and mtime were unchanged had not been
#: rewritten -- which is false, because mtime is settable. Replacing a photograph and restoring its
#: mtime with os.utime defeated it for as long as a `serve` process stayed up, and a capture UI is
#: exactly a long-running process.
#:
#: The key now includes the inode and ctime. ctime is the inode's own change time and cannot be set
#: through utime; rewriting the file's contents moves it whatever is done to mtime. That is not a
#: cryptographic guarantee -- a process with enough privilege can do more than utime -- but it
#: closes the gap that an ordinary write leaves open, and `--recheck` re-hashes everything.
_HASH_CACHE = {}


def _hash_changed(path, want, use_cache=True):
    from .manifest import sha256_file
    try:
        st = os.stat(str(path))
    except OSError:
        return True
    key = (str(path), st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    got = _HASH_CACHE.get(key) if use_cache else None
    if got is None:
        got = sha256_file(path)
        if use_cache:
            _HASH_CACHE[key] = got
    return got != want


def _human_resolved(state, shot_id, rep, qa_record, capture=None):
    """A HUMAN outcome counts only when every claim it raised has a verification OF THIS PHOTOGRAPH.

    Three things were wrong with resolving a claim by name alone, and each was a false READY:

    * The verification was not bound to the frame. Re-ingesting a different photograph under the
      same shot id left the old confirmation in place, so a frame of the back of the garment
      inherited a confirmation that the front was facing up.
    * It was not bound in TIME either, so every claim the plan could ever raise could be confirmed
      in a loop before a single photograph existed, and each frame arrived pre-cleared.
    * A recorded refusal counted the same as an approval wherever `value` was not read.

    So a verification clears a claim only when it names the capture's own hash, or -- for records
    written before that field existed -- was made after the photograph it is about.
    """
    claims = [c.get("check_id") for c in (qa_record.get("checks") or [])
              if c.get("outcome") == QA.HUMAN]
    if not claims:
        return False
    cap_sha = (capture or {}).get("sha256")
    cap_seq = (capture or {}).get("seq")
    for claim in claims:
        rec = state["verifications"].get((shot_id, rep, claim))
        if not rec or rec.get("value") is not True or not rec.get("operator"):
            return False
        # Both, not either. The OR was the hole: a verification carrying a sha that no capture had
        # yet -- the API takes capture_sha256 straight from the client -- satisfied the first branch
        # and never reached the second, so every claim could still be pre-cleared before the
        # photograph existed. And the ordering is log POSITION, because the payload's clock is
        # writable while the sequence number is stamped by the appender.
        if not cap_sha or rec.get("capture_sha256") != cap_sha:
            return False
        if cap_seq is not None and rec.get("seq") is not None \
                and int(rec["seq"]) < int(cap_seq):
            return False
    return True
