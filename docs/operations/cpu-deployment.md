# CPU deployment

The reference Docker build installs CPU-only PyTorch and preloads checksum-pinned
TrustMark Q weights. Runtime can be disconnected from the network. The tested
server has 2 vCPU / 8 GiB; test containers use 2 CPU / 6 GiB limits.

Load `Watermarker(threads=2)` once and reuse it. Model calls are serialized;
use an application queue, not a new model instance per request. Video encodes
every frame and therefore consumes substantially more CPU time than an image.
See measured [release evidence](../validation/0.2.0a0.md); large production
queues and peak-load capacity are not yet qualified.

Export uses a temporary directory beside the destination. The file is published
only after C2PA and watermark read-back. Failures remove temporary media. A
registry failure rolls back the new output and receipt. Existing output names
are refused, including publication races. Retrying to a new filename creates a
new asset; the SDK is not an idempotent distributed job scheduler.

SQLite and filesystem publication are not a single crash-atomic transaction.
A process/host crash between publication and registry commit can leave a signed
export without a recovery record. Reconcile receipts and database before
serving such an export. Production queue/recovery design remains REQ-013 work.
