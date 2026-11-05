# Integrate at export

Use one persistent SDK per product worker process. Provision models during deployment, create the SDK after the process starts, reuse it for jobs and close it during shutdown. Processing is synchronous: run it in your existing background job queue rather than blocking a web request. Python is the native SDK; other backends can invoke the CLI. The public HTTP service is for verification, not an unbounded public marking API.

## A video job

```python
from datetime import datetime
from pathlib import Path
from ariadne_mark.pipeline import SDK
from ariadne_mark.provenance import Action, GenerativeSystem, MediaKind, ProvenanceRecord
from ariadne_mark.registry import Registry
from ariadne_mark.signing import SigningIdentity

# Development integration only. Production needs your own identity/trust setup.
identity = SigningIdentity.from_directory(Path(".ariadne/dev"), allow_dev=True)
sdk = SDK(identity=identity, registry=Registry(Path(".ariadne/registry.sqlite3")))

record = ProvenanceRecord.create(
    publisher="Example Studio",  # truthful public organization information
    system=GenerativeSystem("Example Generator", "1.0"),
    media_kind=MediaKind.VIDEO,
    action=Action.CREATED,
    created_at=datetime.fromisoformat("2026-11-06T09:00:00+00:00"),
    # Supply the actual generation time, not the later marking time.
)

receipt = sdk.mark(Path("input.mp4"), Path("output.mp4"), record,
                   audio_kind="original")  # default economy_5s
report = sdk.verify(Path("output.mp4"))
sdk.close()
```

Create the development directory with `ariadne init-dev .ariadne/dev` in a provisioned environment. Keep it out of version control. `--allow-dev` is explicit because that identity is not a production credential. Never deploy its private key in the verifier.

Use `video_profile="economy_2s"` or `"resilient"` on the constructor to set a worker default, or on `mark()` to select a single export. Product JSON configuration can select `sdk.video_profile`; a per-export override must agree with that product configuration. Only requested profile workers are loaded. Public verification can reuse an already resident compatible decoder regardless of its encoding preset.

## Publication and retries

`SDK.mark()` writes a private candidate, applies the selected visual watermark/visible disclosure, encodes/remuxes, signs C2PA and checks the actual signed output. Economy checks every occupied watermark window; Resilient checks five uniform positions. On failure it publishes neither final media nor a success receipt. Registry entry and fsynced receipt precede final media publication; the media's existence is the completion marker.

Use a fresh output path per job and your own idempotency key. The SDK does not overwrite an existing output. Manage retries and orphan cleanup at the product level. The [stock-product example](../../examples/stock_product/README.md) includes a queue and bounded retries. Shared-thread exports serialize a single profile's model access; use separate product processes for parallel throughput. Multiple active profile workers use additional memory.

## Audio, images and source facts

For images, use `MediaKind.IMAGE` and a JPEG/PNG input/output. Video profile selection does not change the image engine. Preserve actual source facts, use `Action.ALTERED` for appropriate credentialed inputs and retain parent history through the supported workflow. Do not replace unknown source facts with invented certainty.

AAC can be copied and covered by the signed MP4 file binding. It is **not** independently watermarked. `audio_kind="synthetic"` is a provenance declaration, not an audio-marking solution; the EU/California visual product profile blocks profiled synthetic-audio exports that require that missing control. Choose a separate audio solution if your product generates sound.

The public UUID and watermark ID are per-asset identifiers, not user/account identifiers. Use public provider/model values only; never include end-user names, prompts, emails or account IDs. The optional registry must be backed up and persistently served where your workflow relies on it for recovery after metadata loss.

[Mode trade-offs](video-profiles.md) · [Supported media boundaries](../operations/support.md) · [Verifier quickstart](../operations/verifier-quickstart.md) · [Legal map](../compliance/launch-mapping.md)
