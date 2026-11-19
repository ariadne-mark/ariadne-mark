FROM python:3.12-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS ffmpeg-build
ARG FFMPEG_BUILD_JOBS=2
RUN --mount=type=bind,source=scripts/build_ffmpeg.sh,target=/tmp/build_ffmpeg.sh,readonly \
    apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates \
        curl gnupg libx264-dev nasm pkg-config xz-utils zlib1g-dev \
    && bash /tmp/build_ffmpeg.sh

FROM node:26-bookworm-slim@sha256:5df79989ed685e09f0a98019db4cebfb22fb9df1a53c0161664a011f7ff6b0f1 AS node
FROM python:3.12-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS packaged

COPY --from=ffmpeg-build /opt/ffmpeg /opt/ffmpeg
ENV ARIADNE_VIDEO_DATA=/opt/ariadne-video
WORKDIR /data
RUN --mount=type=bind,from=node,source=/usr/local,target=/build-node,readonly \
    --mount=type=bind,source=.,target=/input,readonly \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates libstdc++6 libx264-164 zlib1g apt libapt-pkg7.0; \
    rm -rf /var/lib/apt/lists/*; \
    ln -s /opt/ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg; \
    ln -s /opt/ffmpeg/bin/ffprobe /usr/local/bin/ffprobe; \
    install /build-node/bin/node /usr/local/bin/node; \
    ln -s /build-node/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm; \
    mkdir /app; cp -a /input/. /app; chmod -R a+rX /app; cd /app; \
    python src/ariadne_mark/bootstrap_c2pa.py --allow-system --cache-dir /tmp/c2pa-bootstrap; \
    rm -rf /tmp/c2pa-bootstrap; \
    python -m pip install --no-cache-dir --require-hashes --no-build-isolation -r requirements/media-linux-py312.lock; \
    python scripts/build_release.py; \
    ariadne models fetch --engine media; \
    python -m pip check; \
    bash scripts/check_ffmpeg_runtime.sh; \
    rm /usr/local/bin/npm; \
    useradd --create-home --uid 10001 ariadne; \
    mkdir /state; chown ariadne:ariadne /data /state

# The build target also provisions a fresh, isolated wheel install for CI.
FROM packaged AS build
RUN --mount=type=bind,from=node,source=/usr/local/lib/node_modules/npm,target=/build-npm,readonly \
    mkdir -p /usr/local/lib/node_modules/npm \
    && cp -a /build-npm/. /usr/local/lib/node_modules/npm/ \
    && ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

FROM packaged AS runtime
USER ariadne
EXPOSE 8080
ENTRYPOINT ["ariadne"]
CMD ["--help"]
