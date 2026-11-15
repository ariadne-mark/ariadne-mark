"""A small development worker: one resident SDK, serial bounded jobs, private outputs.

Use only for newly generated visual files. This is an integration example, not a
public upload endpoint or a production credential manager. See own-files.md.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROFILES = {'economy_5s', 'economy_2s', 'resilient'}


def load_jobs(manifest):
    """Validate all operator-supplied jobs before creating an SDK or any output."""
    manifest = Path(manifest).resolve()
    data = json.loads(manifest.read_text())
    if set(data) != {'schema_version', 'publisher', 'system', 'jobs'} or data['schema_version'] != 1:
        raise ValueError('Expected schema_version=1, publisher, system and jobs')
    if not isinstance(data['publisher'], str) or not data['publisher'].strip():
        raise ValueError('Supply a truthful public publisher')
    if not isinstance(data['system'], dict) or set(data['system']) != {'name', 'version'}:
        raise ValueError('Supply public system name and version')
    if not all(isinstance(v, str) and v.strip() for v in data['system'].values()):
        raise ValueError('System values must be non-empty strings')
    if not isinstance(data['jobs'], list) or not 1 <= len(data['jobs']) <= 100:
        raise ValueError('Use 1–100 jobs per batch; admission queue belongs to your app')
    jobs, identifiers, inputs, outputs = [], set(), set(), set()
    for raw in data['jobs']:
        required = {'job_id', 'source', 'destination', 'generated_at'}
        if not isinstance(raw, dict) or not required <= set(raw) or set(raw) - required - {'video_profile', 'audio_kind'}:
            raise ValueError('Unexpected job fields')
        job_id = raw['job_id']
        if not isinstance(job_id, str) or not job_id.strip() or job_id in identifiers:
            raise ValueError('Use a unique non-empty job_id')
        if not isinstance(raw['generated_at'], str):
            raise ValueError('generated_at must be the actual per-job ISO 8601 time')
        created = datetime.fromisoformat(raw['generated_at'].replace('Z', '+00:00'))
        if created.tzinfo is None or created.utcoffset() is None or created > datetime.now(timezone.utc):
            raise ValueError('generated_at requires a timezone and cannot be in the future')
        source = (manifest.parent / raw['source']).resolve()
        destination = (manifest.parent / raw['destination']).resolve()
        if not source.is_file():
            raise ValueError('Input is not a regular file: ' + str(source))
        if source.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.mp4'}:
            raise ValueError('Use JPEG/PNG or a supported silent SDR MP4')
        video = source.suffix.lower() == '.mp4'
        if destination.suffix.lower() not in ({'.mp4'} if video else {'.png', '.jpg', '.jpeg'}):
            raise ValueError('Destination must match the media kind')
        receipt = destination.with_name(destination.name + '.receipt.json')
        if destination.exists() or receipt.exists() or source == destination or destination in outputs:
            raise ValueError('Use fresh, unique destination and receipt paths')
        if video and raw.get('audio_kind') != 'none':
            raise ValueError('This example requires audio_kind=none and a silent input')
        if not video and ('video_profile' in raw or 'audio_kind' in raw):
            raise ValueError('Video options do not apply to images')
        if raw.get('video_profile', 'economy_5s') not in PROFILES:
            raise ValueError('Unknown video_profile')
        identifiers.add(job_id); inputs.add(source); outputs.add(destination)
        jobs.append(dict(job_id=job_id, source=source, destination=destination,
                         created_at=created, video=video, profile=raw.get('video_profile')))
    if inputs & outputs or any(p.with_name(p.name + '.receipt.json') in outputs | inputs for p in outputs):
        raise ValueError('Batch input/output/receipt paths must not collide')
    return data, jobs


def run(manifest, identity_dir, registry_path):
    # Development only: the production kit owns credential, timestamp and trust setup.
    data, jobs = load_jobs(manifest)
    from ariadne_mark.pipeline import SDK
    from ariadne_mark.provenance import Action, GenerativeSystem, MediaKind, ProvenanceRecord
    from ariadne_mark.registry import Registry
    from ariadne_mark.signing import SigningIdentity
    from ariadne_mark.watermark import LazyWatermarker
    identity = SigningIdentity.from_directory(Path(identity_dir), allow_dev=True)
    if not identity.development:
        raise ValueError('This example requires a development identity; use the production kit for real credentials')
    # Construct after a process fork, then reuse for every accepted queue job.
    with SDK(identity=identity, registry=Registry(Path(registry_path)),
             marker=LazyWatermarker(threads=2), verification_scope='current') as sdk:
        for job in jobs:
            record = ProvenanceRecord.create(publisher=data['publisher'],
                system=GenerativeSystem(**data['system']),
                media_kind=MediaKind.VIDEO if job['video'] else MediaKind.IMAGE,
                action=Action.CREATED, created_at=job['created_at'])
            options = {'audio_kind': 'none'} if job['video'] else {}
            if job['profile'] is not None:
                options['video_profile'] = job['profile']
            receipt = sdk.mark(job['source'], job['destination'], record, **options)
            report = sdk.verify(job['destination'])
            if (report['c2pa'].get('signature') != 'valid'
                    or report['c2pa'].get('token') != receipt['token']
                    or report['watermark'].get('token') != receipt['token']
                    or report['c2pa'].get('record') != record.to_dict()):
                raise RuntimeError('Independent local read-back failed; keep staging private and investigate')
            print(json.dumps({'job_id': job['job_id'], 'status': 'accepted_in_private_staging',
                'output': str(job['destination']), 'receipt': receipt,
                'verification': report}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--allow-dev', action='store_true', required=True)
    args = parser.parse_args()
    try:
        run(args.manifest, args.identity, args.registry)
    except Exception as exc:
        print(json.dumps({'status': 'stopped', 'error': type(exc).__name__, 'message': str(exc),
                          'publication': 'No original-file fallback; inspect earlier accepted jobs separately'}), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
