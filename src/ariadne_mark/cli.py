"""Local CLI: no account, API key or hosted service required."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from ariadne_mark.errors import AriadneError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ariadne", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    models = commands.add_parser("models", help="Provision or check pinned TrustMark models")
    models.add_argument("action", choices=["fetch", "check"])
    dev = commands.add_parser("init-dev", help="Generate a DEVELOPMENT signing identity")
    dev.add_argument("directory", type=Path)
    mark = commands.add_parser("mark", help="Watermark, sign and verify a JPEG, PNG or MP4")
    mark.add_argument("source", type=Path)
    mark.add_argument("destination", type=Path)
    mark.add_argument("--publisher", required=True)
    mark.add_argument("--system", required=True)
    mark.add_argument("--system-version", required=True)
    mark.add_argument("--created-at", required=True, help="Actual generation/edit time, ISO 8601 with timezone")
    mark.add_argument("--action", choices=["created", "altered"], default="created")
    mark.add_argument("--identity", type=Path, required=True)
    mark.add_argument("--allow-dev", action="store_true")
    mark.add_argument("--timestamp-url", help="Optional TSA URL; explicitly enables timestamp network request")
    mark.add_argument("--visible", action="store_true", help="Add an AI-generated/AI-altered visible label")
    mark.add_argument("--audio-kind", choices=["none", "original", "synthetic", "unknown"], default="unknown")
    verify = commands.add_parser("verify", help="Verify supported claims without uploading media")
    verify.add_argument("source", type=Path)
    serve = commands.add_parser("serve", help="Run the self-hosted public verifier UI/API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--max-upload-mb", type=int, default=32)
    serve.add_argument("--feedback-url", help="Optional public feedback page URL")
    for sub in (mark, verify, serve):
        sub.add_argument("--registry", type=Path, help="Optional local recovery SQLite database")
        sub.add_argument("--trust-anchors", type=Path, help="PEM trust roots supplied by the operator")
        sub.add_argument("--threads", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        if args.command == "models":
            from ariadne_mark.watermark import fetch_models, check_models
            result = fetch_models() if args.action == "fetch" else check_models()
        elif args.command == "init-dev":
            from ariadne_mark.signing import create_development_identity
            create_development_identity(args.directory)
            result = {"development": True, "directory": str(args.directory), "publicly_trusted": False}
        else:
            from ariadne_mark.watermark import Watermarker
            from ariadne_mark.registry import Registry
            from ariadne_mark.pipeline import SDK
            marker = Watermarker(threads=args.threads)
            registry = Registry(args.registry) if args.registry else None
            sdk = SDK(marker, registry=registry, trust_anchors=args.trust_anchors)
            if args.command == "serve":
                from ariadne_mark.server import serve
                serve(sdk, host=args.host, port=args.port, max_upload_mb=args.max_upload_mb, feedback_url=args.feedback_url)
                return 0
            if args.command == "verify":
                result = sdk.verify(args.source)
                print(json.dumps(result, indent=2))
                if result["c2pa"]["status"] in {"invalid", "not_checked"} or result["watermark"]["status"] in {"invalid", "not_checked"} or result["token_mismatch"]:
                    return 2
                return 0
            from ariadne_mark.signing import SigningIdentity
            from ariadne_mark.provenance import ProvenanceRecord, GenerativeSystem, MediaKind, Action
            sdk.identity = SigningIdentity.from_directory(args.identity, allow_dev=args.allow_dev, timestamp_url=args.timestamp_url)
            record = ProvenanceRecord.create(
                publisher=args.publisher, system=GenerativeSystem(args.system, args.system_version),
                media_kind=MediaKind.VIDEO if args.source.suffix.lower() == ".mp4" else MediaKind.IMAGE,
                action=Action(args.action), created_at=datetime.fromisoformat(args.created_at.replace("Z", "+00:00")),
            )
            result = sdk.mark(args.source, args.destination, record, visible=args.visible, audio_kind=args.audio_kind)
        print(json.dumps(result, indent=2))
        return 0
    except (AriadneError, OSError, ValueError, ImportError) as exc:
        # Diagnostics go to stderr with a failing exit code, never unsigned success.
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
