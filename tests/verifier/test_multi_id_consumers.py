"""Every consumer handles multiple_ids explicitly (no fall-through to success)."""
import contextlib
import http.client
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from ariadne_mark.errors import VerificationFailed
from ariadne_mark.public_verifier import public_report
from ariadne_mark.server import make_server
from tests.provenance.test_records import example_record

A = '014d123456789abc'
B = '014d000000000001'
Q = 'adobe.trustmark.Q.variax-bch5'
LEGACY = 'adobe.trustmark.Q.bch5'
PRIVATE = 'alice@example.org'


def multi_report(record=None, positions=40):
    record = record or example_record().to_dict()
    times = [i / 24 for i in range(positions)]
    return {
        'schema_version': 2, 'label': 'Multiple watermark IDs found; each applies only where it was observed',
        'c2pa': {'status': 'not_found'}, 'token_mismatch': False,
        'watermark': {
            'status': 'multiple_ids', 'reason': 'multiple_ids_observed',
            'samples': [{'time': 0.0, 'token': A, 'algorithm': Q, 'frame': {'stream': 0, 'pts': 0, 'time_base': '1/24'},
                         'private': PRIVATE}],
            'ids': [{'token': A, 'status': 'confirmed', 'confirmation_basis': 'two_or_more_unique_frames_one_scheme',
                     'bases': [{'algorithm': Q, 'basis': 'individual', 'unique_frames': positions, 'observations': positions,
                                'debug': PRIVATE}],
                     'first_time_s': 0.0, 'last_time_s': times[-1], 'positions_s': times, 'matches_signed_claim': None},
                    {'token': B, 'status': 'observed', 'confirmation_basis': None,
                     'bases': [{'algorithm': LEGACY, 'basis': 'individual', 'unique_frames': 1, 'observations': 1}],
                     'first_time_s': 5.0, 'last_time_s': 5.0, 'positions_s': [5.0], 'matches_signed_claim': None}],
            'evidence_scope': {'passes': [{'pass': 0, 'algorithm': Q, 'implementation': 'node-' + PRIVATE,
                                           'preprocessing': 'decoded_rgb_display_orientation', 'selection': 'sequential_from_start',
                                           'coverage': 'prefix_until_stop', 'unique_frames': positions,
                                           'time_range_s': [0.0, times[-1]], 'samples': [{'private': PRIVATE}]}],
                               'whole_file_examined': False, 'full_decode_schemes': [], 'unavailable_schemes': [],
                               'positions_scope': 'observed_positions_only', 'unexamined_content': 'not_established'}},
        'recovery': {'status': 'per_id', 'automatic_selection': 'none', 'per_id': [
            {'token': A, 'algorithms': [Q], 'status': 'found', 'binding': 'watermark_only_not_cryptographic',
             'record': {**record, 'publisher': PRIVATE}, 'content_binding': 'not_verified',
             'record_scope': 'registry_entry_for_id_not_authenticated_source_of_this_copy'},
            {'token': B, 'algorithms': [LEGACY], 'status': 'not_attempted', 'reason': 'id_not_confirmed'}]}}


class PublicReportTests(unittest.TestCase):
    def test_multi_id_public_report_is_bounded_and_redacted(self):
        report = multi_report()
        result = public_report(report)
        text = json.dumps(result)
        self.assertNotIn(PRIVATE, text)
        self.assertNotIn('samples', result['watermark'])
        self.assertNotIn('"frame"', text)
        ids = result['watermark']['ids']
        self.assertEqual([e['token'] for e in ids], [A, B])
        self.assertEqual(len(ids[0]['positions_s']), 8)
        self.assertEqual(ids[0]['positions_truncated'], 32)
        self.assertNotIn('implementation', result['watermark']['evidence_scope']['passes'][0])
        per_id = result['recovery']['per_id']
        self.assertEqual(per_id[1], {'status': 'not_attempted', 'token': B, 'algorithms': [LEGACY], 'reason': 'id_not_confirmed'})
        self.assertIn('recovery.per_id.0.record.publisher', result['public_output']['redacted_fields'])
        self.assertEqual(result['recovery']['automatic_selection'], 'none')
        self.assertIn(PRIVATE, json.dumps(report))  # local report untouched

    def test_id_list_is_capped(self):
        report = multi_report()
        report['watermark']['ids'] = report['watermark']['ids'][:1] * 20
        self.assertEqual(len(public_report(report)['watermark']['ids']), 16)
        self.assertEqual(public_report(report)['watermark']['ids_truncated'], 4)


