from pathlib import Path
import unittest
from unittest.mock import patch

from ariadne_mark.verification.media import inspect_c2pa


def native_result(success=(), failure=()):
    return {"validation_results": {"activeManifest": {
        "success": [{"code": c} for c in success], "failure": [{"code": c} for c in failure]}}}


class C2paPolicyTests(unittest.TestCase):
    def check(self, raw):
        with patch("ariadne_mark.verification.media.read_manifest", return_value=raw):
            return inspect_c2pa(Path("fixture.png"))

    def test_signature_without_content_binding_is_not_verified(self):
        self.assertEqual(self.check(native_result(["claimSignature.validated"]))["status"], "invalid")

    def test_untrusted_valid_signature_is_distinct_from_tampering(self):
        good = ["claimSignature.validated", "assertion.dataHash.match"]
        report = self.check(native_result(good, ["signingCredential.untrusted"]))
        self.assertEqual(report["signature"], "valid")
        self.assertEqual(report["issuer_trust"], "untrusted")
        report = self.check(native_result(good, ["assertion.hashedURI.mismatch"]))
        self.assertEqual(report["status"], "invalid")

    def test_unknown_failure_is_not_silently_ignored(self):
        report = self.check(native_result(["claimSignature.validated", "assertion.bmffHash.match"], ["new.failure.code"]))
        self.assertEqual(report["status"], "invalid")

    def test_invalid_manifest_preserves_independent_evidence(self):
        from ariadne_mark.public_verifier import public_report
        good = ["claimSignature.validated", "assertion.bmffHash.match", "signingCredential.trusted"]
        report = self.check(native_result(good, ["assertion.action.softBindingMissing"]))
        public = public_report({"c2pa": report})["c2pa"]
        self.assertEqual(public["status"], "invalid")
        self.assertEqual(public["signature"], "valid")
        self.assertEqual(public["asset_binding"], "valid")
        self.assertEqual(public["issuer_trust"], "trusted")

    def test_binding_failure_is_separate_from_a_signature_failure(self):
        report = self.check(native_result(["claimSignature.validated"], ["assertion.dataHash.mismatch"]))
        self.assertEqual((report["status"], report["signature"], report["asset_binding"]),
                         ("invalid", "valid", "invalid"))
        report = self.check(native_result(["assertion.dataHash.match"], ["claimSignature.mismatch"]))
        self.assertEqual((report["status"], report["signature"], report["asset_binding"]),
                         ("invalid", "invalid", "valid"))

    def test_external_credential_is_not_labelled_provenance_unavailable(self):
        from ariadne_mark.verification.media import _verification_result
        claim = self.check(native_result(['claimSignature.validated', 'assertion.dataHash.match']))
        report = _verification_result(Path('fixture.png'), claim, {'status': 'not_checked'}, registry=None, video=False)
        self.assertEqual(report['label'], 'C2PA signature valid; no supported AI-origin claim; watermark check incomplete')

    def test_incomplete_negative_checks_are_not_headlined_as_absence(self):
        from ariadne_mark.verification.media import _verification_result
        for c2pa, watermark in [('not_found', 'not_checked'), ('not_checked', 'not_found'),
                                ('not_checked', 'not_checked')]:
            report = _verification_result(Path('fixture.mp4'), {'status': c2pa},
                {'status': watermark}, registry=None, video=True)
            self.assertEqual(report['label'], 'Check incomplete')
        report = _verification_result(Path('fixture.mp4'), {'status': 'not_found'},
            {'status': 'not_found'}, registry=None, video=True)
        self.assertEqual(report['label'], 'Provenance unavailable')
        for c2pa, watermark in [('invalid', 'not_checked'), ('not_checked', 'invalid')]:
            report = _verification_result(Path('fixture.mp4'), {'status': c2pa},
                {'status': watermark}, registry=None, video=True)
            self.assertEqual(report['label'], 'Invalid or conflicting provenance')


if __name__ == "__main__":
    unittest.main()
