# CPU deployment and worker ownership

Current media scope: SDK 0.7.2a1, Linux x86-64/Python 3.12 CPU. The qualified
host has 2 vCPU/8 GiB; the full test container limit is 2 CPU/6 GiB. A limit is
not measured memory consumption. See [actual results](../validation/0.7.2a1-results.md).

Images use Python TrustMark Q. Current Economy5s/2s and Resilient video use a
persistent Node/ONNX TrustMark-Q worker. VideoSeal is retained for legacy
compatibility, not the default encoder. The full media image includes Torch;
[video-only setup](wheel-install.md) omits Torch/NumPy/Python TrustMark/legacy engines.

Create one SDK per application worker after fork, reuse it for queued jobs and
close it at shutdown. Model access is serialized; avoid a new model per request
or frame. Additional active profiles/processes consume additional memory. Use
an existing application job queue; the verifier HTTP endpoint is not a marking
service. Every video frame is decoded/encoded even when Economy marks selected
windows, so inference savings do not equal total-pipeline savings.

Export stages include preflight, decode/colour, selected/all-frame inference,
encode/remux, C2PA/TSA, read-back, registry and publication. Measure cold/warm,
wall/CPU/container memory separately using [protocol P6](../benchmarks/protocols.md#p6-performance-and-resource-use).
No new 0.7.2a1 throughput/RSS benchmark is inferred from the test-suite duration.

## Publication and crash boundary

The exporter writes a private candidate beside the destination and verifies it
before publication. It commits the registry association and fsynced receipt
before the final media file appears; the media file is the completion marker.
Ordinary failures roll back the attempted export. Existing names are refused.

SQLite and two filesystem paths are not a single power-loss atomic transaction.
A crash can leave an unpublished registry row/receipt/temp directory before
final media publication. Reconcile those orphans, retries and idempotency at the
application level. Earlier successful batch jobs remain committed if a later
job fails. Do not serve the adjacent private staging directory recursively.

The public verifier has one inference slot and no queue; upload bounds and
inference bounds are separate. Negative scans can be expensive. Size public
capacity from actual workloads, and keep keys/registry permissions isolated.
See [operations](verifier.md) and [production onboarding](production-onboarding.md).
