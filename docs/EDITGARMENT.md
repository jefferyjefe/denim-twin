# EditGarment: a local adapter, and why its samples never touch a physical claim

EditGarment is a garment-**editing** dataset: each sample is a source image, an instruction, and an
edited image produced from the source by an image model. It is distributed under an
access-controlled process — the authors publish a request form and a usage agreement, and you
receive the files only after going through it.

**This repository does not distribute the dataset, does not mirror it, and does not automate,
script around, or bypass its access process.** There is no download in `tools/editgarment_adapter.py`
— no URL to the data, no fetch path, no network import at all; `tests/test_editgarment_adapter.py`
reads the tool's own imports and fails if one appears. If you want the dataset, go through the
authors' official access process yourself. Nothing here will do it for you, and nothing here should
be pointed at a mirror of it either: the terms you agreed to are the terms that govern your copy.

The adapter reads files **you have already legally obtained and placed on your own disk**, checks
their shape, and writes provenance records. That is all it does.

---

## 1. The scientific point: these are synthetic edits, and they are excluded

Every record this adapter emits carries, unconditionally:

```json
"pair_type": "synthetic_edit",
"excluded_from_physical_evaluation": true,
"exact_garment": "known_different"
```

The exclusion is not a policy preference. It is the difference between two entirely different
claims:

* A **real** before/after pair in this project is a photograph of a garment, and a photograph of
  that same garment after it was cut and washed. The difference between the two frames was produced
  by scissors, water and a tumble dryer. Measuring it tells you something about cloth.
* An **edit** sample's "after" frame was produced by a model asked to imagine what the change would
  look like. The difference between the two frames was produced by a prior over pixels. Measuring it
  tells you something about that model.

Score a prediction against the second and report the number beside the first, and this repository
would claim to have validated the physics of fraying when what it actually validated was a renderer
agreeing with another renderer. The failure is silent — the number has the same units, the same
range, and the same look on a plot. That is exactly the class of defect the exclusion flag exists to
make impossible: a machine-readable field, set by the adapter and not by the input, that any
physical-accuracy evaluation can filter on before it computes anything.

**What these samples are legitimately good for:** appearance and instruction priors, vocabulary for
describing edits, sanity-checking segmentation on garment imagery, qualitative figures. Anything
whose claim is about *images*.

**What they are never good for:** fringe depth, raw-edge behaviour, post-wash geometry, hem
placement, or any other number this project reports as a property of a garment.

### Why `exact_garment` is `known_different` and not `not_verified`

`exact_garment` is this repository's tri-state for "is the after-frame the same physical garment as
the before-frame": `verified` / `not_verified` / `known_different`.

`not_verified` means *we have not established this yet* — it leaves the door open for a later check
to promote the record to `verified`. For a generated frame, no such check exists, and none could:
the edited pixels were never cloth, so there is no second physical garment to be identical to, and
no photograph anyone could produce that would settle it. Recording `not_verified` would file a
permanent impossibility as a pending task, and pending tasks get closed by someone in a hurry.
`known_different` states the truth and closes it.

---

## 2. The local layout the adapter expects

Keep your copy of the dataset **outside this working tree**, so that no automated commit can ever
sweep it into a repository that is not licensed to redistribute it. Point `--root` at it:

```
<root>/
  editgarment_manifest.json        # you write this, from your access grant
  images/
    eg_0000_source.png
    eg_0000_edited.png
    eg_0001_source.png
    eg_0001_edited.png
```

Image paths in the manifest are **relative to `<root>`**, must stay inside it, and are never copied,
moved or rewritten — the adapter opens each one, records its dimensions and a SHA-256 digest, and
closes it. Only derived numbers leave your disk, which is the same rule
`data/external/README.md` applies to every other image channel in this project.

### `editgarment_manifest.json`

You write this file yourself, out of the access grant you were given. The adapter refuses if any
field is missing, because a rights field invented by a tool is worth nothing.

