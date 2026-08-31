"""One log per garment, and every view of the session derived from it.

The alternative -- a session.json holding current state, a manifest holding captures, a
measurements.json holding numbers -- has a failure mode that this project cannot afford: the files
disagree, and nothing says which one is right. A gate reading the wrong one passes a garment that
should have been blocked, and the garment gets cut.

So there is one append-only log, and everything else is a projection of it. `fold()` replays the log
into the state the session is in. That makes three properties fall out rather than having to be
engineered:

  * RESUME is free. There is no separate state to reconcile after an interruption -- replaying the
    log is what the process does every time anyway, so a session that died mid-capture resumes into
    exactly the state its last durable entry describes.
  * TAMPER IS EVIDENT. Editing history to make a gate pass breaks the hash chain at the edited
    entry, and the chain is verified on every read.
  * PLANNED AND ACTUAL CANNOT COLLAPSE. A wash's actual settings are a new entry, not a mutation of
    the planned ones, so a deviation is computed by diffing two entries that both still exist. The
    protocol requires deviations to stay visible; an append-only log makes losing them impossible
    rather than merely discouraged.

Entry kinds are closed. An unknown kind in the log is surfaced rather than ignored, because a log
this process cannot fully interpret is not a log it should be gating a cut on.
"""
import copy
import time
from pathlib import Path

from .manifest import Manifest, canonical, sha256_text

KINDS = (
    "session_opened",        # garment id, spec version and hash
    "setup_frozen",          # the rig configuration and its hash
    "setup_check",           # one rig calibration reading (square size, height, lens, backdrop...)
    "feature_answers",       # the intake questionnaire, whole or partial
    "measurement",           # one named measurement with its individual readings
    "capture",               # one photograph accepted into the tree
    "qa_result",             # the checks run against one capture
    "human_verification",    # a person asserting something a measurement cannot settle
    "reuse_declaration",     # one image satisfying a second shot id, with the reason it may
    "deviation",             # any departure from the frozen protocol
    "state_transition",      # before -> marked -> immediate_after -> post_wash
    "cut_spec",              # the digital cut definition and its prediction
    "wash_planned", "wash_actual",
    "offcut",                # one offcut sample's identity and measurements
    "note",
)


