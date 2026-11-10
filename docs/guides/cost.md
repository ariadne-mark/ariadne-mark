# Budget for AI image and video labeling

The Ariadne SDK has no licence fee or per-export Ariadne API charge. Your
CPU time, storage, verifier capacity, identity/signing and timestamps still
have a cost. Estimate them for your actual final renditions and delivery path.

## Calculate the workload

Use `daily exports × measured warm CPU seconds / 3600` for CPU-hours per day.
For wall-time capacity use measured jobs/hour per bounded worker, then leave
headroom for generation spikes, retries and verification. CPU time and elapsed
time are different; two vCPUs do not promise twice the throughput.

Example arithmetic, **not a benchmark**: 1,000 jobs/day at 10 CPU seconds/job
consume 2.78 CPU-hours/day. At 60 CPU seconds/job they consume 16.67. Multiply
by your provider's actual billed rate, including idle capacity. Compare cold
starts separately. No production SLA follows from a sample or test-suite runtime.

## Choose what to measure

| Cost | Measure or obtain |
| --- | --- |
| Export | Cold/warm wall time, total process-tree CPU and peak memory; image dimensions, video duration/FPS/codec/profile |
| Verification | Clean negatives, long scans, concurrency limits and hostile uploads, not only fast known-ID positives |
| Storage | Published media, receipts, manifests, registry/backup retention; avoid retaining uploads unnecessarily |
| Signing | Certificate eligibility, renewal, key storage and conformance work |
| Timestamps | Exports requiring a timestamp × price above included quota; network latency/retries |
| Delivery | App/CDN transforms and whether each final rendition must be exported separately |

Economy5s and Economy2s reduce selected-frame inference. They still decode and
encode every frame. Resilient computes a fresh signal for every frame; this is
more expensive and does not promise survival of arbitrary crops or removers.
Use the [versioned measurements and protocols](../benchmarks/evidence-index.md),
then benchmark the clips your product actually generates.

## Signing budget is separate

As checked 11 November 2026, [SSL.com's published C2PA offer](https://www.ssl.com/products/content-authenticity/content-credentials/c2pa/)
lists one one-year Level 1 certificate and 2,500 timestamps/year at no cost,
subject to its eligibility and conformance requirements. That is about
6.8 timestamps/day, not a free timestamp allowance for 1,000 exports/day.
Higher-volume prices need a quote; none are assumed here. This is vendor
information, not an Ariadne commercial offer or tested enrollment.

Production exports currently require trusted timestamps by **SDK policy**;
Article 50 does not prescribe this exact per-file TSA topology. Review
[production onboarding](../operations/production-onboarding.md) before estimating
cost or promising your own launch date.
