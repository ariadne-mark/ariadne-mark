FROM python:3.12-slim-trixie
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Install CPU wheels first so the media extra does not pull CUDA packages.
RUN python -m pip install --no-cache-dir setuptools==84.2.1
RUN python -m pip install --no-cache-dir torch==2.14.1 torchvision==0.29.1 \
    --index-url https://download.pytorch.org/whl/cpu
WORKDIR /app
COPY . /app
RUN python -m pip install --no-cache-dir '.[media]' \
    && ariadne models fetch \
    && python -m pip check
RUN useradd --create-home --uid 10001 ariadne && mkdir /data && chown ariadne:ariadne /data
USER ariadne
WORKDIR /data
EXPOSE 8080
ENTRYPOINT ["ariadne"]
CMD ["--help"]
