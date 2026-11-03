import unittest

from ariadne_mark.verification import CheckStatus, IssuerTrust, SignatureStatus, VerificationResult
from tests.provenance.test_records import example_record


class VerificationTests(unittest.TestCase):
    def test_operational_failures_are_not_negative_detections(self):
        for reason in ("unsupported_format", "model_missing", "decode_failed", "timeout"):
            result = VerificationResult("example-watermark-v1", CheckStatus.NOT_CHECKED, reason=reason)
            self.assertEqual(result.to_dict()["status"], "not_checked")
            self.assertIsNone(result.record)
        absent = VerificationResult("example-watermark-v1", CheckStatus.NOT_FOUND)
        self.assertEqual(absent.to_dict()["status"], "not_found")

    def test_unsigned_recovered_claim_is_not_trusted(self):
        record = example_record()
        recovered = VerificationResult("example", CheckStatus.RECOVERED_CLAIM, SignatureStatus.ABSENT, record=record)
        self.assertEqual(recovered.to_dict()["issuer_trust"], "not_checked")
        with self.assertRaises(ValueError):
            VerificationResult("example", CheckStatus.RECOVERED_CLAIM, SignatureStatus.ABSENT, IssuerTrust.TRUSTED, record)
        with self.assertRaises(ValueError):
            VerificationResult("example", CheckStatus.VERIFIED_CLAIM, SignatureStatus.ABSENT, record=record)

    def test_signature_validity_does_not_imply_issuer_trust(self):
        for trust in IssuerTrust:
            result = VerificationResult("example-c2pa", CheckStatus.VERIFIED_CLAIM, SignatureStatus.VALID, trust, example_record())
            self.assertEqual(result.to_dict()["issuer_trust"], trust.value)
        result = VerificationResult("example-c2pa", CheckStatus.VERIFIED_CLAIM, SignatureStatus.VALID, record=example_record())
        self.assertEqual(result.issuer_trust, IssuerTrust.NOT_CHECKED)

    def test_tampered_claim_is_invalid(self):
        result = VerificationResult("example-c2pa", CheckStatus.INVALID, SignatureStatus.INVALID, reason="asset_binding_mismatch")
        self.assertEqual(result.to_dict()["status"], "invalid")
        with self.assertRaises(ValueError):
            VerificationResult("example-c2pa", CheckStatus.INVALID, SignatureStatus.INVALID, IssuerTrust.TRUSTED, reason="tampered")

    def test_contradictory_results_rejected(self):
        cases = [
            dict(status=CheckStatus.NOT_CHECKED),
            dict(status=CheckStatus.INVALID),
            dict(status=CheckStatus.NOT_FOUND, record=example_record()),
            dict(status=CheckStatus.NOT_FOUND, signature=SignatureStatus.ABSENT),
            dict(status=CheckStatus.NOT_FOUND, issuer_trust=IssuerTrust.TRUSTED),
            dict(status=CheckStatus.RECOVERED_CLAIM),
            dict(status=CheckStatus.VERIFIED_CLAIM, signature=SignatureStatus.VALID),
            dict(status=CheckStatus.INVALID, signature=SignatureStatus.VALID, reason="invalid"),
            dict(status="not_found"),
            dict(status=CheckStatus.NOT_FOUND, signature="not_checked"),
            dict(status=CheckStatus.NOT_FOUND, issuer_trust="not_checked"),
            dict(status=CheckStatus.RECOVERED_CLAIM, record={}),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                VerificationResult("example", **case)

    def test_no_implicit_compliance_or_human_origin_verdict(self):
        result = VerificationResult("example", CheckStatus.NOT_FOUND).to_dict()
        self.assertNotIn("compliant", result)
        self.assertNotIn("human_created", result)
        self.assertNotIn("ai_probability", result)


if __name__ == "__main__":
    unittest.main()
