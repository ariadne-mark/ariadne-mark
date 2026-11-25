#!/usr/bin/env python3
"""Validate assessment fixtures offline on the qualified Ariadne native runtime."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time


TIME = re.compile(
    r"(?P<second>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d{1,9}))?(?P<zone>Z|[+-]\d{2}:\d{2})",
    re.ASCII,
)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
CLOCK_VAR = "ARIADNE_ASSESSMENT_CLOCK"
NANOSECONDS = 1_000_000_000


def epoch_ns(value):
    match = TIME.fullmatch(value) if isinstance(value, str) else None
    if match is None or match["zone"] == "-00:00":
        raise ValueError("Use RFC 3339 with a known offset and up to nine fractional digits")
    offset = match["zone"]
    if offset != "Z" and (int(offset[1:3]) > 23 or int(offset[4:6]) > 59):
        raise ValueError("Invalid RFC 3339 UTC offset")
    moment = datetime.fromisoformat(match["second"] + offset)
    delta = moment - EPOCH
    seconds = delta.days * 86400 + delta.seconds
    return seconds * NANOSECONDS + int((match["fraction"] or "").ljust(9, "0"))


def pem_bundle(path):
    from ssl import PROTOCOL_TLS_CLIENT, SSLContext

    with path.open("rb") as stream:
        data = stream.read(1024 * 1024 + 1).decode("ascii")
    if len(data) > 1024 * 1024:
        raise ValueError("Trust list exceeds 1 MiB")
    cert = re.compile(r"-----BEGIN CERTIFICATE-----[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----")
    blocks = cert.findall(data)
    if not blocks or data.count("-----BEGIN") != len(blocks) or data.count("-----END") != len(blocks):
        raise ValueError("Pass a PEM bundle of X.509 trust anchors")
    verifier = SSLContext(PROTOCOL_TLS_CLIENT)
    for block in blocks:
        verifier.load_verify_locations(cadata=block)


def run_reader(args, requested):
    if time.time_ns() != requested:
        raise RuntimeError("The assessment clock is not active in the validation subprocess")
    for trust_list in (args.trust_list, args.tsa_trust_list):
        pem_bundle(trust_list)
    from ariadne_mark.signing import context
    import c2pa

    with context(args.trust_list, tsa_trust_anchors=args.tsa_trust_list) as ctx:
        with c2pa.Reader(args.asset, context=ctx) as reader:
            raw = reader.crjson()
    report = json.loads(raw)
    manifests = report.get("manifests")
    if not isinstance(manifests, list) or not manifests:
        raise RuntimeError("The native reader yielded no manifest assessment")
    for manifest in manifests:
        results = manifest.get("validationResults", {})
        observed = manifest.get("validationTime", results.get("validationTime"))
        if epoch_ns(observed) != requested:
            raise RuntimeError("The native crJSON did not record the requested evaluation time")
    sys.stdout.write(raw.rstrip() + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path, help="Local JPEG, PNG or MP4 fixture")
    parser.add_argument("--trust-list", required=True, type=Path, help="Test C2PA Trust List (PEM)")
    parser.add_argument("--tsa-trust-list", required=True, type=Path, help="Test C2PA TSA Trust List (PEM)")
    parser.add_argument("--validation-time", required=True, help="RFC 3339 instant")
    parser.add_argument("--clock-library", required=True, type=Path, help="Locally built, trusted assessment clock")
    parser.add_argument("--clock-sha256", required=True, help="Expected hash of the locally built library")
    internal = sys.argv[1:2] == ["--ariadne-assessment-child"]
    args = parser.parse_args(sys.argv[2:] if internal else sys.argv[1:])
    try:
        if platform.system() != "Linux" or platform.machine() != "x86_64" or sys.version_info[:2] != (3, 12):
            raise ValueError("Use the qualified Linux x86-64, Python 3.12 runtime")
        requested = epoch_ns(args.validation_time)
        seconds, nanos = divmod(requested, NANOSECONDS)
        stamp = f"{seconds}:{nanos}"
        library = args.clock_library.resolve(strict=True)
        if re.search(r"[:\s]", str(library)):
            raise ValueError("Build the clock library at a path without spaces or colons")
        if not re.fullmatch(r"[a-f0-9]{64}", args.clock_sha256):
            raise ValueError("Clock SHA-256 must be 64 lowercase hex digits")
        with library.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != args.clock_sha256:
                raise ValueError("The assessment clock library hash did not match")
        if internal:
            if os.environ.get(CLOCK_VAR) != stamp or os.environ.get("LD_PRELOAD") != str(library):
                raise RuntimeError("Invalid assessment subprocess environment")
            run_reader(args, requested)
            return 0
        if CLOCK_VAR in os.environ:
            raise RuntimeError("Unexpected inherited assessment clock")
        environment = dict(os.environ)
        environment.update({CLOCK_VAR: stamp, "LD_PRELOAD": str(library), "TZ": "UTC"})
        environment.pop("FAKETIME", None)
        return subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--ariadne-assessment-child", *sys.argv[1:]],
            env=environment, stdin=subprocess.DEVNULL, timeout=90, check=False,
        ).returncode
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"C2PA assessment failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
