#!/usr/bin/env python3
"""Replay an Ariadne C2PA assessment corpus from its expected native outputs."""
import argparse
from hashlib import file_digest
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    with path.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def indexed_path(root, artifact):
    path = (root / artifact['path']).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file() or digest(path) != artifact['sha256']:
        raise ValueError(f"Assessment artifact did not match manifest: {artifact['path']}")
    return path


def replay(root, clock, clock_hash):
    matrix = json.loads((root / 'CASE-MATRIX.json').read_text())
    cli = Path(__file__).with_name('c2pa_assess.py')
    if digest(cli) != matrix['assessor_sha256']:
        raise ValueError('Use the exact assessor source recorded for this corpus')
    for case in matrix['cases']:
        asset, issuers, tsa = [indexed_path(root, case[name]) for name in ('asset', 'issuer_list', 'tsa_list')]
        expected = indexed_path(root, case['crjson']).read_bytes()
        stderr = indexed_path(root, case['diagnostic']).read_bytes()
        result = subprocess.run(
            [sys.executable, cli, asset, '--trust-list', issuers, '--tsa-trust-list', tsa,
             '--validation-time', case['validation_time'], '--clock-library', clock, '--clock-sha256', clock_hash],
            capture_output=True, timeout=100, check=False)
        # Compare complete structured output. Whitespace and key order have no semantics.
        actual_report = json.loads(result.stdout) if result.stdout else None
        expected_report = json.loads(expected) if expected else None
        actual_diagnostic = json.loads(result.stderr) if result.stderr else None
        expected_diagnostic = json.loads(stderr) if stderr else None
        if (result.returncode, actual_report, actual_diagnostic) != (case['exit_code'], expected_report, expected_diagnostic):
            raise RuntimeError(f"Assessment output drifted in {case['name']}")
        print(f"PASS {case['name']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus', type=Path, help='Directory with CASE-MATRIX.json and referenced inputs')
    parser.add_argument('--clock-library', required=True, type=Path)
    parser.add_argument('--clock-sha256', required=True)
    args = parser.parse_args()
    try:
        replay(args.corpus.resolve(strict=True), args.clock_library, args.clock_sha256)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f'Assessment replay failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
