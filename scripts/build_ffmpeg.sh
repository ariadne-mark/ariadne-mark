#!/bin/bash
# Build the local media CLI from FFmpeg's signed release. Called by Docker.
set -euo pipefail

version=9.0.2
fingerprint=FCF986EA15E6E293A5644F10B4322F04D67658D8
archive="ffmpeg-$version.tar.xz"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cd "$work"
export GNUPGHOME="$work/gnupg"
install -d -m 0700 "$GNUPGHOME"
curl=(curl --proto '=https' --tlsv1.2 -fsSL --retry 3 --max-time 120)
"${curl[@]}" https://ffmpeg.org/ffmpeg-devel.asc -o signing-key.asc
"${curl[@]}" "https://ffmpeg.org/releases/$archive" -o "$archive"
"${curl[@]}" "https://ffmpeg.org/releases/$archive.asc" -o "$archive.asc"
gpg --batch --import signing-key.asc
gpg --batch --status-fd 1 --verify "$archive.asc" "$archive" |
    awk -v key="$fingerprint" '$2 == "VALIDSIG" && ($3 == key || $NF == key) { valid=1 } END { exit !valid }'

tar -xJf "$archive"
cd "ffmpeg-$version"
./configure \
    --prefix=/opt/ffmpeg --enable-gpl --enable-libx264 --enable-zlib \
    --disable-autodetect --disable-everything --disable-network --disable-doc \
    --disable-debug --disable-ffplay --disable-libxml2 \
    --enable-protocol=file,pipe \
    --enable-demuxer=mov,image2,image2pipe,matroska,rawvideo \
    --enable-muxer=mov,mp4,matroska,null,image2,image2pipe,rawvideo \
    --enable-indev=lavfi \
    --enable-decoder=h264,hevc,aac,png,mjpeg,mpeg4,rawvideo,wrapped_avframe,pcm_s16le \
    --enable-encoder=libx264,aac,png,mjpeg,mpeg4,rawvideo,wrapped_avframe,pcm_s16le \
    --enable-parser=h264,hevc,aac,png,mjpeg,mpeg4video \
    --enable-bsf=aac_adtstoasc,extract_extradata,h264_mp4toannexb,hevc_mp4toannexb \
    --enable-filter=anull,aformat,aresample,asetpts,asettb,concat,crop,format,null,rotate,scale,select,setpts,settb,sine,testsrc,testsrc2,transpose,trim
make -j"${FFMPEG_BUILD_JOBS:-2}" ffmpeg ffprobe
install -D -m 0755 ffmpeg /opt/ffmpeg/bin/ffmpeg
install -D -m 0755 ffprobe /opt/ffmpeg/bin/ffprobe
install -d /opt/ffmpeg/source
install -m 0644 "../$archive" "../$archive.asc" COPYING.GPLv2 /opt/ffmpeg/source
sha256sum "/opt/ffmpeg/source/$archive"
