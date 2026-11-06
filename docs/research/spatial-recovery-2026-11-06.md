# Crop and letterbox recovery: ready implementations

Status: research for the next spatial recovery step, not a qualified SDK feature.
Economy 5s, Economy 2s and Resilient retain their present cadence and models.
Tests and media probes for this work run only on the Oregon EC2 host.

## Different failure mechanisms

A 16:9 image cropped to 9:16 at constant height retains about 31.6% of its
original area. Missing pixels cannot be recovered by stripping metadata or
increasing the number of marked frames. Black letterbox bars instead change the
image coordinates and the effective marked area presented to a global decoder.
Removing those bars may restore the input geometry without changing the marker.
Native portrait exports and portrait crops of landscape exports are different
cases and must have separate benchmark rows.

## Candidates in priority order

| Ready implementation | Use | Deployment cost and limits | Decision |
| --- | --- | --- | --- |
| FFmpeg `cropdetect` + `crop` | Detect black bars, then decode only the active image rectangle | Existing CPU dependency; no new model. Dark scenes, changing bars, subtitles and non-black backgrounds need controls | First recovery prototype. Keep full-frame attempt, bound ROI candidates and total inference/deadline; log coordinates and how they were obtained |
| Adobe TrustMark Q `loadBBoxDetector=True`, `localize`, `DETECTFIRST` | Find a watermarked region inside a larger image | Additional detector/weights and Torch path; CPU is selectable upstream, but our ONNX worker has no equivalent adapter yet. Localization cannot restore deleted pixels | Benchmark upstream implementation before porting; pin source/weights/license and measure CPU cost |
| TrustMark `concentrate_wm_region` | Place watermark in a central region; upstream decoder uses matching geometry | Changes encoder layout and visibility distribution. Existing exports do not acquire this property retroactively | Consider as a separately versioned spatial policy, never silently redefine the existing presets |
| Meta Watermark Anything, `wam_mit.pth` | Localized messages and mask-based detection | Inference model and integration work; benchmark CPU rather than assume GPU is mandatory. SA-1B weights MIT, original COCO weights noncommercial. Repository archived Aug 2026 | Strong localized-watermark research candidate, not an immediate drop-in replacement |
| Meta VideoSeal / PixelSeal | Alternative trained spatial robustness, evaluation suite, streaming inference | Models and toolkit are MIT per upstream; new model/runtime qualification and payload mapping required. Vendor/research benchmark scores are not our SDK results | Reuse their geometric augmentations/evaluation methodology and benchmark the exact checkpoint if simpler recovery fails |

## Proposed first implementation

1. Keep today's full-frame detector result and resource ceilings.
2. Sample a bounded set of frames for FFmpeg black-border detection. Require a
   temporally stable, sufficiently large rectangle; reject empty/tiny regions.
3. Run one additional ROI hypothesis only when geometry supports it; retain a
   shared overall deadline/frame budget. Cache ROI logits separately.
4. Report the rectangle, preprocessing, evidence and scope. A mark in one region
   does not establish provenance for the entire composite image/video.
5. Measure clean negative videos, dark content, real letterbox/pillarbox,
   overlays, genuine 9:16 crops, and existing portrait exports. No unrestricted
   rectangle scan: more hypotheses also increase false-positive opportunities.

The upstream FAQ describes approximately 20% area-loss crop testing; it does not
promise survival of the roughly 68% area loss in our 16:9-to-9:16 case. Merely
raising strength or using Resilient is therefore not a supported spatial fix.

## Primary sources, inspected 2026-11-06

- [FFmpeg cropdetect documentation](https://ffmpeg.org/ffmpeg-filters.html#cropdetect), also inspected in [official source](https://github.com/FFmpeg/FFmpeg/blob/master/doc/filters.texi).
- [TrustMark implementation](https://github.com/adobe/trustmark/blob/main/python/trustmark/trustmark.py): constructor, `get_the_image_for_processing`, `localize`, `decode`.
- [CAI TrustMark FAQ](https://opensource.contentauthenticity.org/docs/durable-cr/tm-faq/): robustness limits and centralized watermark visibility trade-off.
- [Watermark Anything](https://github.com/facebookresearch/watermark-anything): localized messages, CPU fallback, distinct model licenses.
- [VideoSeal / PixelSeal](https://github.com/facebookresearch/videoseal): model cards, streaming inference, evaluation suite and MIT statement.
