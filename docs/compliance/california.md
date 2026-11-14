# Implement California provider marking and verification

SDK **0.7.3a2 candidate** · baseline legal-source review **2026-11-10**.

The source review date and dated evidence below remain historical; this header
is not a new legal clearance or candidate qualification.

This guide maps the current provider duties in [BPC Chapter 25](https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?division=8.&chapter=25.&part=&lawCode=BPC) to the
visual SDK. The consolidated official text was checked in the browser on
10 November 2026, including SB 1000, Stats. 2026 Ch. 861. Chapter operation
began 2 August 2026; the mapped amendment took effect 30 September 2026.

## Check the actor and content

The amended covered-provider definition concerns producing a GenAI system
publicly accessible in California; it has no monthly-user threshold. Do not
apply thresholds for another actor or jurisdiction. Check whether your product
only supplies minor modifications or falls within a statutory exception.
The temporary assistive-technology exception and the exclusively non-user-generated
videogame exception require their actual facts; a profile flag does not prove them.

## Provide the verification route

Section 22757.2 addresses a no-cost public verification tool for the provider's
image/video/audio output, system-provenance display, privacy controls, upload
or URL submission, programmatic access and efficacy feedback. Ariadne supplies
upload UI/API, minimized output, signed results and anonymous feedback counters.
It does not fetch remote URLs; upload is the supported submission alternative.
The operator deploys the endpoint, reviews public fields/host logs, uses relevant
feedback and keeps access operational. The third-party route also requires a
clear product-UI entry point and compatibility. See [verifier operations](../operations/verifier.md).

## Include latent disclosure

Section 22757.3(a)(1) specifies provider, system/version, creation/alteration
time, unique identifier and created/altered information, directly or through
a permanent website link. The assistive-technology metadata field starts in
2029. Current C2PA records carry the implemented fields; after metadata loss,
ID recovery needs the operator's persistent registry/verifier. A watermark ID
alone is not a complete public provenance record or universal resolver address.

The disclosure must also address removal/tampering resistance, compatibility
with its verifier and recognised industry standards, to the extent technically
feasible. Known crop/remover/temporal failures remain material evidence. Neither
Economy nor Resilient has been established as satisfying statutory permanence.
The amended provider section no longer requires the former offer of a visible
provider disclosure; other product/actor obligations can still require one.

## Process duties and future dates

If licensing the GenAI system, assign the notice and response workflow under
22757.3(b), including the relevant 72-hour and 96-hour steps and Attorney General
reporting when triggered. This is an operator process, not an SDK function.
Do not describe use of this SDK library alone as that licensing scenario.

Large online platforms and GenAI hosting platforms have separate provisions
operative 1 January 2027; capture-device duties have a 1 January 2028 date.
These actors are not automatically covered by the SDK's provider profile.
Review 2029 assistive-technology changes before relying on that scope.

Use the [requirements matrix](requirements-matrix.md), [short source excerpts](source-excerpts.md)
and [evidence template](operator-evidence-template.md). Generated audio is not
independently marked by this visual kit; AAC preservation does not close that gap.
