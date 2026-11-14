# Resolver discovery: production acceptance

## What works today

An operator's configured verifier can decode an Ariadne token and query its own
registry. [Manifest recovery](c2pa-recovery.md) implements a read-only subset of
the C2PA soft-binding API and validates recovered signatures/bindings separately.
The token is an opaque 64-bit value; it does not embed a resolver URL. Merely
registering an algorithm name cannot identify every operator's registry.

## What is not qualified

An unrelated third party with only a metadata-stripped file cannot automatically
discover the correct per-operator resolver. Provisional algorithm IDs, a public
website, or one successful own-kit lookup do not demonstrate that capability.
This remains an interoperability gap, not a claim that every statute mandates
embedding an endpoint URL in every watermark. The EU voluntary Code's selected
interoperability route and product-specific statutory assessment are distinct.

## Bounded route to qualify

Keep the current payload and marking modes. First establish a reviewed,
versioned directory of participating operator resolvers and supported algorithm
IDs, distributed by an industry/consortium access method or an equivalent
discovery mechanism. The detector identifies an algorithm; the directory routes
binding lookups to participating endpoints. Multiple operators may issue the
same algorithm. Unknown/conflicting matches must remain explicit; a match alone
does not authenticate an altered copy. This is a proposed deployment route,
not an implemented universal directory or an external partnership.

For a public directory, define the operator's stable HTTPS endpoint, ownership
proof/contact, supported algorithms, privacy policy, withdrawal/revocation and
rate limits. Prefer binding-only requests; do not upload assets to unrelated
resolvers without a separate privacy decision. Do not enable arbitrary
asset-supplied URLs, automatic broad detector scans or unconstrained fetching.
Require TLS, an operator allowlist, bounded query fan-out/timeouts and no private
network destinations in any future routing client.

## Acceptance before claiming third-party discovery

1. Two independent operator registries issue real marked exports with different
   IDs. Strip metadata; retain signed originals and hashes as evidence.
2. A separate client starts with only each stripped file and the reviewed
   directory/discovery configuration, with no expected ID or per-file endpoint.
3. It decodes the observed token/algorithm, records how the appropriate resolver
   was selected, obtains candidate manifest IDs and retrieves exact manifests.
4. Validate signature, issuer/TSA trust and soft binding; report hard-binding
   mismatch of an edited file separately. Never call a copied ID an authenticated
   copy. Unknown, duplicate, unpublished and conflicting records stay explicit.
5. Exercise stale directory, unavailable endpoint, wrong operator, unrelated ID,
   private registry, copied watermark and multiple-ID inputs. Failure cannot
   become a successful negative or a fallback upload to arbitrary servers.
6. Save directory version/hash, asset/manifest hashes, raw requests with secrets
   redacted, responses and signed verifier reports. Log resource/latency costs
   separately from detector performance.

This acceptance has not been run for a public discovery service. Publishing or
enrolling actual operators requires their stable endpoint, authorization and
external agreement. Until then use the documented operator-provided verifier;
do not advertise universal cross-provider recovery.

See [requirements map](../compliance/eu-code-map.md),
[production onboarding](production-onboarding.md), and the
[C2PA soft-binding resolution API](https://spec.c2pa.org/specifications/specifications/2.3/specs/C2PA_Specification.html#_soft_binding_resolution_api).
