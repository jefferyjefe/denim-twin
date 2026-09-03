# The three rehearsals no verification profile can perform

`tools/verify.py --profile full` is the strongest claim the software can make about itself. It
runs on a machine with no garment on it. Every check in it is a statement about code and committed
artefacts; not one of them has touched cloth, a camera, a phone, a washing machine or a pair of
shears.

That is not a gap to be closed by writing more tests. It is the boundary between two different
kinds of claim, and this file exists so that the boundary is written down in the same place as the
work that has to cross it. Nothing here may be recorded as passed unless a person actually did it.

Each rehearsal below states, in this order: what must already be true, what the operator does,
what evidence should exist afterwards, what counts as a pass, what counts as a fail, how to
recover from the fail, and the exact command that reports the state.

Throughout: **use a scratch garment directory**, never the pilot one.

    export PILOT_GARMENTS=/tmp/rehearse
    tools/pilot.py new

`R2` and `R3` involve a garment. `R1` does not; it can be done at a desk.

---

## R1 — the phone, over the connection it will actually be used on

The self-test drives the same module functions the phone calls, and since the confirmation model
was unified it goes through the same claim resolution. **It does not press the buttons.** Every
defect in `ui/app.js` found so far was found by reading it, twice by an attacker and once by a
test that spoke real multipart to a real server — never by the phone itself, because the phone has
never been used.

### Prerequisites
- a scratch garment created as above, taken as far as the rig freeze and the questionnaire;
- the phone and the machine on the same local network, nothing exposed beyond it;
- `tools/pilot.py serve <GARMENT> --lan`, and the URL it prints, which carries the token.

### Operator actions
1. Open the printed URL on the phone. Sign in as the operator when asked who is operating.
2. Take and upload one frame for a shot that raises a human claim, from the phone's camera.
3. Read the claim card. Confirm the claim from the card, against the photograph, as a second step.
4. Reload the page mid-session. Confirm the same claim a second time.
5. Put the phone in flight mode for thirty seconds and bring it back.
6. Press the browser back button after a submission and resubmit the same form.
7. Open a second tab on the same session and submit from the stale one.
8. Copy the URL without its token and open it.
9. Copy the URL with its token onto a second device and use it.
10. Reach a blocker deliberately — omit a required subject — and run the remedy the phone prints,
    on the CLI, verbatim.
11. Visit the cut-day claims (`legs_cut_separately`, `offcuts_retained_labelled`,
    `cut_marks_verified`, `cut_out_of_model_acknowledged`) and confirm that each is reachable and
    confirmable from the phone, not only from the CLI.

### Expected evidence
Every write attributed to a named operator; one `capture` entry and one later, separate
`human_verification` entry per confirmed claim; no entry attributed to the empty string.

### Pass
- No action recorded twice from a refresh, a back-button resubmit, a stale tab or a reconnect.
- The tokenless URL is refused.
- Every claim card renders its claim text before it offers the button.
- The remedy the phone printed was accepted by the CLI parser and cleared the blocker it named.
- The folded state after the session is one a CLI-only session could also have produced.

### Fail
Any duplicate record, any unattributed write, any card that offers approval without showing what
is being approved, any printed remedy the parser rejects, any screen that cannot be recovered from
without restarting the server.

### Recovery
The log is append-only: a wrong record stays. Record what happened with
`tools/pilot.py deviation <GARMENT> --kind protocol --field <what departed> --reason '<what
happened>'`, and — because this is a scratch garment — start a fresh one for the real session.

### Command that reports state
    tools/pilot.py status <GARMENT>
    tools/pilot.py claims <GARMENT> --pending

---

## R2 — the rig, with real calibration and real capture files, and no cut

### Prerequisites
- the rig physically built: backdrop, lights, camera mount, the printed ChArUco board;
- the board printed and its squares measured with a rule over at least four whole squares;
- a garment that is NOT the pilot garment — any pair of jeans, to be photographed and not cut;
- the equipment and rig checklists: `protocol/pilot/CHECKLIST_EQUIPMENT.md`,
  `protocol/pilot/CHECKLIST_RIG.md`.

### Operator actions
1. `tools/pilot.py setup <GARMENT>` and answer every field from the room, not from memory. There
   are no defaults; that is deliberate.
2. Shoot the seventeen `RIG.*` frames and ingest them.
3. Shoot a representative sample of the before-state arm, including at least: one whole-garment
   overhead, one oblique, one macro that needs the rule, one hem loop position, and one motion
   clip.
4. Deliberately produce a bad frame — out of focus, or with the board out of plane — and ingest it.
   Read the quality feedback. Re-take it and ingest the retake.
5. Upload the largest single file the protocol expects (a motion clip) through the phone.
6. Restart the server mid-upload and re-run the same upload.
7. Fill the machine's storage headroom to the point where the next upload would fail, and attempt
   it. Read what happens.
8. Export the evidence packet and read it: `tools/pilot.py packet <GARMENT>`.

