# Versioned test and benchmark evidence

SDK **0.7.2a1** · documentation review **2026-11-10**.

Use this index to select the right evidence for a claim. Engineering tests,
small robustness experiments and population performance estimates are different
things. Historical measurements are not relabelled as new 0.7.2a1 results.

| Record | Actual scope | Supported conclusion | Boundary |
| --- | --- | --- | --- |
| [0.7.2a1 qualification](../validation/0.7.2a1-results.md) | 217 installed-media tests, core matrix, clean installs, kit/HTTPS/reports/registry, external c2patool | Current packaged workflow passes those checks on Linux CPU | Development identities; no current population durability or throughput benchmark |
| [0.7.1a1 paired media](../validation/0.7.1a1.md) | Two stock scenes, 10 s and prepared 3 s renditions, three profiles, identity transforms and remover | Measured short/excerpt/remover boundaries on that corpus | Two source scenes are not all content; repeats/IDs are dependent |
| [Reliability observations](../../benchmarks/reliability/README.md) | Production-Node 22 selected clean 720p clips; four positive controls, auxiliary reference analysis | No recovered ID in those scoped clean checks; controls recovered | Not a population FPR or cross-provider detector guarantee |
| [0.7.1 pipeline](../validation/0.7.1a0.md) | Colour/FPS/BCH fixes and focused release tests | Versioned pipeline regression evidence | Earlier exports/CPU conditions must remain identified |
| [0.7.0 recovery](../validation/0.7.0a0.md) | Signed reports and detached manifest integration | Signature/ID/binding distinctions | Not authentication of arbitrary edited copies |
| [Historical profile selection](../../benchmarks/video/profiles/README.txt) | Legacy Fast/shared residual versus per-frame candidate | Earlier technology-selection rationale | Not Economy5s/2s or current installed-SDK throughput |
| [Legacy VideoSeal](../validation/0.3.0a0.md) | Older CPU encoder/stock corpus | Compatibility/history of old format | Not the current default engine |
| [Spatial research](../research/spatial-recovery-2026-11-06.md) | Geometry recovery feasibility | Research rationale and measured limitations | Experimental cropdetect is not silently enabled in the release verifier |

## Current cadence integration observation

The 0.7.2a1 6 s/12 fps fixture has 72 frames. Economy5s marked 4 frames in two
windows; Economy2s 6 frames in three; Resilient all 72. This distinguishes the
implemented schedules. It is not a durability percentage or benchmark ranking.

## Historical speed and resources

The paired **0.7.1a1** Linux/m6a.large record reports the following means over
two exports per cell, including worker startup, signing and read-back:

| Input duration | Economy5s wall / cgroup CPU s | Economy2s wall / cgroup CPU s | Resilient wall / cgroup CPU s |
| --- | --- | --- | --- |
| 10 s, 720p24 | 13.92 / 22.77 | 17.29 / 28.78 | 94.69 / 166.22 |
| 3 s, 720p24 | 5.81 / 8.44 | 6.48 / 10.40 | 29.85 / 51.95 |

These are original-version/corpus measurements, not a 0.7.2a1 performance claim
or SLA. Current container memory limits are deployment limits, not measured RAM
consumption. A positive early-stop scan must not be compared as if equivalent
to an unmarked full scan. Use [P6](protocols.md#p6-performance-and-resource-use)
for a new matched comparison; do not combine Mac/server or old adapter timings.

## Observed short and removal limits

In the same two-scene record, all modes recovered the two fresh 10 s and two
fresh 3 s exports, and all four identity CRF23 transcodes per mode. A 1–4 s
excerpt recovered 0/2 Economy5s versus 2/2 Economy2s and Resilient; an excerpt
between Economy windows recovered 0/2 both Economy modes versus 2/2 Resilient.
A leading 0.2 s trim of the 3 s exports recovered 0/2 Economy5s versus 2/2 the
other modes. These are scenario counts, not estimated probabilities.

The paired public-remover image experiment removed IDs in 4/4 trials across two
scenes/two IDs; matching identity controls recovered. Resilient video after removal
recovered by aggregation for crowd, while face returned `not_found`. Crop and
letterbox remain known limitations. A correct ID alone never authenticates an
edited copy. See the complete versioned record for parameters and logs.

## Public claim rules

Publish claims with SDK version, source/CI identity, machine, corpus and exact
stage/transform scope. Do not describe test count as attack count, sampled reads
as whole-video confidence, a memory cap as RSS, or standard C2PA parsing as
public trust/conformance enrollment. Include failures and incomplete outcomes.