class Store(object):
    def __init__(self, garment_dir):
        self.dir = Path(garment_dir)
        self.garment_id = self.dir.name
        self.pilot_dir = self.dir / "pilot"
        # The chain starts from THIS garment's identity, so a log copied from another garment fails
        # at its first entry instead of verifying perfectly and satisfying the gate for a garment
        # that was never photographed.
        self.manifest = Manifest(self.pilot_dir / "manifest.jsonl",
                                 seed=sha256_text("denim-twin/pilot/" + self.garment_id))

    # -- writing ------------------------------------------------------------------------------

    def append(self, kind, payload, *, operator=None, setup_hash=None, now=None):
        if kind not in KINDS:
            raise ValueError("unknown log entry kind %r; the log's vocabulary is closed so that a "
                             "reader cannot silently ignore something it does not understand" % kind)
        return self.manifest.append(kind, payload, operator=operator, setup_hash=setup_hash,
                                    now=now)

    # -- reading ------------------------------------------------------------------------------

    @staticmethod
    def _key(v, what, seq, problems):
        """A projection key taken from a payload. Only a scalar can be one.

        fold() keyed four projections on values taken straight from the payload -- the setup check's
        name, the measurement's name, the offcut's label, the verification's claim -- and coerced
        two more with a bare int(). A JSON object or array in any of them raised inside the replay,
        and because every gate condition reads the folded state rather than the log, one such entry
        made the garment permanently ungateable: not a false pass, but no verdict at all, on a
        garment whose photographs were fine.
        """
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, int) and not isinstance(v, bool):
            return v
        problems.append({"kind": "uninterpretable_payload", "seq": seq,
                         "detail": "the %s of entry %s is %r, which cannot identify anything"
                                   % (what, seq, v)})
        return None

    @staticmethod
    def _rep(v, seq, problems):
        try:
            if v is None:
                return 1
            r = int(v)
            if r < 1:
                raise ValueError(r)
            return r
        except (TypeError, ValueError):
            problems.append({"kind": "uninterpretable_payload", "seq": seq,
                             "detail": "entry %s has a repeat index of %r" % (seq, v)})
            return None

    def fold(self):
        """Replay the log. Returns a state dict plus the integrity problems found on the way.

        Total by construction: an entry this code cannot interpret becomes a PROBLEM, which
        `gates.log.intact` blocks on, rather than an exception that leaves the gate with nothing to
        say.
        """
        entries, problems = self.manifest.read()
        st = {
            "garment_id": self.dir.name,
            "spec_version": None, "spec_hash": None,
            "setup": None, "setup_hash": None, "setup_history": [],
            "setup_checks": {},
            "features": {}, "features_answered_at": None,
            "measurements": {},
            "captures": {},          # (shot_id, rep) -> capture record
            "qa": {},                # (shot_id, rep) -> the qa record for the CURRENT capture
            "qa_all": {},            # (shot_id, rep) -> every qa record, in order
            "verifications": {},     # (shot_id, rep, claim) -> verification
            "reuse": [],
            "deviations": [],
            "state": None, "state_history": [],
            "cut_spec": None,
            "wash_planned": None, "wash_actual": None,
            "offcuts": {},
            "notes": [],
            "unknown_kinds": [],
            "n_entries": len(entries),
        }
        for e in entries:
            k, p = e.get("kind"), e.get("payload") or {}
            if k == "session_opened":
                st["spec_version"] = p.get("spec_version")
                st["spec_hash"] = p.get("spec_hash")
            elif k == "setup_frozen":
                st["setup"] = p.get("setup")
                st["setup_hash"] = p.get("setup_hash")
                st["setup_history"].append({"setup_hash": p.get("setup_hash"), "ts": e.get("ts"),
                                            "seq": e.get("seq"), "reason": p.get("reason")})
            elif k == "setup_check":
                key = self._key(p.get("check"), "check name", e.get("seq"), problems)
                if key is not None:
                    # The rig it was taken against travels with it, so a re-freeze cannot inherit
                    # the previous configuration's calibration.
                    st["setup_checks"][key] = dict(p, setup_hash=e.get("setup_hash"),
                                                   seq=e.get("seq"))
            elif k == "feature_answers":
                st["features"].update(p.get("answers") or {})
                st["features_answered_at"] = e.get("ts")
            elif k == "measurement":
                key = self._key(p.get("name"), "measurement name", e.get("seq"), problems)
                if key is not None:
                    st["measurements"][key] = p
            elif k == "capture":
                sid = self._key(p.get("shot_id"), "shot id", e.get("seq"), problems)
                rep = self._rep(p.get("rep", 1), e.get("seq"), problems)
                if sid is None or rep is None:
                    continue
                st["captures"][(sid, rep)] = dict(
                    p, ts=e.get("ts"), seq=e.get("seq"), setup_hash=e.get("setup_hash"),
                    operator=e.get("operator"), chain=e.get("chain"))
            elif k == "qa_result":
                sid = self._key(p.get("shot_id"), "shot id", e.get("seq"), problems)
                rep = self._rep(p.get("rep", 1), e.get("seq"), problems)
                if sid is None or rep is None:
                    continue
                st["qa_all"].setdefault((sid, rep), []).append(
                    dict(p, ts=e.get("ts"), seq=e.get("seq")))
            elif k == "human_verification":
                claim = self._key(p.get("claim"), "claim", e.get("seq"), problems)
                if claim is None:
                    continue
                rep = self._rep(p.get("rep"), e.get("seq"), problems) if p.get("rep") else None
                if p.get("rep") and rep is None:
                    continue
                # The record's OWN attribution wins. `operator=e.get("operator")` overwrote it, so a
                # verification that explicitly named its author projected as operator None -- and
                # the second-person check, which refuses a verifier equal to the operator, compared
                # a name against None and let it through.
                st["verifications"][(p.get("shot_id"), rep, claim)] = dict(
                    p, ts=e.get("ts"), seq=e.get("seq"),
                    operator=p.get("operator") or e.get("operator"))
            elif k == "reuse_declaration":
                st["reuse"].append(dict(p, ts=e.get("ts")))
            elif k == "deviation":
                st["deviations"].append(dict(p, ts=e.get("ts")))
            elif k == "state_transition":
                st["state"] = p.get("to")
                st["state_history"].append({"to": p.get("to"), "ts": e.get("ts")})
            elif k == "cut_spec":
                st["cut_spec"] = dict(p, ts=e.get("ts"))
            elif k == "wash_planned":
                st["wash_planned"] = dict(p, ts=e.get("ts"))
            elif k == "wash_actual":
                st["wash_actual"] = dict(p, ts=e.get("ts"))
            elif k == "offcut":
                lbl = self._key(p.get("label"), "offcut label", e.get("seq"), problems)
                if lbl is None:
                    continue
                cur = st["offcuts"].get(lbl, {})
                cur.update(p)
                st["offcuts"][lbl] = cur
            elif k == "note":
                st["notes"].append(dict(p, ts=e.get("ts")))
            else:
                st["unknown_kinds"].append({"kind": k, "seq": e.get("seq")})
        # A verdict belongs to the photograph it judged. Folding qa_result last-write-wins let one
        # appended line turn ten rejected frames into "all frames captured and passing" -- the
        # cheapest false READY there was. A verdict now only counts when it names the sha256 of the
        # capture currently filed under that shot and repeat, and the latest such verdict wins.
        # Turning a RETAKE into a PASS therefore requires what it requires physically: another
        # photograph.
        for key, recs in st["qa_all"].items():
            cap = st["captures"].get(key)
            if cap is None:
                continue
            sha = cap.get("sha256")
            # The WORST verdict bound to this photograph wins, not the latest. Taking the latest
            # let a second verdict IMPROVE the first: name the same sha, carry a fabricated
            # all-PASS check list, and a RETAKE became a PASS -- which is exactly what "turning a
            # RETAKE into a PASS requires another photograph" was supposed to prevent. Re-running
            # the checker on one frame is deterministic, so two verdicts that disagree about it are
            # evidence of tampering, and the safe reading of a disagreement is the worse one.
            bound = [r for r in recs if sha and r.get("capture_sha256") == sha]
            if bound:
                from .qa import SEVERITY as _SEV
                st["qa"][key] = max(bound, key=lambda r: _SEV.get(r.get("outcome"), 3))
        return st, problems

    # -- convenience --------------------------------------------------------------------------

    def done_keys(self, state=None):
        """(shot_id, rep) pairs that have an accepted capture, optionally within one state.

        Reuse counts, because a declared reuse that passed the borrowing shot's own checks is that
        shot's evidence. A RETAKE does not count: a rejected frame is not a captured one, and
        treating it as captured is how a required shot goes missing without anything saying so.
        """
        st, _ = self.fold()
        out = set()
        for (sid, rep), cap in st["captures"].items():
            if state is not None and cap.get("state") != state:
                continue
            if not cap.get("sha256"):
                continue        # nothing to verify the file against; see gates.captures.files_intact
            q = st["qa"].get((sid, rep))
            if q is None or q.get("outcome") == "RETAKE_REQUIRED":
                continue        # never checked, or rejected: either way not an accepted capture
            out.add((sid, rep))
        for r in st["reuse"]:
            if state is not None and r.get("state") != state:
                continue
            out.add((r.get("shot_id"), int(r.get("rep", 1))))
        return out


