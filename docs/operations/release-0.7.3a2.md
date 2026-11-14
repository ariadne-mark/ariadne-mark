# 0.7.3a2 adoption changes (candidate, not published)

SDK **0.7.3a2 candidate** · documentation updated **2026-11-14**.

This candidate follows an adoption pilot that integrated the public 0.7.2a1
release into a small generator service. Numbers below are from the
qualification EC2 host (2 vCPU, shared), one container at a time, limited to
2 CPUs and 4 GiB, using the pilot's 720p 24 fps 10 s clip and a 4 MP PNG. They
are single runs on one host, not service-level objectives. Older pilot
numbers belong to 0.7.2a1 and are not repeated here as candidate results.

## Install and disk budget

| Path | What it needs | Notes |
| --- | --- | --- |
| Docker build | ~9–10 GB free while building | Final image ~3.2 GB, build stage ~3.5 GB, plus BuildKit cache; less if base layers are cached |
| Wheel + `ariadne setup media --fetch-models` | ~2.2 GB | venv ~1.5 GB, models ~0.3 GB, Node runtime ~0.2 GB; about 2 minutes on the pilot host |

Use the wheel path where the Docker build does not fit. Downloaded runtime
resources go to `$XDG_CACHE_HOME/ariadne-mark` when that variable is set to an
absolute path, otherwise `~/.cache/ariadne-mark`; `--cache-dir`,
`ARIADNE_VIDEO_DATA` and `ARIADNE_VIDEOSEAL_MODEL` still take precedence. An
existing install at the old default keeps being used; nothing is moved. Video
provisioning uses a throwaway npm cache and no longer writes `~/.npm`. pip's own
cache follows pip's rules (`PIP_CACHE_DIR`, `XDG_CACHE_HOME`).

## Which image a kit runs

Build with `--iidfile`, then run the kit's `pin-image.sh IMAGE` on the Docker
host. The kit records the immutable image ID and the SDK version it was
initialized with; Compose uses the ID, and `kit export` / `kit serve` refuse an
image that reports another version. No tag is created or moved. See the
[deployment kit](deployment-kit.md).

## Running the verifier on a host

`ariadne kit serve DIR` now binds `127.0.0.1:8080` on a host (previously
`0.0.0.0:8080`). Use `--host` / `--port` to choose. Inside a container it binds
all interfaces of the container network; the kit's Compose file publishes only
its TLS edge.

## Memory with several video presets

Every preset now shares one Node worker per SDK. Before, each preset used in a
process started its own worker with identical models.

| One SDK: image + Economy5s + Economy2s + Resilient + verify | 0.7.3a1 | 0.7.3a2 |
| --- | --- | --- |
| Node worker processes | 3 | 1 |
| Peak resident memory (all processes) | 2.44 GiB | 1.33 GiB |
| Container memory peak (cgroup, includes page cache) | 2.20 GiB | 1.17 GiB |
| Export wall time, Economy5s / Economy2s / Resilient | 13.8 / 17.3 / 96.2 s | 13.7 / 16.0 / 92.6 s |

The image runtime (PyTorch/TrustMark) accounts for about 0.6 GiB of the
remainder and the Node worker for about 0.6 GiB. Exports of *different*
presets in one SDK now run one after another, as concurrent exports of one
preset already did. For parallel exports use one SDK per worker process.
`SDK.close()` stops the worker; no child process remains.

## Verification cost

A positive check of an intact export stops early (about 2.5 s for the 10 s
clip). A negative or blind check of a clean video decodes frames until a
budget, an early positive stop or the end of the file: the pilot observed
10–70 s on 0.7.2a1. Incomplete searches stay `not_checked`, never
`not_found`. Size a public verifier separately from exports; it serves one
inference job at a time and answers `429` while busy.

## Trusted claims and scope

A trusted C2PA signer can no longer switch off the operator's own primary
watermark scan (video-Q for MP4, Python-Q for images). `completed_schemes`
lists only declared checks; supplemental readers appear in
`supplemental_completed_schemes`. `SDK.mark` refuses an encoder outside the
SDK's own `verification_scope`. See the [API reference](../reference/api-cli.md).

## Production timestamping boundary

Production exports still require a trusted TSA. The pinned C2PA pair cannot
send TSA authentication; the reasons, the c2pa-rs 0.92.0 upgrade path and what
the SDK enforces now are in [production onboarding](production-onboarding.md).
A TSA that accepts TCP but never answers fails the export after the native
client's fixed 30 s timeout; nothing is published.

## Not changed

Economy5s remains the default; Economy2s and Resilient keep their cadence and
meaning. Watermark strength, models, the export read-back gate, the pinned
C2PA pair and dependency locks are unchanged.
