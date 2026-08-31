#!/usr/bin/env python3
"""Load the shot-plan specification and refuse it if anything it points at does not exist.

This is separated from the self test because it is the cheaper and more fundamental question. The
self test asks whether the gate behaves; this asks whether the document the gate enumerates from is
coherent at all. A shot whose `conditional_on` names a feature key that does not exist can never
activate, so a typo there removes a required photograph and nothing else in the system notices.

    tools/check_shotplan.py [--spec protocol/shotplan/shotplan.json]

Exit 0 the specification loads and every reference resolves
     1 it does not
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from denimtwin.pilot import spec as SPEC     # noqa: E402
from denimtwin.pilot import plan as PLAN     # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--spec", default=str(ROOT / "protocol" / "shotplan" / "shotplan.json"))
a = p.parse_args()

try:
    s = SPEC.load(a.spec)
except SPEC.SpecError as e:
    print(e)
    raise SystemExit(1)

# Every feature answered "present" must produce a plan; a plan that fails to generate under the
# most inclusive answers is a plan that can fail to generate at all.
answers = {f["key"]: (1 if f["type"] == "count" else True) for f in s.features}
shots, meta = PLAN.activate(s, answers, {"leg_opening_cm": {"mean": 20.0}})
if not shots:
    print("the specification activates no shots even with every feature present")
    raise SystemExit(1)
if meta["expansion_blocked"]:
    print("templated series could not expand even with a leg opening supplied:")
    for x in meta["expansion_blocked"]:
        print("   %s: %s" % (x["shot_id"], x["why"]))
    raise SystemExit(1)

ordered = PLAN.order(s, shots)
required = [x for x in ordered if x["necessity"] != "optional"]
by_state = {}
for x in ordered:
    by_state[x["state"]] = by_state.get(x["state"], 0) + 1

print("shot plan v%s (%s) loads and cross-checks" % (s.version, s.content_hash[:12]))
print("  %d shot definitions -> %d frames with every feature present" % (len(s.shots), len(ordered)))
print("  %d required, %d optional; %d regions; %d features; %d matched pairs"
      % (len(required), len(ordered) - len(required), len(s.regions), len(s.features),
         len(s.matched_pairs())))
print("  by state: " + ", ".join("%s=%d" % kv for kv in
                                 sorted(by_state.items(),
                                        key=lambda kv: [st["order"] for st in s.states
                                                        if st["state"] == kv[0]][0])))
raise SystemExit(0)
