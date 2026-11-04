# Configure a product and inspect its remaining requirements

Ariadne Mark 0.4 adds an **offline requirements planner**, with an optional
connection to media export. It distinguishes product declarations, implemented
technical measures, missing deployment steps and matters requiring review.
The profile snapshot is `2026-11-04.1`. It covers EU visual-content marking /
deepfake disclosure and California covered-provider duties, not every AI law.

## Start without models or a GPU

After installing the core wheel (no media extra required):

```sh
ariadne profile init > product.json
# Edit product.json with your actual product details and deployment choices.
ariadne profile check product.json > requirements-report.json
ariadne profile sources
```

`examples/profiles/small-generator.json` is a deliberately incomplete example.
Replace the example publisher/system, assess scope and fill deployment fields.
Unknown values use JSON `null`; do not turn them into `false` just to clear a
check. `role` describes the EU role; California has its own provider questions.

The checker does not fetch URLs, inspect a deployment, classify a deepfake,
verify a benchmark reference or resolve legal exceptions. URL validation is
syntax-only. A declared public endpoint still needs an actual availability,
privacy, compatibility and accessibility review.

### Report and exit codes

| Field | Meaning |
|---|---|
| `configuration_status` | `valid` or `invalid` for this SDK configuration |
| `assessment_status` | `action_required`, `review_required` or `configuration_reviewed` |
| `export_supported` | Whether this configuration can be passed to the SDK; not permission to launch |
| `implemented_measure` | A measure implemented by the SDK; export read-back is recorded separately |
| `declared_not_verified` | The operator supplied information; the checker has not verified it |
| `action_required` | A concrete configuration/deployment item is missing |
| `review_required` | Applicability, exceptions, evidence or another obligation needs assessment |
| `legal_determination` | Always `not_performed` |

CLI exit **2** means invalid input/unsupported configuration; **3** means open
actions or review; **0** means no open items in the evaluated scope. None means
legal certification. Applicability, durability, interoperability and other-role review remain open
even after every deployment field is filled.

`--as-of YYYY-MM-DD` evaluates a scenario against this snapshot; it does not
retrieve historical legislation or future amendments. Dates before the mapped
California amendment return `historical_version_not_supported`. After 30 days
the SDK recommends source refresh; that interval is our maintenance policy,
not a statutory deadline.

## Use the same configuration for export

```sh
ariadne mark input.png marked.png --profile product.json \
  --created-at 2026-11-03T10:00:00Z --identity .ariadne/dev --allow-dev
```

For video, use MP4 paths and truthfully set `sdk.audio_kind` in the profile.
`none` rejects a video that actually contains audio. `original` retains audio;
`unknown` leaves an explicit review item. Profiled exports with synthetic audio
are unsupported because the SDK does not independently mark its audio track.
The unprofiled low-level media API remains available with its documented limits.

Python: `sdk.mark(source, destination, record, profile=config)` accepts the same
validated dictionary. Record publisher, generator name/version and media kind
must agree with it. Each record still supplies its actual creation/edit time,
asset ID and created/altered action. An optional CLI metadata override must match.

The profile always enables watermarking and signed C2PA. `baked_in` or `both`
disclosure selects the visible label; `in_app` is an operator declaration and
does not insert UI into the product. An explicit `--visible` may add a label.
Existing read-back checks still run before output publication. Profile reports
and their canonical configuration hash are attached to the receipt before it
is saved or committed to the registry. The receipt records actual export
settings separately from the configuration's requested settings.

Open legal/deployment actions **do not block a technical test export**. Invalid
metadata, conflicting configuration and unsupported media/audio do. A generated
file plus a successful receipt does not close the report's remaining actions.

## Decisions represented in this release

- EU provider marking and deployer deepfake disclosure are separate. The
  pre-2-August-2026 provider transition does not postpone deployer disclosure.
- Claimed editing, creative-work and other exceptions stay under review; they
  never silently disable marks. Creative-work disclosure is not a blanket exemption.
- California mapping uses the 30-September-2026 SB 1000 chaptered text: no
  million-user threshold, and no mandatory offer of a visible overlay under
  that amended provider provision. Other contexts may still require disclosure.
- California verifier submission may be **upload or URL**, with programmatic
  access. The supplied verifier implements upload; remote URL fetching is not
  necessary. Third-party verifier use introduces a product-UI access check.
- Durability/interoperability, verifier privacy, feedback and licensing workflows
  remain product responsibilities. The 2029 assistive-technology metadata change
  is flagged as an unsupported future schema requirement.

See [source mapping and remaining limits](release-mapping.md). EU source text,
Commission guidance and voluntary Code of Practice are separate source types.
The selected C2PA/watermark combination is an SDK implementation choice.
