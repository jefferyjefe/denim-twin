# Literature Map — denim-twin

Scope: prior work relevant to reconstructing a *specific* pair of denim jeans from guided phone captures and predicting its appearance after a user-specified cut and one standardized wash (see `CHARTER.md`). Every entry below was verified against a live URL on 2026-08-28 (entries 14–15: 2026-08-29). Component tags: capture / segmentation / geometry / material / cutting / fray / rendering / uncertainty / eval.

## 1. Overview table

| # | Paper | Year | Venue | URL | One-line contribution | Informs | Code |
|---|-------|------|-------|-----|-----------------------|---------|------|
| 1 | Image2Garment: Simulation-ready Garment Generation from a Single Image (Can, Ackermann, Nakayama, ..., Wetzstein) | 2026 | arXiv 2601.09658 | https://arxiv.org/abs/2601.09658 | Feed-forward pipeline: VLM predicts material composition/fabric attributes from a photo, a small predictor maps them to simulator physics parameters; introduces FTAG (16k tag-annotated images) and T2P (1,254 fabrics with measured physics) datasets | material, geometry | Project page https://image2garment.github.io/ lists "Code (soon) / Data (soon)" — not released as of 2026-08-28 |
| 2 | Dress-1-to-3: Single Image to Simulation-Ready 3D Outfit with Diffusion Prior and Differentiable Physics (Li et al.) | 2025 | ACM TOG / SIGGRAPH 2025 | https://arxiv.org/abs/2502.03449 | Image → coarse sewing pattern → multi-view diffusion → pattern refined by differentiable cloth simulator; outputs separable, simulation-ready garments | geometry, material | No code link on project page https://dress-1-to-3.github.io/ |
| 3 | Single View Garment Reconstruction Using Diffusion Mapping via Pattern Coordinates (DMap; Li, Ren et al.) | 2025 | SIGGRAPH 2025 Conf. Papers | https://arxiv.org/abs/2504.08353 | Diffusion prior in UV pattern space + pixel↔UV↔3D mapping model; jointly optimises 3D mesh and 2D pattern to match image | geometry, segmentation | Yes: https://github.com/liren2515/dmap |
| 4 | ChatGarment: Garment Estimation, Generation and Editing via Large Language Models (Bian et al.) | 2025 | CVPR 2025 | https://arxiv.org/abs/2412.17811 | Fine-tuned VLM emits GarmentCode JSON sewing patterns from images/text; supports instruction-based edits, patterns drape to simulatable 3D | geometry, cutting (pattern-level edits) | Yes: https://github.com/biansy000/ChatGarment |
| 5 | Deep Fashion3D: A Dataset and Benchmark for 3D Garment Reconstruction from Single Images (Zhu et al.) | 2020 | ECCV 2020 | https://arxiv.org/abs/2003.12753 | 2,078 scanned 3D garment models (563 instances, 10 categories) with feature lines, body pose, multi-view real images; adaptable-template baseline | geometry, eval | Yes (dataset + V2 release): https://github.com/GAP-LAB-CUHK-SZ/deepFashion3D |
| 6 | DeepFashion2: A Versatile Benchmark for Detection, Pose Estimation, Segmentation and Re-Identification of Clothing Images (Ge et al.) | 2019 | CVPR 2019 | https://arxiv.org/abs/1901.07973 | 801K clothing items with masks, dense landmarks, bboxes, 873K commercial–consumer pairs; Match R-CNN baseline | segmentation, capture | Yes (dataset): https://github.com/switchablenorms/DeepFashion2 |
| 7 | Segment Anything (Kirillov et al.) | 2023 | ICCV 2023 | https://arxiv.org/abs/2304.02643 | Promptable zero-shot segmentation foundation model trained on SA-1B (1B masks) | segmentation | Yes: https://github.com/facebookresearch/segment-anything |
| 8 | Adaptive Tearing and Cracking of Thin Sheets (Pfaff, Narain, de Joya, O'Brien) | 2014 | ACM TOG / SIGGRAPH 2014 | http://graphics.berkeley.edu/papers/Pfaff-ATC-2014-07/ | Adaptive remeshing so cracks/tears in thin sheets (incl. cloth) propagate along arbitrary paths with local detail | cutting, fray (macro-scale) | Yes, via ARCSim: http://graphics.berkeley.edu/resources/ARCSim/ |
| 9 | Estimating Cloth Simulation Parameters from Video (Bhat, Twigg, Hodgins, Khosla, Popović, Seitz) | 2003 | SCA 2003 | https://homes.cs.washington.edu/~seitz/papers/bhat-sca03.pdf | Fits stiffness/bending/damping of a cloth simulator to video of real swatches using a fold-matching metric and simulated annealing | material, capture (motion clip) | No public code |
| 10 | Fitting Procedural Yarn Models for Realistic Cloth Rendering (Zhao, Luan, Bala) | 2016 | ACM TOG / SIGGRAPH 2016 | https://escholarship.org/uc/item/2fw2w3gs | Automatically fits fiber-level procedural yarn models (ply/fiber twist, migration, flyaways) to CT measurements for realistic cloth rendering | fray, rendering | Yes: code + microCT data via https://replicability.graphics/papers/10.1145-2897824.2925932/index.html (Cornell ctcloth project) |
| 11 | Fiber-level Woven Fabric Capture from a Single Photo (Li, Shen, Sun, ..., Marschner, Hašan, Wang) | 2024 | arXiv 2409.06368 (cs.GR) | https://arxiv.org/abs/2409.06368 | Neural prediction + differentiable rasterization/path tracing recover procedural woven-fabric geometry and optical parameters from one microscope photo | material, rendering | Not mentioned on arXiv page |
| 12 | AnyDoor: Zero-shot Object-level Image Customization (Chen et al.) | 2024 | CVPR 2024 | https://arxiv.org/abs/2307.09481 | Diffusion inpainting with ID extractor + frequency-aware detail extractor to insert a reference object into a masked region while preserving its identity | rendering (neural refinement) | Yes: https://github.com/ali-vilab/AnyDoor |
| 13 | A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification (Angelopoulos, Bates) | 2021 | arXiv 2107.07511 | https://arxiv.org/abs/2107.07511 | Tutorial on split conformal prediction: wrap any model to get prediction sets/intervals with finite-sample coverage guarantees | uncertainty, eval | Yes: https://github.com/aangelopoulos/conformal-prediction |
| 14 | Automatic Measurement of Shrinkage Rate in Denim Fabrics After Washing (Talu) | 2021 | Tekstil ve Mühendis 28(123), 191–198 | https://doi.org/10.7216/1300759920212812304 | CCD cabinet + Hough-line measurement of a 500 mm printed square on denim before/after industrial washing; agrees with manual measurement to 0.33–0.5% | material (shrinkage), capture | No code; method fully described |
| 15 | Garment washed jeans: impact of launderings on physical properties (Card, Moore, Ankeny) | 2006 | Int. J. Clothing Science & Technology 18(1), 43–52 | https://doi.org/10.1108/09556220610637503 | Pre-washed / stone-washed / enzyme-treated jeans through 0, 5, 25 home launderings; measures pilling and **edge abrasion** by treatment | fray (edge behaviour), material | No code; paywalled full text |

## 2. Per-paper summaries

### 1. Image2Garment (2026)
Fine-tunes a vision-language model to read material composition, fabric family and structure from a garment photo, then maps those attributes to physical simulator parameters via a lightweight predictor trained on 1,254 measured fabrics (T2P); the result is a simulation-ready garment with no per-instance optimisation.
**Reuse:** the FTAG/T2P idea is exactly our "material" branch — care-label + close-up → (cotton %, elastane %, weight, weave) → bending/stretch parameters; their attribute taxonomy is a good schema for our metadata, and T2P (once released) is a calibration target for our own denim swatch measurements.
**Does not solve:** nothing about cutting, laundering, or fray; parameters are drape-level (stiffness), not the yarn-level properties (twist, yarn count, weft/warp density) that govern fray length; code and data were still "soon" at the time of writing.

### 2. Dress-1-to-3 (2025)
Reconstructs separable, simulation-ready garments from one in-the-wild image by generating a coarse sewing pattern, synthesising multi-view images with a diffusion model, and refining the pattern through a differentiable cloth simulator until renders match the views.
**Reuse:** the "pattern + differentiable physics fitted to multi-view evidence" loop is the right template for our geometry stage, and we have far better evidence (calibrated multi-view flat-lay captures) than they assume.
**Does not solve:** targets generic, category-level garments on a body, not a specific instance's texture/whiskering/fade; no mechanism for editing the pattern after reconstruction; no code released.

### 3. DMap — Diffusion Mapping via Pattern Coordinates (2025)
Learns a diffusion prior over garments in 2D UV pattern space (Implicit Sewing Patterns) and a mapping network that ties image pixels to UV coordinates and 3D positions, enabling joint optimisation of mesh and pattern against a single image; trained purely on synthetic data yet generalises to photos.
**Reuse:** the pixel→UV correspondence is directly what we need to express the user's cut line in canonical garment coordinates and to build the per-pixel difference map; code is public.
**Does not solve:** built for dressed humans, not flat-laid garments; the pattern prior covers common silhouettes, not the specific pocket/seam topology of jeans at the fidelity we need; no material or appearance modelling.

### 4. ChatGarment (2025)
A VLM fine-tuned to emit GarmentCode JSON sewing patterns from an image, sketch or text, and to apply instruction-based edits ("shorten the legs"), after which the pattern is draped into a simulatable mesh.
**Reuse:** GarmentCode's parametric jeans/pants template gives a clean canonical coordinate system, and the "edit as a pattern operation" framing maps to our straight cut / target-inseam input; code is public.
**Does not solve:** reconstruction is category-level (Chamfer-scale accuracy), not mm-accurate for one garment; edits produce a new clean hem, not a raw cut edge; nothing about wash behaviour, fray, or preserving the original photographed texture.

### 5. Deep Fashion3D (2020)
Provides 2,078 3D garment scans (563 real instances, including trousers) with multi-view photos, feature-line annotations and pose; V2 adds registered meshes and 2K textures. Baseline reconstructs single-view garments with an adaptable template.
**Reuse:** a public benchmark with real multi-view photos and ground-truth geometry to sanity-check our geometry stage before our own paired dataset exists; feature lines (hem, seams) match our close-up capture targets.
**Does not solve:** garments are worn/posed rather than flat-laid on a rig; no before/after modification pairs, no material or wash data; denim is a small fraction.

### 6. DeepFashion2 (2019)
Large 2D benchmark (801K items) with per-pixel masks, dense landmarks and commercial–consumer pairs across 13 categories including trousers/shorts, with a Mask R-CNN-based baseline.
**Reuse:** pretraining/fine-tuning data for garment segmentation and landmark detection (hem, inseam, waistband) on phone photos; the consumer-vs-commercial pairs echo our phone-vs-rig domain gap.
**Does not solve:** instance identity across a physical modification; no 3D, no material labels, images are of worn garments in the wild rather than controlled flat-lays.

### 7. Segment Anything (2023)
A promptable segmentation model (points/boxes/masks) trained on SA-1B that transfers zero-shot to new image distributions.
**Reuse:** our segmentation component is essentially solved at the mask level: prompt with the fiducial-derived garment bbox to isolate jeans, pockets, seams and the calibration board across all capture views.
**Does not solve:** semantic naming of parts, sub-millimetre hem boundaries, or the frayed-edge boundary after wash (soft, thread-level edges are outside SAM's crisp-mask regime).

### 8. Adaptive Tearing and Cracking of Thin Sheets (2014)
Simulates fracture in thin elastic sheets by adaptively refining the triangle mesh along crack fronts so tears follow arbitrary, physically driven paths; implemented in ARCSim.
**Reuse:** ARCSim (open source) gives a tested way to introduce a cut into a simulated cloth mesh and to model the loosening of the free edge; the adaptive-remeshing approach is what our cutting component needs at the macro scale.
**Does not solve:** continuum thin-shell model has no yarns, so it cannot produce weft-thread unravelling or the length/density of fray; no laundering forces; ARCSim is unmaintained.

### 9. Estimating Cloth Simulation Parameters from Video (2003)
Fits cloth-simulator stiffness, bending and damping parameters to video of real fabric using a fold-based perceptual metric and simulated annealing, with small static/dynamic swatch experiments as calibration.
**Reuse:** motivates our "short motion clip (lifted and released)" capture; the swatch-calibration protocol is a template for tying denim samples to simulator parameters.
**Does not solve:** 2003-era simulator and metric; no fray, no wash; parameters are for drape not edge behaviour; no code.

### 10. Fitting Procedural Yarn Models for Realistic Cloth Rendering (2016)
Fits a procedural yarn model (ply and fiber twist, cross-section, migration, flyaway fibers) to micro-CT scans so fiber-level cloth can be rendered without storing explicit fiber geometry.
**Reuse:** the flyaway-fiber and ply parameters are the natural vocabulary for a procedural fray model: a raw denim hem is loose weft yarns plus flyaways, which this model already parameterises; code and micro-CT scans are released.
**Does not solve:** describes intact yarn, not the process of yarns pulling free; parameters come from CT, not phone photos; render cost is high for interactive use.

### 11. Fiber-level Woven Fabric Capture from a Single Photo (2024)
Recovers procedural woven-fabric geometry (yarn widths, spacing, twist) and optical parameters from a single microscope photo via a neural initialiser followed by differentiable rasterization and path-tracing refinement.
**Reuse:** closest existing work to "phone close-up → weave/yarn parameters"; a twill-denim variant of their procedural weave model would feed both the fray simulator (yarn count, density) and the renderer.
**Does not solve:** assumes microscope imagery with known lighting, not a phone; no dynamics, cutting or wash; code not indicated.

### 12. AnyDoor (2024)
Diffusion-based object insertion: an ID extractor plus a frequency-aware detail extractor condition an inpainting model so a reference object is placed into a masked region with texture preserved and local lighting/pose adapted.
**Reuse:** a template for our identity-preserving neural refinement — condition on the original capture (identity) and the procedural fray render (structure) and inpaint only the hem band, leaving unchanged pixels untouched by construction.
**Does not solve:** no physical grounding — it will happily hallucinate plausible but wrong fray; no guarantee outside the mask beyond copying; evaluated on semantic identity, not the pixel-level "difference map" fidelity our charter claims.

### 13. Conformal Prediction tutorial (2021)
Explains split conformal prediction: hold out a calibration set, compute nonconformity scores, and derive prediction intervals/sets with a finite-sample coverage guarantee for any black-box predictor.
**Reuse:** gives us the conservative/median/aggressive fray range with a provable coverage claim ("calibrated intervals") on scalar targets — fray length, hem drop, colour shift — using our locked test set; code is public.
**Does not solve:** coverage is marginal, not per-garment; requires exchangeable calibration data (≥ tens of pairs), which our dataset will only reach late in year one; no notion of calibrated *image* intervals.

### 14. Automatic Measurement of Shrinkage Rate in Denim Fabrics After Washing (2021)
A 50 cm square is printed on the denim, photographed in a fixed cabinet before and after washing, and the two side
lengths are recovered by Hough lines; shrinkage is the difference against 500 mm. Reported table over six fabric types
(five samples each): width change −0.2 to −25 mm on 500 mm (**0.04% to 5.0%**), the second measured direction −0.04 to
−1.3%. Automatic vs manual measurement agrees to 0.33–0.5%.
**Reuse:** the only source we could verify that reports *measured* denim shrinkage with a stated method, and it is
essentially our own measurement problem (fiducial + vision + before/after). Its precision (~0.5%) also bounds what any
photo-based shrinkage estimate can claim.
**Does not solve:** it is industrial rope-washing of fabric rolls, not one home laundering of a made-up garment, and it
does not label the two directions warp/weft in the results table. **It does not support the anisotropy our wash model
assumes** (`canon/wash.py`: warp 2% > weft 1%); if anything the larger changes are in the width direction. Our
shrinkage parameters therefore remain unsupported priors — flagged as such in EXP_0013 and in the module docstring.

### 15. Garment washed jeans: impact of launderings on physical properties (2006)
Factorial laundering experiment (0/5/25 cycles) on three garment-wash treatments, measuring pilling and edge abrasion.
Pre-washed jeans pilled most but abraded least at edges; stone-washed abraded most.
**Reuse:** the closest published evidence that *edge* behaviour under laundering depends on the garment's prior wash
treatment — i.e. our fringe prior should eventually be conditioned on wash shade / finish, not just on state. It also
justifies recording `wash_shade` and finish in the garment record, which the schema already does.
**Does not solve:** no dimensional data, no raw cut edges (the edges are finished hems), no imagery, no fray depth.

## 3. Gaps — components with no directly reusable prior work

- **Fray prediction (core gap).** No paper models the transition from a cut continuum edge to loose weft yarns, flyaways and hem roll after laundering. Macro cutting (Pfaff/ARCSim) and static yarn appearance (Zhao 2016; Li 2024) bracket the problem but neither covers the process or its dependence on fabric parameters and wash agitation. This must be built from scratch as a procedural/physical model and validated against our paired data.
- **Wash as a physical process.** No garment-vision work models a laundering cycle (mechanical agitation, shrinkage, colour loss). Textile engineering does measure fabric shrinkage (entry 14) but for industrial roll washing, not one home cycle on a made-up garment, and no source we could verify establishes the warp/weft anisotropy our model assumes. Our single standardized protocol (`protocol/PROTOCOL.md`) is the only lever; the mapping wash → outcome is purely empirical for us.
- **Instance-specific denim material from phone captures.** Image2Garment gives category-level physics from a photo and Li 2024 gives yarn-level structure from a microscope; nothing bridges phone close-ups + care label to yarn-level denim parameters (weight, twill, yarn count, elastane).
- **Flat-lay, rig-calibrated capture.** All garment reconstruction work assumes worn garments; flat-lay with fiducials is simpler but unsupported by existing priors, so geometry will lean on classical multi-view + template fitting rather than DMap/Dress-1-to-3 as-is.
- **Paired before/after garment dataset.** No public dataset contains the same physical garment before and after modification and wash; DeepFashion2 pairs are different photos of the same product, not the same instance transformed. Our ≥50-garment dataset is itself a contribution.
- **Pixel-level identity evaluation and calibrated image-space uncertainty.** Existing editing metrics (CLIP/DINO similarity) do not measure "exactly which pixels changed"; conformal methods cover scalar targets only. We need to define a difference-map metric and restrict calibration claims to scalar fray/geometry quantities.
