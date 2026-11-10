# Choose a labeling stack for your product

Pick the operating model first: compose components yourself, run a connected
open-source kit, or use a managed provider. This comparison is architectural,
not a claim of equal robustness or regulatory certification. Reviewed 11 November 2026.

| Approach | Useful when | What your team still assembles or operates |
| --- | --- | --- |
| Official CAI/C2PA libraries | You need direct control of Content Credentials integration | Watermark/recovery choices, final-rendition workflow, legal mapping, identity and product operations |
| Adobe TrustMark / Meta VideoSeal | You need a watermark engine or are evaluating robustness research | Signing, record semantics, registry/verifier, key management, tests and integration |
| Ariadne Mark developer alpha | You want a self-hosted CPU image/video kit with pinned tools and EU/California implementation guides | Production identity/trust/TSA, public hosting, delivery tests and your product obligations |
| Managed provenance/labeling platform | You prefer vendor-operated integration and commercial support | Vendor scope/contract, data flow, keys, quotas, portability and your own legal applicability |

Primary references: [CAI tools](https://opensource.contentauthenticity.org/),
[TrustMark](https://github.com/adobe/trustmark),
[VideoSeal](https://github.com/facebookresearch/videoseal),
and [Trufo's described platform](https://trufo.ai/). Trufo describes certificates,
timestamps, provenance and watermark services; we have not audited its private
engine, throughput or frame cadence. A commercial compliance claim does not
establish equivalence between its undisclosed settings and Ariadne's presets.

## Questions worth asking any provider

- Can you export and independently verify a sample from the exact version offered?
- Which image/video formats, transformations and negative results were tested?
- What is included in the price: signing, timestamps, registry, verification or only embedding?
- Can you retain signed manifests and evidence if you leave the service?
- What identity/trust enrollment and product duties remain with you?

Ariadne's [downloadable samples](../benchmarks/samples.md), [versioned evidence](../benchmarks/evidence-index.md),
[licences](../operations/licensing.md) and [production guide](../operations/production-onboarding.md)
make its current boundary inspectable. It is an early developer alpha, with
documented crop/removal and short-excerpt limits.
