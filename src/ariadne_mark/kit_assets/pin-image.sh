#!/usr/bin/env bash
# Pin this kit's SDK image by immutable image ID (run on the Docker host).
# Usage: ./pin-image.sh IMAGE_REFERENCE   (a local tag or image ID; never pulls)
set -euo pipefail
ref=${1:?usage: ./pin-image.sh IMAGE_REFERENCE}
cd "$(dirname "$0")"
[ -f .env ] || { echo 'Run inside a kit directory created by kit init' >&2; exit 2; }
want=$(sed -n 's/^KIT_SDK_VERSION=//p' .env)
[ -n "$want" ] || { echo 'This kit predates image pinning: add KIT_SDK_VERSION=<expected SDK version> to .env first' >&2; exit 2; }
id=$(docker image inspect --format '{{.Id}}' "$ref") || { echo "No local image $ref; build it first" >&2; exit 2; }
# Ask the image itself what it installs, offline and without mounts.
info=$(docker run --rm --network none --entrypoint ariadne "$id" runtime identity)
got=$(printf '%s\n' "$info" | sed -n 's/.*"sdk_version": *"\([^"]*\)".*/\1/p')
record=$(printf '%s\n' "$info" | sed -n 's/.*"record_sha256": *"\([0-9a-f]*\)".*/\1/p')
if [ "$got" != "$want" ]; then
  echo "Refusing: $ref ($id) provides SDK '$got' but this kit expects '$want'" >&2
  exit 3
fi
tmp=$(mktemp .env.XXXXXX)
grep -v -e '^KIT_SDK_IMAGE=' -e '^KIT_SDK_RECORD_SHA256=' .env > "$tmp"
printf 'KIT_SDK_IMAGE=%s\nKIT_SDK_RECORD_SHA256=%s\n' "$id" "$record" >> "$tmp"
chmod --reference=.env "$tmp" 2>/dev/null || chmod 600 "$tmp"
mv "$tmp" .env
echo "Pinned SDK $got image $id (installed RECORD sha256 $record)"