### Expected evidence
A frozen rig with a hash on every photograph taken under it; a `qa_result` for every frame with
per-check outcomes; a recorded RETAKE for the bad frame and a later PASS for its replacement; the
interrupted upload either absent or complete, never half-ingested.

### Pass
- Every rig field in the log is a number or a sentence somebody read off the equipment.
- The bad frame was refused with a message that named what to change, and the retake passed.
- The interrupted upload left no partial photograph in the manifest.
- The storage-exhaustion attempt produced a refusal, not a corrupted file and not a silent success.
- `tools/pilot.py precut` refuses, and every blocker it names is a frame that genuinely was not
  taken. **No frame that was taken is reported missing.**

### Fail
A field filled from a default; a bad frame accepted; a partial upload recorded as a photograph; an
upload failure that leaves the log unreadable; a blocker naming evidence that is on disk.

### Recovery
`protocol/pilot/RECOVERY.md` is the generated procedure and takes precedence over anything here.
The phone's own camera roll is the recovery source for any frame the log lost.

### Command that reports state
    tools/pilot.py status <GARMENT>
    tools/pilot.py precut <GARMENT>          # must refuse; read WHY
    tools/pilot.py hem <GARMENT>

---

## R3 — a sacrificial garment through the whole lifecycle, stopping before each irreversible act

**Do not begin R3 until every decision in `docs/PILOT_OWNER_DECISIONS.md` is frozen.** Several of
them change what has to be photographed, and one of them — the cut line — changes which regions
leave with the offcut. A rehearsal shot against an unfrozen plan rehearses the wrong session.

The garment for R3 is sacrificial: a pair of jeans whose destruction costs nothing. It is not the
pilot garment and its numbers are not results.

### Prerequisites
- R1 and R2 both performed and passed, by a person, with their evidence kept;
- every owner decision frozen and recorded by the command that freezes it;
- a second person available, who is not the operator, for the marks verification;
- a washing machine and the wash settings the protocol will use.

### Operator actions, with the three deliberate stops
1. Full before-state capture. Then **STOP**.
2. `tools/pilot.py cutspec <GARMENT> --inseam <the frozen value>` and
   `tools/pilot.py packet <GARMENT>`; mark the garment; shoot the `marked` state.
3. `tools/pilot.py precut <GARMENT>`. **STOP HERE regardless of what it prints.** A second person,
   who did not shoot the session, reads the evidence packet and the gate's output and says out
   loud whether the evidence supports cutting. Record their verification.
4. Cut, one leg at a time. Label both offcuts. Record the achieved lengths with
   `tools/pilot.py cut-performed`, before anything goes near water.
5. Shoot the twenty `IMMEDIATE_AFTER.*` frames and the ten `OFFCUT_BEFORE.*` frames. These are the
   only frames in the plan that cannot be re-taken later at all: the cloth they are of stops
   existing when the water is added.
6. `tools/pilot.py wash <GARMENT>` to record the planned settings, then
   `tools/pilot.py gate <GARMENT> ready_to_wash`. **STOP.** Independent inspection again.
7. Wash. Record the actual settings, reading each one off the machine.
8. Post-wash re-measurement and the post-wash and offcut-after arms.
9. `tools/pilot.py finalize <GARMENT>`. **STOP.** Independent inspection of the manifest.

### Expected evidence
One append-only log that folds to a session in which every gate was ready at the sequence position
where the act it guards was recorded, and an evidence packet a second person read at each of the
three stops.

### Pass
- All three gates opened on their own evidence, with zero blockers, before their act was recorded.
- The second person's verification is in the log at each stop, attributed, and distinct from the
  operator's own records.
- The pre-wash frames in step 5 exist and were taken in that window.
- No deviation was needed to reach a ready verdict. A rehearsal that needed one has found
  something, and what it found belongs in the shot plan or in this file, not in a waiver.

### Fail
Any gate that had to be argued past. Any frame from step 5 that had to be filled after the wash —
that is the case `captures.state_order` now refuses, and if the rehearsal reaches it, the plan or
the runbook is asking for evidence in an order a person cannot supply.

### Recovery
There is none for the cut and none for the wash. That is the whole reason for the stops. Before
each stop everything is recoverable; after it, nothing is.

### Command that reports state
    tools/pilot.py precut    <GARMENT>
    tools/pilot.py gate      <GARMENT> ready_to_wash
    tools/pilot.py finalize  <GARMENT>
    tools/pilot.py claims    <GARMENT> --pending

---

## Recording that a rehearsal happened

There is deliberately no command that marks a rehearsal complete, and no field in any gate that
reads one. A rehearsal is a claim about the physical world made by a person, and the only honest
record of it is a person writing down what they did and what they saw, with the evidence beside
it. Put that record next to the scratch garment's log and keep both.

What must never happen is a rehearsal recorded as passed because the software could not tell the
difference. Nothing in `tools/verify.py`, in either profile, distinguishes a rehearsed system from
an unrehearsed one, and it does not pretend to: read its closing paragraph, which says what a pass
proves and stops there.
