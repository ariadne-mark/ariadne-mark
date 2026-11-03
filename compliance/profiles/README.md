# Versioned requirements profiles

Implementation: [`src/ariadne_mark/profiles`](../../src/ariadne_mark/profiles).
The packaged `catalog.json` identifies sources, review date and snapshot version.
The core checker runs offline without model downloads or media dependencies.

[Configuration and CLI guide](../../docs/compliance/applicability.md) ·
[Example configurations](../../examples/profiles) ·
[Scenario tests](../../tests/compliance/test_profiles.py).

The profiles cover EU image/video provider marking and deployer disclosure,
and California covered-provider marking/verification. They generate an action
plan, not a certificate. California's official-source reconciliation, complete
Code of Practice assessment, and broader obligations remain open.
