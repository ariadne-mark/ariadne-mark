# C2PA signing and validation

The qualified media runtime uses the official tagged c2pa-python 0.38.3 wrapper
and SHA-256-pinned native 0.91.11, provisioned explicitly because this wrapper
version is not available as an ordinary PyPI wheel. Runtime preflight verifies
the actual loaded native identity/version/hash. See [diagnostics](../operations/c2pa-runtime.md).

The exporter signs final JPEG/PNG/MP4 media using ES256. Its manifest records
standard actions and AI digital source types plus the Ariadne record and
supported soft-binding assertion. Verification separates signature/content
binding, issuer trust, timestamp trust and source claims. Unknown substantive
validation failures are not silently accepted.

Non-development exports currently require an explicit TSA and trusted timestamp
read-back. Issuer and private-TSA roots are separate. `kit check` now validates
the provider path/EKU against configured roots; this is not public enrollment,
revocation freshness or a complete production-readiness check. Generation times
over five minutes in the future are refused at issuance; externally supplied
claims can still be parsed for inspection.

The immutable registry can retain exact signed manifest bytes. The read-only
[repository subset](../operations/c2pa-recovery.md) supports explicitly approved
publication and validation of recovered manifests. Algorithm IDs remain provisional;
full repository conformance and global discovery are not claimed. Parent inputs
follow the current altered/ingredient workflow; marking-only relay remains open.

[Key operations](../operations/keys-and-trust.md) ·
[Result semantics](verification-results.md) ·
[Current qualification](../validation/0.7.2a1-results.md)
