FROM node:24-bookworm-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c AS node
FROM python:3.12-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS build
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY src/ariadne_mark/bootstrap_c2pa.py src/ariadne_mark/c2pa-bootstrap.json /bootstrap/
RUN python /bootstrap/bootstrap_c2pa.py --allow-system --cache-dir /opt/bootstrap-cache \
    && python -m pip install --no-cache-dir setuptools==84.2.1
RUN python -m pip install --no-cache-dir torch==2.14.1 torchvision==0.29.1 \
    --index-url https://download.pytorch.org/whl/cpu
ENV ARIADNE_VIDEO_DATA=/opt/ariadne-video
WORKDIR /app
COPY . /app
RUN python scripts/build_release.py && ariadne models fetch && python -m pip check

FROM python:3.12-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN rm -rf /usr/local/lib/python3.12/site-packages/*
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin/ariadne /usr/local/bin/ariadne
COPY --from=build /opt/ariadne-video /opt/ariadne-video
COPY --from=build /opt/dist /opt/dist
COPY --from=build /app /app
ENV ARIADNE_VIDEO_DATA=/opt/ariadne-video
RUN useradd --create-home --uid 10001 ariadne && mkdir /data && chown ariadne:ariadne /data
USER ariadne
WORKDIR /data
EXPOSE 8080
ENTRYPOINT ["ariadne"]
CMD ["--help"]
