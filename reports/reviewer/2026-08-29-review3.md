# Review 3 (local adversarial agent) — 14 findings, all addressed same day; tests adopted as tests/test_review3_*.py

| # | sev | finding | fix |
|---|---|---|---|
| 1 | high | LOO leak: excluded pair's own after-wash photo stayed in the unpaired pool | `denimtwin/prior.py` (LOO over both pools); unpaired pool drops pairs with a paired run and honours exclude.txt |
| 2 | high | mm/px mixup: NOTE printed mm, fit_fringe divided by px waist | NOTE prints px (+ scale separately); fit_fringe skips legacy mm notes |
| 3 | high | interval lo/hi in mm vs median in px; real==median on non-prior runs | px everywhere; real omitted when it would be the median |
| 4 | high | `--state` only passed with the prior → after_cut pairs labelled after_wash | batch always passes `--state` |
| 5 | high | manual landmarks never transformed after crop/rotation | transformed with the same rotation; snapped to the mask edge |
| 6 | med | coin detector on cropped image, no mask, weak acceptance | detection inside run_pair with the garment mask; requires mask; edge support ≥0.5 (gradient-based); exit 1 when rejected |
| 7 | med | bench refreeze silent / empty baseline passes | unknown pairs fail; refreeze over regressions needs `--force` |
| 8 | med | hem_chamfer diluted by waist/hip columns | columns restricted to where the real garment exists below the cut |
| 9 | med | consent bypass (`[x]` anywhere) | `consent_ok`: the ticked box on its own line |
| 10 | low | pooled sd for intervals | LOO per-state sd |
| 11 | low | grid detector confident on noise | requires axes agreement and SNR ≥ 6, else `mm_per_px: null` |
| 12 | low | coin_key gaps (€2, AUD, US 50c) | fixed |
| 13 | low | modification ranges unchecked | range asserts |
| 14 | low | template.fit "IoU" was 1−loss | returns a real IoU |
Bench baseline refrozen (`--force`) because the hem metric definition changed; `experiments/pairs/REPORT.md` attached.
