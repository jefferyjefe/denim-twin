# Pair harvest, this step — three unsearched segments, one real pair, and why text evidence is not enough

EXP_0005 declared the found-pair channel exhausted at 32 tutorial pages → 6 cut pairs + 1 fray pair.
That was one search strategy: English, German and French craft blogs. This pass widened it. The
Romance-language and Ibero-American segment was searched properly for the first time — 22 queries
across Spanish, Brazilian Portuguese, Italian and Romanian, ~90 URLs surfaced, ~45 pages read.

**Nothing in that segment produces a new scored pair.** Three pages were worth examining and all
three fail, but the failures are informative and one of the images is not a failure at all.

## The one thing worth having

`elartedelascosasnimias.blogspot.com/2012/08/diy-convierte-tus-antiguos-pantalones.html`,
image `IMG_5552.jpg` — **1600×1200, a whole pair of raw-edge cut-offs laid flat on a plain quilted
bedspread, shot from directly above, unworn, entire garment in frame, no text overlay, individual
frayed threads clearly resolved.** The waistband spans roughly 1370 px.

That last number is the point. EXP_0016 established that hem roughness needs **600–1000 px of
waistband**; the seven scored pairs give **241–389 px**, which is why EXP_0025 found 6 of 7 real
frayed hems reading exactly zero and why every fray number in this project is a diagnostic rather
than a measurement. This image clears that threshold by a wide margin.

It is **not a pair** — the page has no photograph of the uncut jeans, the author says so. So it
cannot enter the bench. It belongs in the **unpaired fray channel** (`tools/fringe_unpaired.py`,
`data/external/unpaired_candidates.jsonl`), which is where `f542c57cec`'s after-wash photo already
sits for the same reason. Licence is **unstated** on the host blog; treat as all-rights-reserved,
research use only, derived numbers only — the policy in `data/external/README.md`.

## The other two, and why they fail

- `fashionyfacil.blogspot.com/2012/08/customiza-un-short-de-jean-o-denim.html` — the **before**
  photo is genuinely usable: 798×532, whole jeans flat on a tiled floor, from above, unworn, entire
  garment in frame (rotated ~90°, which the pipeline uprights). The **after** photo is cropped: the
  garment runs off the bottom and right edges of the frame, which `run_pair.sane()` refuses for an
  after photo ("garment touches the frame bottom"). Good before, unusable after → **partial**. The
  legs also lie touching in the before shot, the condition that sends `autolm` to its
  `prior_legs_touching` crotch fallback — the same failure mode as `4bfef03bd7`.
- `viajantejeans.wordpress.com/2010/12/13/fazendo-um-hot-pants-ou-short-desfiado/` — `finalizado.jpg`
  is a real whole-garment raw-edge flat-lay, but on a **chevron-patterned quilt** with a "Pronto!"
  text overlay, and at 640×480. The repository already rejects one pair for a patterned backdrop
  (`d52a3ff876`) and one for text overlay (`f542c57cec`). The two frames offered as `before` and
  `after_cut` are close-ups of a single leg. **Reject.**

## The Nordic / Slavic / East Asian segment, searched for the first time

~20 query variants across Polish, Russian, Ukrainian, Czech, Swedish, Norwegian, Danish, Finnish,
Turkish, Japanese and Korean; ~120 URLs surfaced, ~25 read. Four candidates, and the two I could
check by eye both fail:

- `byduhn.com/diy-shorts-saadan-genbruger-du-dine-gamle-jeans/` (Danish) — the only page in the whole
  sweep whose written method is *lay the trousers flat on the floor and measure both outer sides*,
  which is exactly this project's geometry, and a genuinely raw unfinished edge. **The photographs do
  not do what the prose says.** `IMG_0879` is the jeans **folded** into a rectangle on a patterned
  rug; `IMG_0888` is a close crop of two legs mid-cut. Neither is a whole-garment flat lay. There is
  also no wash step at all — the fraying is done by hand. **Reject.**
