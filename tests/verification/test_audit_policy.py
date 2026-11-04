import unittest
from pathlib import Path
from unittest.mock import patch
from ariadne_mark.verification.media import inspect_c2pa,summarize_watermarks
class AuditPolicyTests(unittest.TestCase):
    def test_operational_reader_failure_is_not_tampering(self):
        for error in [RuntimeError('native unavailable'),MemoryError(),OSError()]:
            with patch('ariadne_mark.verification.media.read_manifest',side_effect=error):
                self.assertEqual(inspect_c2pa(Path('fixture.png'))['status'],'not_checked')
    def test_untrusted_timestamp_never_overrides_expiry(self):
        raw={'validation_results':{'activeManifest':{'success':[{'code':x} for x in ['claimSignature.validated','assertion.dataHash.match','timeStamp.validated']], 'failure':[{'code':'signingCredential.expired'}], 'informational':[{'code':'timeStamp.untrusted'}]}}}
        with patch('ariadne_mark.verification.media.read_manifest',return_value=raw):report=inspect_c2pa(Path('fixture.png'))
        self.assertEqual(report['status'],'expired_credential');self.assertEqual(report['timestamp_trust'],'untrusted')
    def test_one_marked_frame_is_reported_as_partial_sample_evidence(self):
        token='014d000000000001';rows=[{'token':token}]+[{'token':None} for _ in range(4)]
        r=summarize_watermarks(rows,[],video=True)
        self.assertEqual(r['sample_coverage']['interpretation'],'partial_sample_evidence')
        self.assertEqual(r['sample_coverage']['matched_frames'],1)
        self.assertEqual(r['sample_coverage']['whole_video_coverage'],'not_established')
    def test_aggregate_recovery_does_not_invent_matched_frames(self):
        r=summarize_watermarks([{'token':None}]*5,[{'token':'014d000000000001'}],video=True)
        self.assertEqual(r['sample_coverage']['interpretation'],'aggregate_only_evidence')
        self.assertEqual(r['sample_coverage']['matched_frames'],0)
