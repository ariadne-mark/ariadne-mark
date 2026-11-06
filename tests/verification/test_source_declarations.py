"""External standard declarations must never bypass validation or trust."""
from pathlib import Path
import unittest
from unittest.mock import patch

from ariadne_mark.c2pa_types import DigitalSourceType, declared_source_types
from ariadne_mark.verification.media import inspect_c2pa


class SourceDeclarationTests(unittest.TestCase):
    def manifest(self, *types, label="c2pa.actions"):
        return {"assertions": [{"label": label, "data": {"actions": [
            {"action": "c2pa.created", "digitalSourceType": t} for t in types]}}]}

    def test_external_standard_claim_without_ariadne_payload_is_readable(self):
        for label in ("c2pa.actions", "c2pa.actions.v2"):
            with self.subTest(label=label):
                self.assertEqual(declared_source_types(self.manifest(
                    DigitalSourceType.TRAINED_ALGORITHMIC_MEDIA.value, label=label)),
                    [DigitalSourceType.TRAINED_ALGORITHMIC_MEDIA.value])

    def test_edit_history_is_preserved_without_inferring_final_origin(self):
        capture = DigitalSourceType.DIGITAL_CAPTURE.value
        edit = DigitalSourceType.COMPOSITE_WITH_TRAINED_ALGORITHMIC_MEDIA.value
        result = declared_source_types(self.manifest(capture, edit, capture))
        self.assertEqual(result, [capture, edit])

    def test_ingredients_cannot_declare_origin_of_active_asset(self):
        manifest = {"ingredients": [self.manifest(DigitalSourceType.TRAINED_ALGORITHMIC_MEDIA.value)]}
        self.assertEqual(declared_source_types(manifest), [])

    def test_unknown_and_malformed_declarations_do_not_become_claims(self):
        manifest = self.manifest("https://unknown.invalid/ai", {"untrusted": True}, None)
        manifest["assertions"].extend([None, {"label": "c2pa.actions", "data": None},
            {"label": "c2pa.actions", "data": {"actions": [None, "bad"]}}])
        self.assertEqual(declared_source_types(manifest), [])
        self.assertEqual(declared_source_types({"assertions": None}), [])

    def test_ai_declaration_does_not_upgrade_invalid_or_untrusted_signatures(self):
        source = DigitalSourceType.TRAINED_ALGORITHMIC_MEDIA.value
        for failures, status, trust in [
            (["claimSignature.mismatch"], "invalid", "not_checked"),
            (["signingCredential.untrusted"], "verified_claim", "untrusted"),
        ]:
            raw = {"active_manifest": "external", "manifests": {"external": self.manifest(source)},
                "validation_results": {"activeManifest": {
                    "success": [{"code": "claimSignature.validated"}, {"code": "assertion.dataHash.match"}],
                    "failure": [{"code": c} for c in failures]}}}
            with patch("ariadne_mark.verification.media.read_manifest", return_value=raw):
                result = inspect_c2pa(Path("external.png"))
            self.assertEqual(result["declared_source_types"], [source])
            self.assertEqual(result["status"], status)
            self.assertEqual(result["issuer_trust"], trust)
            self.assertNotIn("token", result)

    def test_signing_vocabulary_retains_wire_values(self):
        prefix = "http://cv.iptc.org/newscodes/digitalsourcetype/"
        self.assertEqual(DigitalSourceType.TRAINED_ALGORITHMIC_MEDIA.value,
                         prefix + "trainedAlgorithmicMedia")
        self.assertEqual(DigitalSourceType.COMPOSITE_WITH_TRAINED_ALGORITHMIC_MEDIA.value,
                         prefix + "compositeWithTrainedAlgorithmicMedia")
