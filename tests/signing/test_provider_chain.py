"""Real offline certificate paths with C2PA-specific (not TLS) purposes."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec('cryptography'), 'requires reports extra')
class ProviderChainTests(unittest.TestCase):
    def setUp(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
        self.x509, self.hashes, self.serialization = x509, hashes, serialization
        self.ec, self.NameOID, self.EKU = ec, NameOID, ExtendedKeyUsageOID
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime.now(timezone.utc)
        self.ca_key = ec.generate_private_key(ec.SECP256R1())
        self.ca = self.issue('Configured Root', self.ca_key, ca=True, path_length=1)
        self.roots = self.root / 'roots.pem'; self.roots.write_bytes(self.pem(self.ca))

    def issue(self, name, key, *, issuer=None, issuer_key=None, ca=False,
              path_length=None, eku='default', expired=False):
        x = self.x509
        subject = x.Name([x.NameAttribute(self.NameOID.COMMON_NAME, name)])
        issuer_name = issuer.subject if issuer else subject
        authority = issuer_key or key
        builder = (x.CertificateBuilder().subject_name(subject).issuer_name(issuer_name)
            .public_key(key.public_key()).serial_number(x.random_serial_number())
            .not_valid_before(self.now-timedelta(days=2))
            .not_valid_after(self.now+timedelta(days=-1 if expired else 10))
            .add_extension(x.BasicConstraints(ca=ca, path_length=path_length if ca else None), True)
            .add_extension(x.KeyUsage(not ca, False, False, False, False, ca, ca, False, False), True)
            .add_extension(x.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
            .add_extension(x.AuthorityKeyIdentifier.from_issuer_public_key(authority.public_key()), False))
        if eku == 'default': eku = None if ca else [self.EKU.EMAIL_PROTECTION]
        if eku is not None: builder = builder.add_extension(x.ExtendedKeyUsage(eku), False)
        return builder.sign(authority, self.hashes.SHA256())

    def pem(self, cert):
        return cert.public_bytes(self.serialization.Encoding.PEM)

    def leaf(self, **kw):
        key = self.ec.generate_private_key(self.ec.SECP256R1())
        return self.issue('Content Signer', key, issuer=self.ca, issuer_key=self.ca_key, **kw), key

    def verify(self, certs):
        from ariadne_mark.signing import validate_provider_chain
        path = self.root / 'chain.pem'; path.write_bytes(b''.join(self.pem(c) for c in certs))
        validate_provider_chain(path, self.roots)

    def test_configured_root_accepts_document_claim_and_email_signers_without_tls_san(self):
        for oid in [self.EKU.EMAIL_PROTECTION, self.x509.ObjectIdentifier('1.3.6.1.5.5.7.3.36'),
                    self.x509.ObjectIdentifier('1.3.6.1.4.1.62558.2.1')]:
            with self.subTest(eku=oid):
                leaf, _ = self.leaf(eku=[oid]); self.verify([leaf])

    def test_unrelated_root_and_same_name_wrong_key_are_rejected(self):
        wrong_key = self.ec.generate_private_key(self.ec.SECP256R1())
        for name in ['Other Root', 'Configured Root']:
            wrong = self.issue(name, wrong_key, ca=True, path_length=1)
            self.roots.write_bytes(self.pem(wrong))
            leaf, _ = self.leaf()
            with self.subTest(root=name), self.assertRaisesRegex(ValueError, 'chain/EKU'):
                self.verify([leaf, self.ca])

    def test_missing_tls_timestamp_and_mixed_purposes_are_rejected(self):
        cases = [None, [self.EKU.SERVER_AUTH], [self.EKU.TIME_STAMPING],
                 [self.EKU.EMAIL_PROTECTION, self.EKU.TIME_STAMPING],
                 [self.EKU.EMAIL_PROTECTION, self.EKU.OCSP_SIGNING],
                 [self.EKU.EMAIL_PROTECTION, self.EKU.ANY_EXTENDED_KEY_USAGE]]
        for eku in cases:
            leaf, _ = self.leaf(eku=eku)
            with self.subTest(eku=eku), self.assertRaisesRegex(ValueError, 'chain/EKU'):
                self.verify([leaf])

    def test_expired_leaf_and_ca_leaf_are_rejected(self):
        for kw in [dict(expired=True), dict(ca=True)]:
            leaf, _ = self.leaf(**kw)
            with self.subTest(kw=kw), self.assertRaisesRegex(ValueError, 'chain/EKU'):
                self.verify([leaf])

    def test_intermediate_path_is_required_and_constraints_are_enforced(self):
        key = self.ec.generate_private_key(self.ec.SECP256R1())
        intermediate = self.issue('Intermediate', key, issuer=self.ca, issuer_key=self.ca_key, ca=True, path_length=0)
        leaf_key = self.ec.generate_private_key(self.ec.SECP256R1())
        leaf = self.issue('Signer', leaf_key, issuer=intermediate, issuer_key=key)
        self.verify([leaf, intermediate])
        with self.assertRaisesRegex(ValueError, 'chain/EKU'): self.verify([leaf])
        restricted = self.issue('Intermediate', key, issuer=self.ca, issuer_key=self.ca_key,
                                ca=True, path_length=0, eku=[self.EKU.SERVER_AUTH])
        with self.assertRaisesRegex(ValueError, 'chain/EKU'): self.verify([leaf, restricted])
        nonca = self.issue('Intermediate', key, issuer=self.ca, issuer_key=self.ca_key)
        with self.assertRaisesRegex(ValueError, 'chain/EKU'): self.verify([leaf, nonca])

    def test_kit_check_rejects_unrelated_chain_and_accepts_configured_chain(self):
        import json
        from ariadne_mark import kit
        bundle = self.root / 'bundle'
        kit.initialize(bundle, publisher='Studio', system='Generator', system_version='1', development=True)
        leaf, key = self.leaf()
        (bundle/'private/provider/certificate.pem').write_bytes(self.pem(leaf)+self.pem(self.ca))
        (bundle/'private/provider/private.key').write_bytes(key.private_bytes(self.serialization.Encoding.PEM,
            self.serialization.PrivateFormat.PKCS8, self.serialization.NoEncryption()))
        (bundle/'private/provider/identity.json').write_text(json.dumps({'development':False}))
        (bundle/'config/issuer-roots.pem').write_bytes(self.pem(self.ca))
        (bundle/'config/tsa-roots.pem').write_bytes(self.pem(self.ca))
        config = json.loads((bundle/'config/kit.json').read_text())
        config.update(mode='production', verifier_url='https://verify.integration-company.org',
                      timestamp_url='https://tsa.integration-company.org')
        (bundle/'config/kit.json').write_text(json.dumps(config))
        product = json.loads((bundle/'config/product.json').read_text())
        product['deployment']['verifier_url'] = config['verifier_url']
        (bundle/'config/product.json').write_text(json.dumps(product))
        result = kit.check(bundle)
        self.assertEqual(result['status'], 'local_configuration_checked', result)
        self.assertEqual(result['issuer_chain'], 'checked_against_configured_roots')
        wrong_key = self.ec.generate_private_key(self.ec.SECP256R1())
        wrong = self.issue('Other Root', wrong_key, ca=True)
        (bundle/'config/issuer-roots.pem').write_bytes(self.pem(wrong))
        result = kit.check(bundle)
        self.assertEqual(result['status'], 'configuration_required')
        self.assertTrue(any('chain/EKU' in e for e in result['errors']))
