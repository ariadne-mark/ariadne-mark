# Download and verify real SDK exports

The [0.7.2a1 release](https://github.com/ariadne-mark/ariadne-mark/releases/tag/v0.7.2a1)
includes **ariadne-mark-samples-0.7.2a1.tar.gz**: one marked PNG, video exported
in Economy5s, Economy2s and Resilient, receipts, verification JSON and signed
verifier reports. It also includes the unmarked inputs, a metadata-stripped PNG,
its verification result and recovered C2PA manifest.

These are synthetic, deterministic integration fixtures. Their AI-origin
declarations are intentional test data under **development credentials**, not
evidence that a generative model made the input or a production-trusted issuer
signed it. The archive contains no private signing/report key or registry database.

## Inspect the files

Download the sample archive and `BUNDLE_SHA256SUMS` from the release. Check the
archive hash before extracting; inside, `SHA256SUMS` covers individual samples.
`samples-manifest.json` records exact SDK/image identity, fixture details and
results. `verifier-report.pub` is the report verification key.

```sh
ariadne report verify ariadne-samples/image.png.signed-report.json   --public-key ariadne-samples/verifier-report.pub   --asset ariadne-samples/image.png   --verifier-id urn:ariadne-mark:sample-verifier:0.7.2a1
```

For a video use the matching `economy_5s.mp4`, `economy_2s.mp4` or `resilient.mp4`
and its signed report. This verifies the report signature and exact asset
association. To independently re-run watermark/C2PA inspection, use
`ariadne verify FILE` in the full media runtime. The original file includes its
signed manifest; registry-based metadata recovery is separately demonstrated
by the supplied result and recovered manifest, not by a distributed live registry.

## What to expect

The original outputs have a recoverable ID and valid development signature;
their issuer is deliberately untrusted. The signed report's public key is a
separate trust choice from the C2PA issuer. The six-second video is 512×320,
12 fps. All three modes export and verify; this fixture is not a population
durability study or production throughput claim.

To create new outputs and a private local registry yourself, follow
[the first-export walkthrough](../start-here.md). For methods and limitations
see [test protocols](protocols.md) and [qualification](../validation/0.7.2a1-results.md).
