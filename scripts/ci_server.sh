#!/bin/bash
set -euo pipefail
# Trusted maintainer dispatch only. All SDK tests execute inside bounded EC2
# containers. Never register this runner for automatic public-fork execution.
root=$(pwd)
out="$root/release-dist"
work="$root/.ci-work"
mkdir -p "$out/logs" "$work/fixtures" "$work/install"
run_id="${GITHUB_RUN_ID:-manual}-$(git rev-parse --short HEAD)"
image="ariadne-mark:ci-$run_id"
build_image="$image-build"
stage() { echo "$1" | tee "$out/current-stage.txt"; date -u +%FT%TZ >> "$out/current-stage.txt"; }
stage build-clean-source
docker build -t "$image" . > "$out/logs/docker-build.log" 2>&1
docker build --target build -t "$build_image" . > "$out/logs/docker-build-stage.log" 2>&1
container=$(docker create "$image" --help)
docker cp "$container":/opt/dist/. "$out/"
docker rm "$container" >/dev/null
stage full-installed-media
docker run --rm --network none --cpus 2 --memory 6g --read-only --tmpfs /tmp:rw,noexec,nosuid,size=512m \
  -e ARIADNE_MEDIA_TESTS=1 -w /app --entrypoint python "$image" \
  -m unittest discover -s tests -t . -v > "$out/logs/full-media.log" 2>&1
stage core-matrix
for py in 3.11 3.12 3.13 3.14; do
  docker run --rm --network none --cpus 2 --memory 1g --user 65534:65534 --read-only --tmpfs /tmp:rw,nosuid,size=512m \
    -v "$out:/artifacts:ro" -v "$root/tests:/tests:ro" -v "$root/examples:/examples:ro" -w / --entrypoint sh \
    "python:$py-slim" -c 'python --version; python -m pip install --no-index --no-deps --no-cache-dir --target /tmp/sdk /artifacts/*.whl; PYTHONPATH=/tmp/sdk python -m unittest discover -s /tests -t / -v' \
    > "$out/logs/core-$py.log" 2>&1
done
stage clean-wheel-install
sudo chown -R 10001:10001 "$work"
docker run --rm --network none --cpus 2 --memory 1g --user 10001:10001 -v "$work/fixtures:/fixtures" \
  -v "$root/scripts:/scripts:ro" --entrypoint python "$build_image" /scripts/ci_prepare_fixtures.py /fixtures > "$out/logs/fixture-preparation.log" 2>&1
for engine in video media; do
  # Explicit setup is online; later processing smoke is repeated offline below.
  docker run --name "ariadne-ci-install-$run_id-$engine" --cpus 2 --memory 6g --user 10001:10001 \
    -v "$out:/artifacts:ro" -v "$root/scripts:/scripts:ro" -v "$work/fixtures:/fixtures:ro" -v "$work/install:/work" \
    -w /work --entrypoint bash "$build_image" /scripts/ci_clean_install.sh "$engine" \
    > "$out/logs/clean-wheel-$engine.log" 2>&1
  docker run --rm --network none --cpus 2 --memory 6g --user 10001:10001 \
    -v "$root/scripts:/scripts:ro" -v "$work/fixtures:/fixtures:ro" -v "$work/install:/work" \
    -e "ARIADNE_VIDEO_DATA=/work/$engine-video-runtime" -w /work --entrypoint "/work/$engine-venv/bin/python" "$build_image" \
    /scripts/ci_install_smoke.py "$engine" "/work/$engine-offline-smoke" /fixtures > "$out/logs/offline-wheel-$engine.jsonl" 2>&1
done
stage deployment-kit
# Provision the independent validator and pinned edge only during explicit setup.
sudo mkdir -p "$work/kit" "$work/tools"
sudo chown "$(id -u):$(id -g)" "$work/kit" "$work/tools"
python3 scripts/fetch_external_validator.py "$work/tools" > "$out/logs/external-validator.json"
docker pull nginx@sha256:583b7f2fce1cdb8da5ad5c39ebd3c33b98b87d493190e548bdee1fa8c619c311 > "$out/logs/edge-provisioning.log" 2>&1
python3 scripts/ci_kit_acceptance.py "$image" "$work/kit" "$work/fixtures" "$out/kit-acceptance" "$work/tools/c2patool" > "$out/logs/kit-acceptance.jsonl" 2>&1
stage traceability-and-inventory
python3 scripts/check_requirements.py > "$out/logs/requirements.log"
python3 scripts/check_runtime_locks.py > "$out/logs/runtime-locks.log"
docker run --rm --network none --entrypoint python "$image" -m pip check > "$out/logs/pip-check.log"
docker run --rm --network none --entrypoint python "$image" -c 'import importlib.metadata as m,json; print(json.dumps({p.metadata["Name"]:p.version for p in m.distributions()},indent=2))' > "$out/installed-packages.json"
docker run --rm --network none -w /app --entrypoint python "$image" scripts/media_inventory.py > "$out/native-media-inventory.json"
docker run --rm --network none -v "$out:/artifacts:ro" -w /app --entrypoint python "$image" scripts/check_installed_payload.py /artifacts /app > "$out/logs/package-parity.json"
python3 scripts/package_release_evidence.py > "$out/logs/release-manifest.log"
stage complete
