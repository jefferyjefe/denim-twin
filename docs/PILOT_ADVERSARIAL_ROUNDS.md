# Adversarial rounds against the cut gate

`tools/pilot.py precut` authorises an irreversible physical act. Everything else in the pilot can be
redone; a garment cut in half cannot. So the gate was not reviewed, it was attacked: independent
agents, working in isolated git worktrees against the committed code, with one instruction — make it
print READY TO CUT without the evidence.

Attacking the SOURCE was out of scope throughout. An attacker who may edit `gates.py` proves nothing
except that the file is writable. Editing DATA — the log, the photographs, the answers, the HTTP
requests — was entirely in scope, because that is what an operator in a hurry, or a mistake, can
actually do.

## Round 1 — seven angles, thirty-one findings

| angle | what it attacked | findings |
|---|---|---|
| manifest | the append-only hash-chained log | 8 |
| human | the recorded assertions that clear a HUMAN outcome | 6 |
| coverage | the required set: conditions, counts, expansions | 3 |
| imagery | one frame satisfying many shots; relays; duplicates | 6 |
| rig | the frozen configuration, attribution, the board's scale | 7 |
| api | the HTTP surface as a second way into the same data | 5 |
| filesystem | files under the manifest's feet | 2 |

Independent verifiers re-ran each claim from scratch in their own worktrees. Nine were confirmed
outright (seven false READYs, one crash, one weakened condition); the rest were either already
refused by the time they were re-run — fixes were landing while verification proceeded, so that
count is not a clean measure of the original code — or not reproducible.

**Every one of the thirty-one was fixed, and each is now a scenario in `tools/pilot.py selftest`.**
The suite went from 25 scenarios to 49.

### The ones worth remembering

**Nothing bound a log to its garment.** The chain was seeded from a constant, so `cp -r` of a
finished garment's directory produced a log that verified perfectly and opened the gate for a
garment that had never been photographed. The seed is now the garment's own identity.

**A verdict was not bound to the photograph it judged.** `fold()` kept the last `qa_result` per
shot, so one appended line turned ten rejected frames into "all frames captured and passing" — a
pure append, so the hash chain had nothing to catch. A verdict now counts only if it names the
capture's sha256, and the gate re-derives the roll-up from the stored checks and refuses one that
disagrees with its own evidence.

**A recorded refusal read as an approval.** `cut.second_person_verified` never read `value`, so a
second person writing "no, the marks are on the wrong leg" satisfied the condition. The same
condition selected by dictionary order, so a retraction could be discarded in favour of an older
approval, and accepted the string `"NaN"` — which compares false against every bound and switched
the 3 mm tolerance off.

**A required shot could expand to zero frames and vanish.** Inclusion and cardinality came from two
independent answers that were never reconciled, so a garment with three tears and no distressing was
required to photograph the tears and expanded to nothing. Nothing reported it missing, because
nothing knew it should exist.

**The web upload could not accept a single photograph.** A name was used six lines before the
function-local import that bound it, so every upload of a readable image raised `UnboundLocalError`
*after* the file had been ingested and the capture entry written. It went unnoticed because the UI
tests read state and never posted a frame. A front end nobody exercises is a front end that does not
work; there is now a test that speaks real multipart to a real server.

**Two readings agreeing with each other say nothing about the tape.** `leg_opening_cm` sizes a
required series and places the cut mark, and an operator reading inches records two readings that
agree perfectly and are 2.5× wrong. Every downstream check passed, because everything downstream
believed the number.

## What the attacks did not break

Worth recording, because they are the parts that held:

- The deny-by-default guard. Making a condition raise costs blocks, never a pass; no attacker found
  a data-reachable path to a verdict of READY through an exception.
- The four-outcome discipline. Making `scale_range_ratio` unmeasurable returns UNAVAILABLE_CHECK,
  which the gate treats as blocking — sweeping the board tilt from 0 to 45 degrees never produced a
  pass.
- One confirmation clearing several claims. `_human_resolved` requires a separate record per claim,
  and a frame raising two questions with one answered stayed unresolved.
- The torn-line repair. It is more aggressive than its trigger and could not be turned into a way of
  removing an inconvenient entry.

## The standing rule

A finding is not closed by a fix. It is closed by a fix **and** a scenario that fails without it.
`tools/verify.py` runs the whole suite, so a regression is a red build rather than a discovery on
cut day.
