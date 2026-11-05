import http.client
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ariadne_mark.public_verifier import public_report, load_public_sources, FeedbackStore
from ariadne_mark.server import make_server
from tests.provenance.test_records import example_record

TOKEN = '014d123456789abc'


class PublicOutputTests(unittest.TestCase):
    def report(self, record):
        return {'schema_version': 1, 'label': 'Watermark ID recovered; source unverified',
                'c2pa': {'status': 'verified_claim', 'issuer_trust': 'trusted', 'record': record,
                         'raw_manifest': {'email': 'alice@example.org'}},
                'watermark': {'status': 'recovered_claim', 'token': TOKEN,
                              'samples': [{'token': TOKEN, 'private': 'alice@example.org'}]},
                'recovery': {'status': 'found', 'record': record},
                'debug': 'alice@example.org'}

    def test_unreviewed_free_text_and_unknown_metadata_never_escape_public_response(self):
        record = example_record().to_dict()
        record['publisher'] = 'alice@example.org'
        report = self.report(record)
        response = public_report(report)
        self.assertNotIn('alice@example.org', json.dumps(response))
        self.assertNotIn('asset_id', response['c2pa']['record'])
        self.assertEqual(response['watermark']['token'], TOKEN)
        self.assertTrue(response['public_output']['redacted_fields'])
        self.assertIn('alice@example.org', json.dumps(report))  # local report was not mutated

    def test_names_alone_do_not_unlock_untrusted_uploaded_metadata(self):
        record = example_record().to_dict()
        sources = [(record['publisher'], record['system']['name'], record['system']['version'])]
        report = self.report(record)
        approved = public_report(report, sources)
        self.assertEqual(approved['c2pa']['record'], record)
        report['c2pa']['issuer_trust'] = 'untrusted'
        untrusted = public_report(report, sources)
        self.assertNotIn('publisher', untrusted['c2pa']['record'])
        self.assertNotIn('created_at', untrusted['c2pa']['record'])
        self.assertEqual(untrusted['recovery']['record'], record)  # operator-owned registry is separate evidence

    def test_extra_record_fields_are_not_copied_even_for_reviewed_names(self):
        record = example_record().to_dict()
        sources = [(record['publisher'], record['system']['name'], record['system']['version'])]
        record['email'] = 'alice@example.org'
        self.assertNotIn('alice@example.org', json.dumps(public_report(self.report(record), sources)))

    def test_unreviewed_optional_assertion_strings_are_not_reflected(self):
        report = self.report(example_record().to_dict())
        report['c2pa'].update(watermark_profile='alice@example.org', audio='alice@example.org',
                              visible_disclosure={'email': 'alice@example.org'}, development_identity='alice@example.org')
        self.assertNotIn('alice@example.org', json.dumps(public_report(report)))

    def test_source_config_is_strict_and_size_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'public.json'
            for value in [{'schema_version': True, 'sources': []}, {'schema_version': 1, 'sources': [{'publisher': 'x', 'system': {'name': 'y', 'version': '1'}, 'email': 'private'}]}]:
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError): load_public_sources(path)
            path.write_text(' ' * 65537)
            with self.assertRaises(ValueError): load_public_sources(path)


class FeedbackTests(unittest.TestCase):
    def test_only_aggregate_enum_counts_persist_under_concurrency(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FeedbackStore(Path(directory) / 'feedback.sqlite')
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _: store.add({'rating': 'incorrect_result', 'media': 'video'}), range(20)))
            self.assertEqual(store.summary()['counts'], [{'rating': 'incorrect_result', 'media': 'video', 'count': 20}])
            for value in [{'rating': 'incorrect_result', 'media': 'video', 'comment': 'alice@example.org'},
                          {'rating': 'alice@example.org', 'media': 'image'},
                          {'rating': 'correct_result', 'media': ['video']}]:
                with self.assertRaises(ValueError): store.add(value)
            self.assertNotIn(b'alice@example.org', store.path.read_bytes())
            with store.connect() as db:
                self.assertEqual([r[1] for r in db.execute('PRAGMA table_info(feedback)')], ['rating', 'media', 'count'])


class PublicEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name)
        self.record = example_record().to_dict()
        self.sources = path / 'sources.json'
        self.sources.write_text(json.dumps({'schema_version': 1, 'sources': [{'publisher': self.record['publisher'], 'system': self.record['system']}]}))
        outer = self
        class Registry:
            def get(self, token):
                return {'record': outer.record} if token == TOKEN else None
        class SDK:
            registry = Registry()
            def verify(self, path):
                return PublicOutputTests().report(outer.record)
        self.db = path / 'feedback.sqlite'
        self.server = make_server(SDK(), port=0, public_sources=self.sources, feedback_db=self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=10)
        try:
            connection.request(method, path, body=body, headers={'Content-Type': 'application/json'} if path == '/feedback' else {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally: connection.close()

    def test_upload_and_registry_return_public_system_fields_only(self):
        status, _, raw = self.request('POST', '/verify?format=png', b'fixture')
        self.assertEqual(status, 200)
        self.assertNotIn(b'alice@example.org', raw)
        self.assertEqual(json.loads(raw)['c2pa']['record'], self.record)
        status, _, raw = self.request('GET', '/records/' + TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['record'], self.record)
        self.assertEqual(self.request('GET', '/records/014d000000000001')[0], 404)
        self.assertEqual(self.request('GET', '/records/../../etc/passwd')[0], 400)

    def test_feedback_is_anonymous_bounded_and_operational(self):
        self.assertEqual(self.request('POST', '/feedback', json.dumps({'rating': 'unable_to_check', 'media': 'video'}))[0], 202)
        self.assertEqual(self.request('POST', '/feedback', json.dumps({'rating': 'unable_to_check', 'media': 'video', 'email': 'alice@example.org'}))[0], 400)
        self.assertEqual(self.request('POST', '/feedback', ' ' * 2049)[0], 413)
        summary = FeedbackStore.read_summary(self.db)
        self.assertEqual(summary['counts'], [{'rating': 'unable_to_check', 'media': 'video', 'count': 1}])

    def test_packaged_ui_api_spec_and_privacy_have_no_third_party_scripts(self):
        for url in ['/', '/app.js', '/style.css', '/privacy', '/openapi.json', '/feedback', '/feedback.js']:
            status, headers, raw = self.request('GET', url)
            self.assertEqual(status, 200, url)
            self.assertIn("script-src 'self'", headers['Content-Security-Policy'])
            self.assertEqual(headers['Cache-Control'], 'no-store')
            if url == '/':
                self.assertIn(b'aria-live', raw)
                self.assertNotIn(b'<script>', raw)
            if url == '/openapi.json':
                self.assertIn('/feedback', json.loads(raw)['paths'])
        self.assertEqual(self.request('GET', '/../pyproject.toml')[0], 404)