- `galant-girl.livejournal.com/246720.html` (Russian) — structurally the best lead anyone found: one
  garment, a raw torn edge, photographed **before and after a described machine wash** ("on the
  harshest programme at the highest spin"), which is category (a) and the thing the project has
  exactly one of. Against it: images served at ~820 px, so the waistband lands well under the
  600–1000 px EXP_0016 needs; the `imgprx.livejournal.net` URLs return **403** to any direct request,
  so the after-wash frame is not retrievable outside a browser session; and the edge is **hand-torn**,
  a different fray mechanism from the scissor cuts in the bench. **Worth a human's five minutes**, not
  ingestible as it stands.
- `adaras.se/diy-blekta-slitna-jeansshorts/` (Swedish) — before, cut and post-wash frames at 1200 px,
  but the garment is **chlorine-bleached** between them, which changes the fabric appearance
  drastically and makes it useless for a fray or colour model. Marking is done with the jeans worn.
- `bengilisular.wordpress.com/.../diy-kot-sort-nasil-yapilir/` (Turkish) — plain unstyled camera
  photos, right register, but the after is **cuffed** (so it cannot fray), at least two frames have
  the garment folded leg-over-leg, no wash, 480×640. **Reject.**

Deliberately excluded and worth recording: `k2j-web.com/howto-cutoff-denim/` (Japanese) is the best
raw-edge-plus-wash source seen anywhere — one vintage Levi's 630, **a ruler in frame**, sandpaper
fraying, an explicit wash step, originals at 5–7 MB. It is excluded only because the result is
ankle-length cut-off *jeans*, not shorts. **If the shorts requirement is ever relaxed for
cut-placement or fray work, start there.**

## Two structural findings, which outlast the individual pages

1. **The dominant failure mode is not "no before photo" — it is "the before photo is on a person."**
   Across all eleven languages in this sweep, tutorials tell the reader to *put the jeans on* and mark
   the length in front of a mirror, and then photograph that step. The geometry this project needs is
   not a photographic accident it is missing; it is contrary to how the genre is written.
   `CONTRIBUTING_PAIRS.md` already asks for a flat lay, and this says why that ask is load-bearing
   rather than a nicety.
2. **Korean is unreachable through this search tool.** Naver Blog and Tistory are effectively
   unindexed here; five Korean query shapes returned wikiHow, TikTok discovery pages and stock
   photography. The floor-level flat-lay geometry is very likely there and would need Naver's own
   search to reach.

## The non-blog segment — and it is the only one that yielded anything

All 32 existing records are `source_type: blog`. Forums, Q&A sites and user-submitted craft-project
sites had never been searched. ~90 pages parsed, ~2,500 Reddit posts machine-screened by title, 20
photographs inspected visually. **This is the segment that produced results**, and the reason is
format: *user-submitted step-by-step craft-project sites are the only non-blog format that behaves
like a blog tutorial.* Reddit and social produce one photo of a finished item, usually worn.

Three candidates, all verified by eye:

- **`cutoutandkeep.net/projects/no-sew-jeans-into-shorts` — a genuine before/after pair, the only one
  found in this whole sweep.** Black bootcut jeans flat on carpet from above, whole garment, unworn;
  the after is the same garment (the `Kickflare` waistband script matches across frames) with a
  **raw** cut edge, same setup. Against it: 800×600, the before is badly underexposed, and both
  frames have **other denim items in shot** at the corners, which is what SAM's coarse pick goes
  wrong on. Waistband ≈350 px in the before, ≈500 px in the after — under the 600 px fray floor.
  **Useful for cut placement, not for fray.** No wash.
- **`cutoutandkeep.net/projects/diy-cutoff-shorts-wit-flair` — a labelled "Before wash" / "After
  wash" pair of the SAME raw-edge cutoffs**, each panel a clean whole-garment flat-lay from above,
  fringe clearly developed in the right panel, text confined to the top margin. This is category (a),
  the capture the whole fray programme currently rests on one garment for. Against it: it is a
  side-by-side collage (though `run_pair.split_collage` exists precisely for that), the ground is a
  **patterned** yellow sheet — the failure mode that got `d52a3ff876` rejected — and at 800×520 each
  panel gives ≈290 px of waistband, so it is **still below the fray floor**. It shows the fray
  developing; it cannot measure it.
- **`instructables.com/Up-Cycle-Jean-Shorts/` — 1600×1200, and the only candidate anywhere in this
  sweep with an explicit open licence (CC BY-NC-SA 4.0).** A whole-garment raw-edge flat-lay plus a
  close-up of the cut edge with individual white weft threads and shed threads on the carpet clearly
  resolved — exactly the hem close-up `CONTRIBUTING_PAIRS.md` asks for. No coin or ruler, no wash,
  and no before photo, so it is a **raw-edge reference**, not a pair.

Two traps this segment set, both invisible from page text and both caught only by looking:
`cutoutandkeep.net/projects/denim-cutoffs` reads as a clean win, but its step-1 garment and its
step-2/3 garment are **different pairs of jeans**. `/r/malefashionadvice/comments/h6if0/` has 16
captioned images, a tape measure in frame, and jeans on the floor — and the finished shorts appear
**only worn**.

Dead ends worth not re-walking: Craftster's forum now 302s to another site and its Photobucket images
are gone; Kollabora is defunct; BurdaStyle blocks crawlers; Reddit is structurally wrong for this.
Cut Out + Keep's other denim categories and the Instructables search index are the two wells worth
returning to.

## A methodological finding, and it matters more than the pages

The search agent's image judgements were made from **filenames, alt text, captions and position in
the step sequence**, because `WebFetch` returns a page as markdown and cannot see pixels. It flagged
this itself and capped every confidence at "low". It was right to: across the eleven images actually
downloaded and viewed, **five of eleven role assignments were wrong** —
`fashionyfacil_afterwash` is a close-up of scissors cutting a folded leg, not a washed garment;
`viajante_before` is a close-up of one leg being marked, not the uncut jeans; `viajante_aftercut`
likewise. Four of those five were the images their lead rested on, and in the Danish case the page's
own prose said the right thing while its photographs did not.

The project's own CLIP tagger (`validate_pairs.py`) does see pixels and was run on all seven. It also
gets it wrong, in the direction EXP_0005 already measured: it scored `fashionyfacil_afterwash` as
`hem_closeup` correctly (0.64) but `viajante_before` as `hem_closeup` at only 0.51 against
`whole_garment_flat` 0.44 — a coin flip on an obvious close-up.

**So: no page enters this repository on text evidence.** Download the images and look at them. That
is one line of work per candidate and it is the difference between a real pair and a plausible one.

## What to do with this

Nothing is ingested. `data/external/pairs.jsonl` is untouched, and deliberately: a record that
validates as `usable` is picked up by `run_pairs_batch.py`, which regenerates `experiments/pairs` and
invalidates every report derived from it (the EXP_0038 cascade). Ingesting is a decision, not a
side effect.

To ingest the unpaired fray sample (the recommended one):

    # append the record to data/external/unpaired_candidates.jsonl, then
    .venv/bin/python tools/ingest_unpaired.py
    .venv/bin/python tools/fringe_unpaired.py

To ingest the fashionyfacil before/after as a `partial` record for the manifest, append it to
`data/external/pairs.jsonl` with the after image marked, then
`tools/tutorial_pairs.py --fetch` and `tools/validate_pairs.py`. Check the resulting status is
**not** `usable` before running any batch, or budget for regenerating the bench and every report.