```json
{
  "dataset": "EditGarment",
  "source_url": "https://<the page you obtained access through>",
  "retrieved_at": "<ISO-8601>",
  "generation_method": "<how the edited frames were produced, per the dataset's own paper>",
  "rights": {
    "license_id": "<the identifier or name of the agreement you accepted>",
    "license_url": "https://<where those terms are published>",
    "attribution": "<the attribution the agreement requires>",
    "redistributable": false,
    "derivatives_allowed": true,
    "commercial_use_allowed": false
  },
  "samples": [
    {
      "sample_id": "eg_0000",
      "instruction": "<the edit instruction shipped with the sample>",
      "edit_type": "length",
      "source_image": "images/eg_0000_source.png",
      "edited_image": "images/eg_0000_edited.png"
    }
  ]
}
```

Rules the adapter enforces, and refuses the **whole run** over — never a partial file that looks
complete:

| Field | Requirement |
| --- | --- |
| `source_url`, `license_url` | `http(s)` URLs |
| `retrieved_at` | starts with an ISO date, `YYYY-MM-DD` |
| `generation_method` | non-empty; it becomes part of `provenance.method` |
| `rights.*` | all six fields present; the three permission fields are real booleans |
| `rights.redistributable` | must be `false` — this adapter is for an access-controlled dataset and will not emit records asserting a right to redistribute it |
| `sample_id` | `[A-Za-z0-9._-]`, unique across the manifest |
| `instruction` | present, long enough to describe an edit |
| `source_image`, `edited_image` | relative to `<root>`, inside it, present, and readable as images |

---

## 3. Running it

The acknowledgement is **required and off by default**:

```
python tools/editgarment_adapter.py \
    --root /somewhere/outside/this/repo/editgarment \
    --out  /somewhere/outside/this/repo/scratch/editgarment_records.jsonl \
    --i-have-dataset-access
```

`--i-have-dataset-access` (or `DENIMTWIN_EDITGARMENT_ACCESS=1`, which must be exactly `1`) is you
stating that you hold access to EditGarment under its official process and accept the terms it was
granted under. Without it the tool prints the refusal, points you at that process, writes nothing,
and exits non-zero. An acknowledgement that defaults to "yes" acknowledges nothing, which is why the
refusal is the default rather than a warning.

Other options: `--manifest NAME` (a different manifest file name inside `--root`), `--format
{jsonl,json}` (one record per line, the default, or a JSON array), `--limit N`, `--overwrite` (the
tool will not silently replace an existing output file).

`--out` is required, has no default, and may not be inside this repository's tracked trees
(`data/`, `reports/`, `experiments/`, `docs/`, `protocol/`, `models/`). Records derived from a gated
dataset do not belong where the next `git add -A` would publish them.

Exit codes: `0` records written · `2` refused for want of the acknowledgement · `3` the local files
are not the shape the adapter accepts. Nothing is written in either non-zero case.

---

## 4. What a record looks like

```json
{
  "record_id": "editgarment_eg_0000",
  "pair_type": "synthetic_edit",
  "excluded_from_physical_evaluation": true,
  "exclusion_reason": "the edited frame is generated, not photographed: ...",
  "exact_garment": "known_different",
  "exact_garment_reason": "the edited frame depicts no physical garment, ...",
  "rights": { "...": "copied verbatim from your manifest" },
  "provenance": {
    "source": "EditGarment",
    "source_url": "...",
    "retrieved_at": "...",
    "method": "local adapter tools/editgarment_adapter.py over a copy obtained by the operator ..."
  },
  "sample": {
    "sample_id": "eg_0000",
    "instruction": "...",
    "edit_type": "length",
    "source_image": {"path_relative_to_root": "...", "width": 0, "height": 0, "sha256": "..."},
    "edited_image": {"path_relative_to_root": "...", "width": 0, "height": 0, "sha256": "..."}
  }
}
```

Two absences are deliberate:

* There is **no `training_eligible` field**. Whether a sample may be trained on is a decision made
  downstream against a stated policy, over the rights fields and the exclusion flag. A record that
  certifies its own eligibility has removed the only step where anyone reads the licence.
* The `pair_type`, exclusion and `exact_garment` values are **not read from the manifest**. They are
  constants in the adapter. A local file cannot talk it into emitting a record that reads as
  physical evidence, and the test suite proves that by feeding it a manifest which tries.

---

## 5. Related

* `data/external/README.md` — the rule this adapter follows: images stay local, only derived numbers
  enter the repository.
* `tests/test_editgarment_adapter.py` — hermetic; every fixture is synthesised in `tmp_path`. No
  file from the real dataset is required, and the suite runs identically on a machine that has never
  had access to it.