class RecoverSelectorTests(unittest.TestCase):
    def sdk(self, report, bundle=None):
        from ariadne_mark.pipeline import SDK

        class Registry:
            def get_manifest(self, token):
                return bundle if bundle and token == A else None
        sdk = SDK(registry=Registry())
        return sdk, patch.object(SDK, 'verify', return_value=report)

    def test_ambiguous_multi_id_recovery_is_refused_without_selector(self):
        sdk, verify = self.sdk(multi_report())
        with verify, tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(VerificationFailed, 'Multiple watermark IDs'):
                sdk.recover_manifest(Path('in.mp4'), Path(folder) / 'out.c2pa')
            with self.assertRaisesRegex(VerificationFailed, 'not a confirmed'):
                sdk.recover_manifest(Path('in.mp4'), Path(folder) / 'b.c2pa', token=B)
            self.assertFalse((Path(folder) / 'out.c2pa').exists())

    def test_selector_after_detection_saves_only_that_ids_manifest(self):
        report = multi_report()
        manifest = {'soft_binding': 'matched', 'signature': 'valid', 'sha256': 'abc'}
        report['recovery']['per_id'][0]['manifest'] = manifest
        sdk, verify = self.sdk(report, {'sha256': 'abc', 'bytes': b'manifest-A'})
        with verify as verified, tempfile.TemporaryDirectory() as folder:
            result = sdk.recover_manifest(Path('in.mp4'), Path(folder) / 'a.c2pa', token=A)
            self.assertEqual((Path(folder) / 'a.c2pa').read_bytes(), b'manifest-A')
            self.assertEqual(result['manifest'], manifest)
            verified.assert_called_once_with(Path('in.mp4'))  # selector is not given to detection

    def test_single_id_selector_must_match_recovered_id(self):
        report = {'watermark': {'status': 'recovered_claim', 'token': A}, 'recovery': {'status': 'found'}}
        sdk, verify = self.sdk(report)
        with verify, tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(VerificationFailed, 'not recovered'):
                sdk.recover_manifest(Path('in.mp4'), Path(folder) / 'x.c2pa', token=B)


class CliExitTests(unittest.TestCase):
    def exit_code(self, watermark, c2pa=None, mismatch=False):
        from ariadne_mark import cli
        from ariadne_mark.pipeline import SDK
        report = {'schema_version': 2, 'label': 'x', 'c2pa': c2pa or {'status': 'not_found'},
                  'watermark': watermark, 'recovery': {'status': 'not_attempted'}, 'token_mismatch': mismatch}
        with patch.object(SDK, 'check_runtime'), patch.object(SDK, 'verify', return_value=report), \
             contextlib.redirect_stdout(io.StringIO()):
            return cli.main(['verify', 'fixture.mp4'])

    def test_only_completed_positive_or_negative_exits_zero(self):
        self.assertEqual(self.exit_code({'status': 'recovered_claim', 'token': A}), 0)
        self.assertEqual(self.exit_code({'status': 'not_found'}), 0)
        for status in ['multiple_ids', 'single_observation', 'not_checked', 'invalid', 'future_status']:
            with self.subTest(status=status):
                self.assertEqual(self.exit_code({'status': status}), 2)
        self.assertEqual(self.exit_code({'status': 'recovered_claim', 'token': A}, mismatch=True), 2)


