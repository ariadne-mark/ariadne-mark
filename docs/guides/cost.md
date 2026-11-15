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
consume 2.78 CPU-hours/day. At 60 CPU seconds/job they consume 16.67. Calculate
the bill from provisioned VM-hours and the VM rate, including idle capacity. Compare cold
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

## A complete workload: 1,000 images and 300 videos per day

At one final rendition and one successful export per item, a **30-day month is
30,000 image exports + 9,000 video exports = 39,000 exports**. A 365-day year is
474,500 exports. Download the [editable workload sheet](../examples/cost-workload.json);
unknown inputs are `null`, never silently zero. These are planning counts, not a
claim that one VM can process this workload.

```text
export attempts = days × (images/day + videos/day) × renditions/item × attempts/rendition
export CPU-hours = (image attempts × full-job image CPU seconds
                 + video attempts × full-job video CPU seconds) / 3600
verify CPU-hours = days × (positive checks/day × full-job positive CPU seconds
                 + negative checks/day × full-job negative CPU seconds) / 3600
monthly compute bill = exporter allocated VM-hours × its hourly price
                     + verifier allocated VM-hours × its hourly price
monthly total = compute + storage/backup + delivery + domain/TLS
              + certificate + TSA + operator work + allocated setup costs
```

Measure CPU for the **whole job/process tree**, including Node and FFmpeg. VM
billing uses allocated hours; CPU-hours above describe work and cannot be directly
multiplied by a VM-hour price. Capacity still needs a sequential/queued wall-time
measurement with headroom. Keep image and each selected video profile separate.
The recent client pilot's Python SELF CPU excludes child processes; it is **not**
a valid complete CPU input or a basis for a dollar total.

| Budget line | Fill in for this workload | Not included automatically |
| --- | --- | --- |
| Export | Image/video dimensions, duration, FPS and profile; cold/warm wall time, total CPU and peak memory; retries/renditions | Generation GPU/API cost, throughput guarantees |
| Positive verification | Checks/day × measured positive job cost | Export gate is not your public independent verification traffic |
| Negative/incomplete verification | Clean negatives/day × full-scan cost; budget/deadline and queue headroom | Early positive timings cannot size this load |
| Hosting | Allocated exporter and separate verifier hours × actual regional VM prices | Idle time, scaling and network egress are not free |
| Storage/registry/backup | Media bytes × retention; receipt/manifest/database growth; tested backup/restore | A deleted upload is not a backup policy |
| CDN/delivery | Egress and each final crop/encode's additional export | Original master export does not mark a new rendition |
| Signing/TSA | Certificate term + requests above real quota + signing retries | Failed export may still consume a timestamp; exact retry volume needs measurement |
| Operations/setup | Engineer hours × your rate; enrollment, renewal, monitoring, incidents | Free SDK code does not supply managed operation |

Do not add the bundled timestamp service again if already included in a managed
plan. Separate recurring spend from initial implementation/conformance work.
Taxes, currency conversion, discounts and temporary promotions are excluded here.

## Dated external price references

Checked **15 November 2026**; confirm eligibility, interface and current terms
before ordering. These references do not establish interoperability with your
credentials, a legal approval or an all-in quote.

For a hosting reference, [AWS Lightsail](https://aws.amazon.com/lightsail/pricing/)
lists a Linux public-IPv4 bundle at $12/month with 2 GB RAM, two burstable vCPUs,
60 GB SSD and a 3 TB transfer allowance (regional transfer conditions apply).
This is a small site/demo hosting reference, **not** a qualified worker size or
capacity estimate for 39,000 image/video exports. Do not count both a bundled
hosting fee and the same VM's hours twice.

[SSL.com's C2PA pricing](https://www.ssl.com/products/content-authenticity/content-credentials/c2pa/)
lists a one-year Level 1 certificate at no charge with 2,500 timestamps/year;
its Premium lists $500 per certificate/year with 10,000 timestamps/year.
At 474,500 annual successful exports, those allowances leave respectively
472,000 or 464,500 requests beyond quota before retries. Overage needs a quote.
Eligibility/conformance and key-interface compatibility remain operator work.

[Trufo's public pricing](https://trufo.ai/pricing) lists Managed Starter at
$120/month including 1,000 signatures, then $0.03/signature; Business at
$1,200 including 10,000, then $0.01. Applied mechanically to 39,000 signatures,
these give **$1,260** and **$1,490/month for the signature-plan component**.
They are not full workload quotes: included watermark ID units are 300/3,000;
video unit accounting and overage need confirmation. Volume discounts or a
temporary promotion can change the result. Managed service includes operator
work that self-hosted Ariadne leaves to your team; prices alone do not establish
which option is cheaper for your app.

## Before choosing a budget

Fill every unknown line, test representative files on your intended worker and
confirm a CA/TSA quote for the request volume. A partially filled worksheet can
show workload and known components, but **cannot report an all-in monthly total**.
The [production critical path](../operations/production-onboarding.md) identifies
which steps need your own operator credentials and an external service.
