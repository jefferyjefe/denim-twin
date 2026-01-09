# External images (priors / pretraining only — never paired data)

`manifest.jsonl` is maintained by `tools/harvest_images.py` (run locally or by the hourly
cloud routine). Sources: Openverse (all CC licenses) and Wikimedia Commons (free licenses
only). Each record keeps license + attribution — respect them in any release.

Download locally: `python tools/harvest_images.py --download 500` → `images/` (gitignored).
Search results are noisy (book scans, people wearing jeans, etc.); filter with the
segmentation model before using anything for training.