class ContentQueryTests(unittest.TestCase):
    def query(self, report, bundles, query=''):
        asked = []

        class Registry:
            def get_manifest(self, token, public_only=False):
                asked.append((token, public_only))
                bundle = bundles.get(token)
                return None if bundle and public_only and bundle.get('private') else bundle

        class SDK:
            registry = Registry()
            def verify(self, path): return report
        server = make_server(SDK(), port=0, public_manifests=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection(*server.server_address, timeout=5)
            connection.request('POST', '/matches/byContent' + query, b'asset', {'Content-Type': 'video/mp4'})
            response = connection.getresponse()
            status, body = response.status, json.loads(response.read())
            connection.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()
        self.assertEqual(status, 200)
        self.assertTrue(all(public_only for _, public_only in asked))
        return body, [token for token, _ in asked]

    def report(self, *, both_confirmed=True):
        report = multi_report()
        report['watermark']['samples'] = [{'token': A, 'algorithm': Q}, {'token': B, 'algorithm': LEGACY}]
        if both_confirmed:
            report['watermark']['ids'][1]['status'] = 'confirmed'
        return report

    def test_by_content_returns_one_candidate_per_confirmed_id(self):
        bundles = {A: {'id': 'urn:a', 'algorithm': 'org.ariadne-mark.trustmark-q.video-bch5.v1'},
                   B: {'id': 'urn:b', 'algorithm': 'org.ariadne-mark.trustmark-q.bch5.v1'}}
        body, asked = self.query(self.report(both_confirmed=False), bundles)
        self.assertEqual(body, {'matches': [{'manifestId': 'urn:a'}]})
        self.assertEqual(asked, [A])  # observed-only B is not looked up

    def test_result_limit_follows_missing_or_private_manifest_filter(self):
        valid = {'id': 'urn:b', 'algorithm': 'org.ariadne-mark.trustmark-q.bch5.v1'}
        for first in (None, {'id': 'urn:private', 'algorithm': 'org.ariadne-mark.trustmark-q.video-bch5.v1', 'private': True}):
            with self.subTest(first=first):
                body, asked = self.query(self.report(), {A: first, B: valid}, '?maxResults=1')
                self.assertEqual(body, {'matches': [{'manifestId': 'urn:b'}]})
                self.assertEqual(asked, [A, B])

    def test_result_limit_follows_requested_algorithm_filter(self):
        legacy_binding = 'org.ariadne-mark.trustmark-q.bch5.v1'
        bundles = {A: {'id': 'urn:a', 'algorithm': 'org.ariadne-mark.trustmark-q.video-bch5.v1'},
                   B: {'id': 'urn:b', 'algorithm': legacy_binding}}
        body, asked = self.query(self.report(), bundles, '?maxResults=1&alg=' + legacy_binding)
        self.assertEqual(body, {'matches': [{'manifestId': 'urn:b'}]})
        self.assertEqual(asked, [A, B])

    def test_result_limit_follows_observed_scheme_filter(self):
        legacy_binding = 'org.ariadne-mark.trustmark-q.bch5.v1'
        # A was read by Q, not the legacy scheme named by its stored bundle.
        bundles = {A: {'id': 'urn:a', 'algorithm': legacy_binding}, B: {'id': 'urn:b', 'algorithm': legacy_binding}}
        body, asked = self.query(self.report(), bundles, '?maxResults=1')
        self.assertEqual(body, {'matches': [{'manifestId': 'urn:b'}]})
        self.assertEqual(asked, [A, B])

    def test_result_limit_caps_actual_matches_and_stops_lookup(self):
        bundles = {A: {'id': 'urn:a', 'algorithm': 'org.ariadne-mark.trustmark-q.video-bch5.v1'},
                   B: {'id': 'urn:b', 'algorithm': 'org.ariadne-mark.trustmark-q.bch5.v1'}}
        body, asked = self.query(self.report(), bundles, '?maxResults=1')
        self.assertEqual(body, {'matches': [{'manifestId': 'urn:a'}]})
        self.assertEqual(asked, [A])

    def test_candidate_lookup_count_remains_bounded(self):
        report = self.report()
        report['watermark']['ids'] = [{'token': f'014d{i:012x}', 'status': 'confirmed'} for i in range(40)]
        body, asked = self.query(report, {}, '?maxResults=100')
        self.assertEqual(body, {'matches': []})
        self.assertEqual(len(asked), 16)
