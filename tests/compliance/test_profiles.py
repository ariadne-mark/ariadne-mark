"""Executable scenarios, not legal certification tests."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import date, datetime, timezone, timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest

from ariadne_mark.profiles import CATALOG, template, evaluate, load, export_settings
from ariadne_mark.provenance import ProvenanceRecord, GenerativeSystem, MediaKind, Action
from ariadne_mark.cli import main


class ProfileTests(unittest.TestCase):
    def config(self, jurisdictions=None):
        c = template()
        c.update(jurisdictions=jurisdictions or ['EU', 'US-CA'], role='provider',
                 publisher='Studio', system={'name': 'Generator', 'version': '1'})
        c['context'].update(eu_in_scope=True, eu_first_placed_on_market='2026-09-01',
                            deepfake=False, creative_work=False, ca_public_access=True,
                            ca_produces_system=True, licenses_system_to_third_parties=False)
        c['sdk']['audio_kind'] = 'none'
        return c

    def report(self, c, on='2026-11-03'):
        return evaluate(c, as_of=date.fromisoformat(on))

    def requirements(self, report):
        return {r['id']: r for r in report['requirements']}

    def record(self, publisher='Studio', media='image'):
        return ProvenanceRecord.create(publisher=publisher, system=GenerativeSystem('Generator', '1'),
            media_kind=MediaKind(media), action=Action.CREATED,
            created_at=datetime(2026, 11, 3, tzinfo=timezone.utc))

    def test_provider_transition_does_not_delay_deployer(self):
        c = self.config(['EU']); c['role'] = 'both'
        c['context'].update(eu_first_placed_on_market='2026-08-01', deepfake=True)
        r = self.report(c)
        self.assertEqual(r['applicability']['EU']['provider_marking']['state'], 'not_yet_applicable')
        self.assertEqual(r['applicability']['EU']['provider_marking']['effective_on'], '2026-12-02')
        self.assertEqual(r['applicability']['EU']['deployer_disclosure']['state'], 'applies_to_declared_scenario')
        self.assertEqual(self.requirements(r)['eu_disclosure']['state'], 'action_required')
        self.assertEqual(self.report(c, '2026-12-02')['applicability']['EU']['provider_marking']['state'], 'applies_to_declared_scenario')

    def test_eu_date_boundaries_and_unknown_date(self):
        c = self.config(['EU']); c['context']['eu_first_placed_on_market'] = '2026-08-02'
        self.assertEqual(self.report(c, '2026-08-01')['applicability']['EU']['provider_marking']['state'], 'not_yet_applicable')
        self.assertEqual(self.report(c, '2026-08-02')['applicability']['EU']['provider_marking']['effective_on'], '2026-08-02')
        c['context']['eu_first_placed_on_market'] = None
        self.assertEqual(self.report(c)['applicability']['EU']['provider_marking']['state'], 'review_required')

    def test_deployer_and_creative_content(self):
        c = self.config(['EU']); c['role'] = 'deployer'
        c['context'].update(deepfake=True, creative_work=True)
        r = self.report(c)
        self.assertNotIn('provider_marking', r['applicability']['EU'])
        self.assertIn('eu_creative_context', self.requirements(r))
        self.assertEqual(self.requirements(r)['eu_disclosure']['state'], 'action_required')
        c['deployment'].update(disclosure='in_app', accessibility_review=True)
        self.assertEqual(self.requirements(self.report(c))['eu_disclosure']['state'], 'declared_not_verified')
        self.assertFalse(self.report(c)['sdk_options']['visible'])

    def test_unknowns_and_exceptions_never_disable_marks(self):
        c = self.config(); c['role'] = 'unknown'
        c['context'].update(eu_in_scope=None, eu_exception='standard_editing', ca_exception='minor_modification')
        r = self.report(c)
        self.assertTrue(r['sdk_options']['watermark'])
        self.assertTrue(r['sdk_options']['c2pa'])
        self.assertIn('eu_role', [f['id'] for f in r['findings']])
        self.assertEqual(r['applicability']['US-CA']['provider_duties'], 'exception_requires_review')
        self.assertEqual(r['legal_determination'], 'not_performed')

    def test_declared_outside_scope_does_not_claim_compliance(self):
        c = self.config(); c['context'].update(eu_in_scope=False, ca_public_access=False)
        r = self.report(c)
        self.assertNotIn('ca_verifier_public', self.requirements(r))
        self.assertNotIn('eu_machine_mark', self.requirements(r))
        self.assertEqual(r['legal_determination'], 'not_performed')

    def test_ca_amendment_has_no_size_threshold_or_required_overlay(self):
        c = self.config(['US-CA']); r = self.report(c)
        self.assertIsNone(r['applicability']['US-CA']['monthly_user_threshold'])
        self.assertFalse(r['sdk_options']['visible'])
        self.assertEqual(self.requirements(r)['ca_no_mandatory_overlay']['state'], 'information')
        self.assertEqual(self.report(c, '2026-09-29')['applicability']['US-CA']['provider_duties'], 'historical_version_not_supported')
        self.assertEqual(self.report(c, '2026-09-30')['applicability']['US-CA']['provider_duties'], 'applies_to_declared_scenario')
        self.assertEqual(r['sources']['CA-22757']['kind'], 'consolidated_statute_official')
        self.assertNotIn('ca_primary_reconciliation', [f['id'] for f in r['findings']])

    def test_ca_upload_or_url_and_third_party_ui(self):
        c = self.config(['US-CA']); d = c['deployment']
        d.update(verifier_provider='third_party', verifier_url_submission=True, verifier_upload=False)
        req = self.requirements(self.report(c))
        self.assertEqual(req['ca_upload']['state'], 'declared_not_verified')
        self.assertEqual(req['ca_third_party_verifier']['state'], 'action_required')
        d['verifier_link_in_product'] = True
        self.assertEqual(self.requirements(self.report(c))['ca_third_party_verifier']['state'], 'declared_not_verified')

    def test_complete_declarations_remain_unverified(self):
        c = self.config()
        c['deployment'].update(verifier_url='https://verify.example.invalid', verifier_free=True,
            verifier_upload=True, verifier_api=True, verifier_provider='own',
            feedback_url='https://feedback.example.invalid', privacy_review=True,
            durability_evidence='report-1', interoperability_evidence='report-2')
        r = self.report(c)
        self.assertEqual(r['assessment_status'], 'review_required')
        self.assertEqual(r['declaration_verification'], 'not_performed')
        self.assertEqual(self.requirements(r)['ca_verifier_public']['state'], 'declared_not_verified')
        self.assertTrue(r['export_supported'])

    def test_bad_public_urls_are_not_accepted(self):
        c = self.config(['US-CA'])
        for url in ['http://example.com', 'https://localhost', 'https://127.0.0.1', 'https://192.168.1.1', 'https://user:pass@example.com', 'https://example.com:8080', 'https://e xample.com', 'https://localhost.', 'https://[::1]']:
            with self.subTest(url=url):
                c['deployment']['verifier_url'] = url
                self.assertEqual(self.requirements(self.report(c))['ca_verifier_public']['state'], 'action_required')
        c['deployment']['verifier_url'] = 'https://[2606:4700:4700::1111]'
        self.assertEqual(self.requirements(self.report(c))['ca_verifier_public']['state'], 'declared_not_verified')

    def test_stale_snapshot_and_future_schema_gap(self):
        c = self.config(['US-CA'])
        r = evaluate(c, as_of=date.fromisoformat(CATALOG['reviewed_on']) + timedelta(days=CATALOG['review_interval_days'] + 1))
        self.assertIn('source_refresh', [f['id'] for f in r['findings']])
        r = self.report(c, '2029-01-01')
        self.assertFalse(r['export_supported'])
        self.assertIn('ca_2029_metadata', [f['id'] for f in r['findings']])

    def test_media_and_audio_scope(self):
        c = self.config(); c['sdk']['audio_kind'] = 'synthetic'
        self.assertFalse(self.report(c)['export_supported'])
        c['sdk']['audio_kind'] = 'unknown'
        self.assertTrue(self.report(c)['export_supported'])
        self.assertIn('audio_scope', [f['id'] for f in self.report(c)['findings']])
        c['media_kinds'] = ['audio']
        self.assertFalse(self.report(c)['export_supported'])

    def test_record_binding_and_export_settings(self):
        c = self.config(); c['deployment']['disclosure'] = 'baked_in'
        r = export_settings(c, self.record())
        self.assertTrue(r['sdk_options']['visible'])
        with self.assertRaisesRegex(ValueError, 'does not match'):
            export_settings(c, self.record(publisher='Another Studio'))
        c['media_kinds'] = ['image']
        with self.assertRaisesRegex(ValueError, 'Media kind'):
            export_settings(c, self.record(media='video'))

    def test_strict_schema_and_json(self):
        for field, value in [('schema_version', True), ('role', 'admin'), ('jurisdictions', ['EU', 'EU'])]:
            c = self.config(); c[field] = value
            with self.assertRaises(ValueError): self.report(c)
        c = self.config(); c['context']['eu_in_scope'] = 1
        with self.assertRaises(ValueError): self.report(c)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'bad.json'
            for body in ['{"schema_version":1,"schema_version":1}', ' ' * 65537]:
                p.write_text(body)
                with self.assertRaises(ValueError): load(p)
        c = self.config(); c['system']['version'] = ''
        self.assertEqual(self.report(c)['configuration_status'], 'invalid')

    def test_configuration_fingerprint_is_stable_and_sensitive(self):
        c = self.config(); first = self.report(c)['configuration_sha256']
        self.assertEqual(first, self.report(dict(reversed(list(c.items()))))['configuration_sha256'])
        c['system']['version'] = '2'
        self.assertNotEqual(first, self.report(c)['configuration_sha256'])

    def test_economy_retains_durability_review_without_changing_requested_preset(self):
        c = self.config()
        for mode in ['economy_5s', 'economy_2s']:
            c['sdk']['video_profile'] = mode
            report = self.report(c)
            self.assertEqual(report['sdk_options']['video_profile'], mode)
            self.assertIn('economy_durability_review', [f['id'] for f in report['findings']])
            self.assertEqual(report['legal_determination'], 'not_performed')

    def test_cli_without_models_and_exit_status(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(['profile', 'init']), 0)
        self.assertEqual(json.loads(out.getvalue()), template())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'; path.write_text(json.dumps(self.config()))
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['profile', 'check', str(path), '--as-of', '2026-11-03']), 3)
            self.assertEqual(json.loads(out.getvalue())['configuration_status'], 'valid')
            path.write_text(json.dumps(template()))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['profile', 'check', str(path)]), 2)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(['profile', 'check', str(path), '--as-of', 'yesterday']), 2)

    def test_cli_rejects_conflicting_profile_before_model_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'config.json'; path.write_text(json.dumps(self.config()))
            with redirect_stderr(io.StringIO()) as err:
                code = main(['mark', 'missing.png', 'out.png', '--profile', str(path),
                    '--publisher', 'Wrong', '--identity', 'missing', '--created-at', '2026-11-03T00:00:00Z'])
            self.assertEqual(code, 2)
            self.assertIn('overrides conflict', err.getvalue())
