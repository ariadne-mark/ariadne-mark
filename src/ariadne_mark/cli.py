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
    reports = commands.add_parser("report", help="Generate verifier keys or independently verify a signed receipt")
    report_commands = reports.add_subparsers(dest="report_command", required=True)
    report_keygen = report_commands.add_parser("keygen")
    report_keygen.add_argument("directory", type=Path)
    report_verify = report_commands.add_parser("verify")
    report_verify.add_argument("receipt", type=Path)
    report_verify.add_argument("--public-key", required=True, type=Path, help="Independently pinned Ed25519 PEM public key")
    report_verify.add_argument("--asset", type=Path, help="Also match the exact submitted file")
    report_verify.add_argument("--verifier-id", help="Require the expected public verifier identifier")
    profile = commands.add_parser("profile", help="Plan requirements and check a product configuration offline")
    profile_commands = profile.add_subparsers(dest="profile_command", required=True)
    profile_commands.add_parser("init", help="Print a configuration template; null means unknown")
    profile_commands.add_parser("sources", help="Show the versioned source catalog and review limits")
    feedback = commands.add_parser("feedback-summary", help="Read aggregate efficacy feedback counters; no media or user data")
    feedback.add_argument("database", type=Path)
    profile_check = profile_commands.add_parser("check", help="Print a requirement plan; does not certify compliance")
    profile_check.add_argument("config", type=Path)
    profile_check.add_argument("--as-of", help="Evaluate a YYYY-MM-DD scenario (does not update source knowledge)")
    models = commands.add_parser("models", help="Provision or check pinned watermark models")
    models.add_argument("action", choices=["fetch", "check"])
    models.add_argument("--engine", choices=["all", "trustmark", "videoseal", "video"], default="all")
    dev = commands.add_parser("init-dev", help="Generate a DEVELOPMENT signing identity")
    dev.add_argument("directory", type=Path)
    mark = commands.add_parser("mark", help="Watermark, sign and verify a JPEG, PNG or MP4")
    mark.add_argument("source", type=Path)
    mark.add_argument("destination", type=Path)
    mark.add_argument("--profile", type=Path, help="Product configuration; applies export settings and records assessment")
    mark.add_argument("--publisher")
    mark.add_argument("--system")
    mark.add_argument("--system-version")
    mark.add_argument("--created-at", required=True, help="Actual generation/edit time, ISO 8601 with timezone")
    mark.add_argument("--action", choices=["created", "altered"], default="created")
    mark.add_argument("--identity", type=Path, required=True)
    mark.add_argument("--allow-dev", action="store_true")
    mark.add_argument("--timestamp-url", help="Optional TSA URL; explicitly enables timestamp network request")
    mark.add_argument("--visible", action="store_true", help="Add an AI-generated/AI-altered visible label")
    mark.add_argument("--video-profile", choices=["economy_5s", "economy_2s", "resilient", "fast"],
                      help="CPU video preset (default: economy_5s; fast is legacy)")
    mark.add_argument("--audio-kind", choices=["none", "original", "synthetic", "unknown"], default="unknown")
    verify = commands.add_parser("verify", help="Verify supported claims without uploading media")
    verify.add_argument("source", type=Path)
    verify.add_argument("--strict", action="store_true", help="Require a valid credential from a trusted issuer")
    recover = commands.add_parser("recover", help="Recover a signed C2PA manifest using a local registry; media stays unchanged")
    recover.add_argument("source", type=Path)
    recover.add_argument("destination", type=Path, help="New .c2pa manifest-store file")
    mark.add_argument("--publish-manifest", action="store_true", help="Explicitly approve publishing the full signed manifest/history through a repository")
    serve = commands.add_parser("serve", help="Run the self-hosted public verifier UI/API")
    serve.add_argument("--public-manifests", action="store_true", help="Enable read-only C2PA resolution for explicitly published manifests")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--max-upload-mb", type=int, default=512)
    serve.add_argument("--production", action="store_true", help="Require configured issuer roots before serving")
    serve.add_argument("--feedback-url", help="Optional public feedback page URL")
    serve.add_argument("--feedback-db", type=Path, help="Persist anonymous category counts only, in a writable state directory")
    serve.add_argument("--public-sources", type=Path, help="Operator-reviewed public provider/system names; other free-text metadata is withheld")
    serve.add_argument("--verification-timeout", type=float, default=180,
                       help="Whole-job model deadline in seconds; timed-out worker and children are terminated")
    for sub in (verify, serve):
        sub.add_argument("--report-key", type=Path, help="Separate Ed25519 verifier-report private key")
        sub.add_argument("--verifier-id", help="Stable public URL or URN identifying this verifier")
    verify.add_argument("--report-output", type=Path, help="Write a portable signed receipt; requires --report-key and --verifier-id")
    for sub in (mark, verify, serve, recover):
        sub.add_argument("--registry", type=Path, help="Optional local recovery SQLite database")
        sub.add_argument("--trust-anchors", type=Path, help="PEM trust roots supplied by the operator")
        sub.add_argument("--tsa-trust-anchors", type=Path, help="Optional separate PEM roots for private timestamp authorities")
        sub.add_argument("--threads", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        report_signer = None
        if args.command in {"verify", "serve"}:
            if bool(args.report_key) != bool(args.verifier_id):
                raise ValueError("Supply --report-key and --verifier-id together")
            if args.report_key:
                from ariadne_mark.reports import ReportSigner
                report_signer = ReportSigner.from_file(args.report_key, args.verifier_id)
            if args.command == "verify" and args.report_output and report_signer is None:
                raise ValueError("--report-output requires a report signing key and verifier ID")
        if args.command == "report":
            from ariadne_mark.reports import generate_report_key, verify_report, MAX_REPORT_BYTES
            if args.report_command == "keygen":
                result = generate_report_key(args.directory)
            else:
                if args.receipt.stat().st_size > MAX_REPORT_BYTES + 65536:
                    raise ValueError("Receipt exceeds maximum size")
                from ariadne_mark.reports import _strict_json
                payload = verify_report(_strict_json(args.receipt.read_bytes()), args.public_key.read_bytes(),
                                        asset=args.asset, verifier_id=args.verifier_id)
                result = {"signature": "valid", "asset_checked": args.asset is not None,
                          "trust_basis": "caller_pinned_public_key", "payload": payload}
        elif args.command == "feedback-summary":
            from ariadne_mark.public_verifier import FeedbackStore
            if not args.database.is_file():
                raise ValueError("Feedback database does not exist")
            result = FeedbackStore.read_summary(args.database)
        elif args.command == "profile":
            from ariadne_mark.profiles import CATALOG, template, load, evaluate, parse_date
            if args.profile_command == "init":
                result = template()
            elif args.profile_command == "sources":
                result = CATALOG
            else:
                result = evaluate(load(args.config), as_of=parse_date(args.as_of, "as-of") if args.as_of else None)
                print(json.dumps(result, indent=2))
                return 2 if result["configuration_status"] == "invalid" else 3 if result["assessment_status"] != "configuration_reviewed" else 0
        elif args.command == "models":
            from ariadne_mark import watermark, videoseal, videoq
            result = {}
            for name, engine in (("trustmark", watermark), ("videoseal", videoseal), ("video", videoq)):
                if args.engine in {"all", name}:
                    import importlib.util
                    dependency = {"trustmark": "trustmark", "videoseal": "torch"}.get(name)
                    if args.engine == "all" and dependency and importlib.util.find_spec(dependency) is None:
                        result[name] = {"status": "skipped", "reason": "optional_dependency_not_installed", "dependency": dependency}
                        continue
                    result[name] = engine.fetch_models() if args.action == "fetch" else engine.check_models()
        elif args.command == "init-dev":
            from ariadne_mark.signing import create_development_identity
            create_development_identity(args.directory)
            result = {"development": True, "directory": str(args.directory), "publicly_trusted": False}
        else:
            selected_profile = None
            if args.command == "mark":
                if args.profile:
                    from ariadne_mark.profiles import load, evaluate
                    selected_profile = load(args.profile)
                    report = evaluate(selected_profile)
                    if not report["export_supported"]:
                        raise ValueError("Profile configuration blocks export: " + "; ".join(x["message"] for x in report["findings"] if x["level"] == "error"))
                    expected = (selected_profile["publisher"], selected_profile["system"]["name"], selected_profile["system"]["version"])
                    supplied = (args.publisher, args.system, args.system_version)
                    if any(actual is not None and actual != wanted for actual, wanted in zip(supplied, expected)):
                        raise ValueError("Publisher/system overrides conflict with profile")
                    args.publisher, args.system, args.system_version = expected
                if not args.publisher or not args.system or not args.system_version:
                    raise ValueError("Supply --publisher, --system and --system-version, or a complete --profile")
            from ariadne_mark.watermark import LazyWatermarker
            from ariadne_mark.registry import Registry
            from ariadne_mark.pipeline import SDK
            marker = LazyWatermarker(threads=args.threads)
            registry = Registry(args.registry, read_only=args.command != "mark") if args.registry else None
            from ariadne_mark.videoq import VideoWatermarker
            from ariadne_mark.video.policy import DEFAULT_PROFILE
            sdk = SDK(marker, registry=registry, trust_anchors=args.trust_anchors, tsa_trust_anchors=args.tsa_trust_anchors,
                      video_marker=VideoWatermarker(threads=args.threads,
                          profile=getattr(args, "video_profile", None) or DEFAULT_PROFILE))
            if args.command == "serve":
                from ariadne_mark.server import serve
                from ariadne_mark.isolated_verifier import IsolatedVerifier
                sdk.close()
                isolated = IsolatedVerifier(registry=args.registry, trust_anchors=args.trust_anchors,
                                            threads=args.threads, timeout=args.verification_timeout, tsa_trust_anchors=args.tsa_trust_anchors)
                serve(isolated, host=args.host, port=args.port, max_upload_mb=args.max_upload_mb,
                      feedback_url=args.feedback_url, production=args.production,
                      public_sources=args.public_sources, feedback_db=args.feedback_db, report_signer=report_signer,
                      public_manifests=args.public_manifests)
                return 0
            if args.command == "recover":
                result = sdk.recover_manifest(args.source, args.destination)
                print(json.dumps(result, indent=2))
                return 0
            if args.command == "verify":
                if report_signer is not None:
                    from ariadne_mark.reports import file_digest
                    before = file_digest(args.source)
                result = sdk.verify(args.source)
                if report_signer is not None:
                    from ariadne_mark.public_verifier import public_report
                    from ariadne_mark.reports import file_digest
                    from ariadne_mark.signing import MIME
                    digest, size = file_digest(args.source)
                    if (digest, size) != before:
                        raise ValueError("Asset changed during verification; no signed report issued")
                    result['signed_report'] = report_signer.sign(public_report(result), sha256=digest,
                        size_bytes=size, media_type=MIME[args.source.suffix.lower()])
                    if args.report_output:
                        with args.report_output.open('x') as stream:
                            json.dump(result['signed_report'], stream, indent=2)
                print(json.dumps(result, indent=2))
                if args.strict and (result["c2pa"]["status"] != "verified_claim" or result["c2pa"]["issuer_trust"] != "trusted" or result["c2pa"].get("development_identity")):
                    return 2
                if result["c2pa"]["status"] in {"invalid", "not_checked", "expired_credential"} or result["watermark"]["status"] in {"invalid", "not_checked", "single_observation"} or result["token_mismatch"]:
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
            result = sdk.mark(args.source, args.destination, record, visible=args.visible, audio_kind=args.audio_kind,
                              profile=selected_profile, video_profile=args.video_profile, publish_manifest=args.publish_manifest)
        print(json.dumps(result, indent=2))
        return 0
    except (AriadneError, OSError, ValueError, ImportError) as exc:
        # Diagnostics go to stderr with a failing exit code, never unsigned success.
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
