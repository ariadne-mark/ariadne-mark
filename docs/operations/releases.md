# Public alpha release qualification

The first public alpha distributes Ariadne's wheel and source archive, plus a
Docker build recipe. A prebuilt combined Docker binary and PyPI publishing are
separate release channels. The SDK provides technical measures and requirements
planning; it does not return a product-wide compliance certificate.

## Required before publishing the alpha

1. Resolve applicable dependency security updates and record scanner coverage,
   skipped packages and native findings; preserve upstream licensing notices.
2. Pass the Python 3.11–3.14 core matrix, real-engine CPU media suite and
   requirements traceability checks on the exact revision.
3. Reconcile public profiles to their operative primary sources. Keep partial
   measures, operator obligations and unassessed legal routes explicit.
4. Build one wheel and source archive; test that wheel, record its hashes and
   dependency/model inventory. Check archives contain no keys or private media.
5. Complete the documented clean-user path: install → provision → image/video
   export → read-back → independent verifier. No source-tree import shortcut.
6. Publish versioned artifacts, scope, benchmark context and security reporting
   links, tied to the tested commit. Do not silently replace release bytes.

## Does not block this scoped alpha

A centrally hosted verifier, paid support/SLA, public certificate enrollment,
new media formats, cross-provider routing and a new broad benchmark campaign
are not required to release the current local developer toolkit. They remain
separate program/deployment work. Existing durability data is not a statutory
pass mark. Repeat performance benchmarks when the processing pipeline changes.

## C2PA setup boundary

The qualified media environment is Linux x86-64/Python 3.12. Patched upstream
C2PA Python 0.38.3 currently has no PyPI files. Install the core first and run
`python -m ariadne_mark.bootstrap_c2pa` in a virtualenv, then install the media
extra. The explicit bootstrap verifies pinned upstream source/native hashes;
request processing never installs packages. The Docker recipe performs this
step during build.

A combined image includes GPL-bearing FFmpeg/codec builds. Before publishing
that binary, complete applicable corresponding-source/notices obligations and
native vulnerability triage for its exact bytes. This is distinct from
publishing Ariadne's own wheel/source and the Docker recipe.

[Current candidate evidence](../validation/0.5.2a0.md) ·
[Previous validation](../validation/0.5.1a0.md)
