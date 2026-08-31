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

    def fold(self):
        """Replay the log. Returns a state dict plus the integrity problems found on the way."""
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
                                            "reason": p.get("reason")})
            elif k == "setup_check":
                st["setup_checks"][p.get("check")] = p
            elif k == "feature_answers":
                st["features"].update(p.get("answers") or {})
                st["features_answered_at"] = e.get("ts")
            elif k == "measurement":
                st["measurements"][p.get("name")] = p
            elif k == "capture":
                st["captures"][(p.get("shot_id"), int(p.get("rep", 1)))] = dict(
                    p, ts=e.get("ts"), setup_hash=e.get("setup_hash"), operator=e.get("operator"),
                    chain=e.get("chain"))
            elif k == "qa_result":
                key = (p.get("shot_id"), int(p.get("rep", 1)))
                rec = dict(p, ts=e.get("ts"), seq=e.get("seq"))
                st["qa_all"].setdefault(key, []).append(rec)
            elif k == "human_verification":
                st["verifications"][(p.get("shot_id"), int(p.get("rep", 1)) if p.get("rep") else None,
                                     p.get("claim"))] = dict(p, ts=e.get("ts"),
                                                             operator=e.get("operator"))
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
                lbl = p.get("label")
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
            for r in recs:
                # No compatibility path for a verdict that does not name its photograph: an
                # unbound verdict is exactly the forgery this guards against, and a shot with no
                # usable verdict reads as unchecked, which blocks.
                if sha and r.get("capture_sha256") == sha:
                    st["qa"][key] = r
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