def mean_of(measurement):
    """The mean of a measurement's own readings, recomputed.

    The gate validates `readings` -- their count, finiteness, spread and plausible range -- and the
    record also carries a `mean` that nothing checked. Every consumer read the mean: the hem series
    is sized from it, the cut is placed from it. So a record could carry two honest readings and a
    fabricated mean, pass every measurement condition, and hand a different number to the planner
    and the cut. Derived fields are recomputed here rather than trusted.
    """
    if not measurement:
        return None
    rs = []
    for r in (measurement.get("readings") or []):
        try:
            f = float(r)
        except (TypeError, ValueError):
            return None
        if f != f:
            return None
        rs.append(f)
    return (sum(rs) / len(rs)) if rs else None


def setup_hash(setup):
    """Hash of the frozen rig configuration.

    Canonical serialisation with sorted keys, and every float rounded, because the hash's job is to
    say "the rig is the same as it was", and a value that arrives as 82.5 from a form and
    82.50000000000001 from a calculation is the same rig. An unrounded float would make it a
    different one, and the deviation record that followed would be noise.
    """
    return sha256_text(canonical(_round_floats(setup)))


def _round_floats(o, places=4):
    if isinstance(o, float):
        return round(o, places)
    if isinstance(o, dict):
        return {k: _round_floats(v, places) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round_floats(v, places) for v in o]
    return o


def diff_planned_actual(planned, actual):
    """Every field where the wash actually differed from the plan.

    The protocol's rule is that actual settings never replace planned ones. This is the function
    that makes keeping both worth something: the deviations are computed, not remembered.
    """
    if not planned or not actual:
        return []
    out = []
    for k in sorted(set(list(planned.keys()) + list(actual.keys()))):
        if k in ("ts", "recorded_by"):
            continue
        pv, av = planned.get(k), actual.get(k)
        if pv is None and av is None:
            continue
        if isinstance(pv, float) and isinstance(av, float):
            same = abs(pv - av) < 1e-9
        else:
            same = pv == av
        if not same:
            out.append({"field": k, "planned": pv, "actual": av})
    return out
