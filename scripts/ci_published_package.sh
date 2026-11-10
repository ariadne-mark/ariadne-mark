#!/usr/bin/env bash
set -euo pipefail
# Maintainer-dispatched EC2-only qualification for documentation changes.
# Never substitutes a rebuilt package for the frozen public release.
root=$(pwd)
out="$root/release-dist"
mkdir -p "$out/logs" "$out/published"
baseline=8c6fda81b27c5c6c0c9539bbbc3daef7e285b1fa
image=ariadne-mark:0.7.2a1
test "$(docker image inspect "$image" --format '{{.Id}}')" = sha256:13689f43bb1e0de927c3ea9605d7a55d251bf0b9cf486e7dd780360a41d27cdc
# This mode is deliberately inapplicable to runtime/test/build changes.
git fetch --no-tags origin "$baseline"
git diff --exit-code "$baseline" HEAD -- src tests requirements Dockerfile pyproject.toml MANIFEST.in examples > "$out/logs/unchanged-runtime.log"
release=https://github.com/ariadne-mark/ariadne-mark/releases/download/v0.7.2a1
for file in ariadne_mark-0.7.2a1-py3-none-any.whl ariadne_mark-0.7.2a1.tar.gz SHA256SUMS; do
  curl --fail --location --retry 2 "$release/$file" -o "$out/published/$file" > "$out/logs/download-$file.log" 2>&1
done
(cd "$out/published"; sha256sum -c SHA256SUMS) > "$out/logs/public-artifact-hashes.log"
test "$(sha256sum "$out/published/ariadne_mark-0.7.2a1-py3-none-any.whl" | cut -d' ' -f1)" = 05d2b28ae205dfc485d91cc06b7fdf09c53a4882a395e957a4bf15cd9a9931c2
test "$(sha256sum "$out/published/ariadne_mark-0.7.2a1.tar.gz" | cut -d' ' -f1)" = db5945b325cbf48620bb842689dfcb323c0210266df536bc8821b8b027a6371f
docker run --rm --network none --cpus 2 --memory 3g --read-only   --tmpfs /tmp:rw,noexec,nosuid,size=512m -e ARIADNE_MEDIA_TESTS=1   -v "$root:/app:ro" -w /app --entrypoint python "$image"   -m unittest discover -s tests -t . -v > "$out/logs/full-media.log" 2>&1
docker run --rm --network none --read-only -v "$root:/review:ro"   -v "$out/published:/artifacts:ro" -w /review --entrypoint python "$image"   scripts/check_installed_payload.py /artifacts /review > "$out/logs/package-parity.json"
python3 scripts/check_requirements.py > "$out/logs/requirements.log"
python3 scripts/check_runtime_locks.py > "$out/logs/runtime-locks.log"
docker run --rm --network none --entrypoint python "$image" -m pip check > "$out/logs/pip-check.log"
python3 - <<'PY'
import json,os,subprocess
from pathlib import Path
out=Path('release-dist')
log=(out/'logs/full-media.log').read_text()
assert 'Ran 217 tests' in log and '\nOK\n' in log and 'skipped=' not in log
(out/'published-qualification.json').write_text(json.dumps({
 'mode':'unchanged published package; no runtime rebuild',
 'reviewed_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'qualified_runtime_sha':'8c6fda81b27c5c6c0c9539bbbc3daef7e285b1fa',
 'full_media_tests':217,'skips':0,'platform':'Linux x86-64 CPU on owned EC2',
 'image_id':'sha256:13689f43bb1e0de927c3ea9605d7a55d251bf0b9cf486e7dd780360a41d27cdc',
 'original_complete_qualification':'https://github.com/ariadne-mark/ariadne-mark/actions/runs/42738430001',
 'public_release':'https://github.com/ariadne-mark/ariadne-mark/releases/tag/v0.7.2a1'
},indent=2)+'\n')
PY
printf '%s\n' 'Public artifact hashes, unchanged runtime, 217 media tests, payload parity and traceability passed.'
