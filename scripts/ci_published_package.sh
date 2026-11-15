#!/usr/bin/env bash
set -euo pipefail
# EC2-only docs qualification against immutable public runtime artifacts.
exec 9>"${ARIADNE_CI_LOCK_FILE:-$HOME/.ariadne-qualification.lock}"
flock 9
root=$(pwd);out="$root/release-dist"
mkdir -p "$out/logs" "$out/published"
field() { python3 -c "import json;print(json.load(open('docs/public-release-baseline.json'))['$1'])"; }
baseline=$(field qualified_source);version=$(field version);image=$(field image_tag)
test "$(docker image inspect "$image" --format '{{.Id}}')" = "$(field image_id)"
git fetch --no-tags origin "$baseline"
# Never permits changed runtime/test/dependency/build-recipe bytes.
git diff --exit-code "$baseline" HEAD -- src tests requirements Dockerfile pyproject.toml MANIFEST.in examples > "$out/logs/unchanged-runtime.log"
release="https://github.com/ariadne-mark/ariadne-mark/releases/download/v$version"
for file in "ariadne_mark-$version-py3-none-any.whl" "ariadne_mark-$version.tar.gz" SHA256SUMS; do
  curl --fail --location --retry 2 "$release/$file" -o "$out/published/$file" > "$out/logs/download-$file.log" 2>&1
done
(cd "$out/published"; sha256sum -c SHA256SUMS) > "$out/logs/public-artifact-hashes.log"
python3 - <<'PY'
import hashlib,json
from pathlib import Path
p=json.loads(Path('docs/public-release-baseline.json').read_text())
for name,expected in p['artifacts'].items():
 assert hashlib.sha256((Path('release-dist/published')/name).read_bytes()).hexdigest()==expected,name
PY
legacy="${ARIADNE_CI_LEGACY_MODEL:-$HOME/.cache/ariadne-ci/y_256b_img.jit}"
printf '%s  %s\n' 5c7a4581c36fc6090aafdcfb3999123bae5172a4847f22e2da4e7fd1a39d1e1b "$legacy" | sha256sum -c - > "$out/logs/legacy-fixture-check.log"
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,noexec,nosuid,size=512m \
  -e ARIADNE_MEDIA_TESTS=1 -v "$legacy:/legacy/y_256b_img.jit:ro" -e ARIADNE_VIDEOSEAL_MODEL=/legacy/y_256b_img.jit \
  -v "$root:/app:ro" -w /app --entrypoint python "$image" \
  -m unittest discover -s tests -t . -v > "$out/logs/full-media.log" 2>&1
docker run --rm --network none --cpus 2 --memory 512m --read-only -v "$root:/review:ro" \
  -v "$out/published:/artifacts:ro" -w /review --entrypoint python "$image" \
  scripts/check_installed_payload.py /artifacts /review > "$out/logs/package-parity.json"
docker run --rm --network none --cpus 2 --memory 512m --read-only -v "$root:/review:ro" -w /review \
  --entrypoint python "$image" scripts/check_documentation.py > "$out/logs/documentation.json"
docker run --rm --network none --cpus 2 --memory 512m --read-only -v "$root:/review:ro" -w /review \
  --entrypoint python "$image" scripts/check_client_docs.py > "$out/logs/client-docs.json"
private_work="$root/.client-journey-private"
mkdir -p "$private_work"
# Sample code is separate from immutable SDK examples/runtime. Exercise it against
# the installed public wheel, with no SDK checkout on Python's import path.
docker run --rm --network none --cpus 2 --memory 4g --read-only --tmpfs /tmp:rw,noexec,nosuid,size=768m \
  --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$root:/review:ro" -v "$private_work:/results" -w /tmp \
  --entrypoint python "$image" /review/scripts/ci_client_journey.py /results/client-journey \
  > "$out/logs/client-journey.log" 2>&1
mkdir -p "$out/client-journey"
cp "$private_work/client-journey/summary.json" "$private_work/client-journey/events.jsonl" "$private_work/client-journey/corpus.json" "$out/client-journey/"
cp -R "$private_work/client-journey/logs" "$out/client-journey/logs"
# Identity, report private key, database and media stay outside uploaded artifacts.
python3 scripts/check_requirements.py > "$out/logs/requirements.log"
python3 scripts/check_runtime_locks.py > "$out/logs/runtime-locks.log"
docker run --rm --network none --entrypoint python "$image" -m pip check > "$out/logs/pip-check.log"
python3 - <<'PY'
import json,re,subprocess
from pathlib import Path
out=Path('release-dist');p=json.loads(Path('docs/public-release-baseline.json').read_text())
log=(out/'logs/full-media.log').read_text()
assert f"Ran {p['full_media_tests']} tests" in log and re.search(r'^OK$',log,re.M) and 'skipped=' not in log
(out/'published-qualification.json').write_text(json.dumps({
 'mode':'unchanged published package; updated docs; no runtime rebuild',
 'reviewed_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'qualified_runtime_sha':p['qualified_source'],'full_media_tests':p['full_media_tests'],'skips':0,
 'platform':'Linux x86-64 CPU on owned EC2','image_id':p['image_id'],
 'original_complete_qualification':p['ci_url'],
 'public_release':'https://github.com/ariadne-mark/ariadne-mark/releases/tag/v'+p['version']
},indent=2)+'\n')
PY
printf '%s\n' 'Public hashes, unchanged runtime, full media, payload parity and docs passed.'
