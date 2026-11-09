# Maintainer-dispatched server qualification

SDK/runtime tests execute on the EC2 test server. Public pull requests never
automatically run code on that host. Automatic GitHub notices explicitly say
runtime qualification is pending; a green notice is not release qualification.

For a reviewed revision, the maintainer provisions a temporary repository runner
with the sole custom label `ariadne-manual-qualified`, no default labels and
ephemeral one-job registration. The runner is not installed as a service.
Dispatch the existing workflow for the reviewed branch and full expected SHA:

```sh
gh workflow run scaffold.yml --ref REVIEWED_BRANCH -f expected_sha=FULL_SHA
```

The current workflow restricts dispatch execution to the project's maintainer
`Genesius001`; maintainers must explicitly review changes to that trust policy.
Never approve a public-fork job to use this runner. Register it only for this
trusted pending job and remove its credentials/working directory afterward.
Runner archives must match the checksum returned by GitHub's official API.

The single server job builds the source Docker recipe, tests the installed
wheel with real engines offline, runs the clean core Python matrix, and tests
new isolated full-media and video-only virtualenv installations from the wheel.
Both new installations export/read all three video modes and then repeat smoke
processing offline. The full install also marks/verifies an image. Model setup
is explicit and online, and uses packaged locks; no source SDK is imported in
the wheel smokes. Source/system prerequisites are controlled by the Docker recipe.

The deployment-kit stage provisions a checksum-pinned official standalone
c2patool and digest-pinned nginx edge explicitly. It then runs the installed
exporter/verifier/registry through Compose, pinned localhost TLS, report
verification and rejection tests, metadata-loss recovery, read-only/key
isolation and restart persistence. The external tool independently validates
signature and content hashes; local development issuer trust is not promoted.
Only the edge joins a standard bridge for publishing ports. SDK processing
and verifier containers remain on the internal network.

`scripts/ci_server.sh` records all stages, checks requirement/lock consistency,
package/source/installed parity, distribution hygiene and inventories. Artifacts
in `release-dist/` are uploaded by the workflow even on failure. The manifest
binds the commit, CI run, wheel/sdist bytes and README/metadata hashes. Private
development identities and media remain in the ignored `.ci-work` directory,
outside the published evidence.

Release requires the successful **EC2 release qualification** job for the exact
revision plus clean artifact manifests. Branch-protection contexts must match
the adopted workflow when this candidate is merged; this documentation does not
change repository branch protections or authorize deployment/publication.
