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

class ResourceOwnershipTests(unittest.TestCase):
    def test_temporary_decoder_is_closed_on_failure(self):
        import tempfile
        from ariadne_mark.verification.media import verify_file
        from ariadne_mark.errors import MissingModel
        closed=[]
        class Temporary:
            algorithm='adobe.trustmark.Q.variax-bch5'
            def decode_frames(self,frames):raise MissingModel('fixture')
            def close(self):closed.append(True)
        class Legacy:
            algorithm='adobe.trustmark.Q.bch5'
            def decode(self,image):return None
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'fixture.mp4';file.touch()
            with patch('ariadne_mark.videoq.VideoWatermarker',Temporary),patch('ariadne_mark.video.sample_frames',return_value=[(object(),0.)]),patch('ariadne_mark.verification.media.inspect_c2pa',return_value={'status':'verified_claim','issuer_trust':'trusted','watermark_algorithm':Temporary.algorithm}):
                verify_file(file,marker=Legacy())
        self.assertEqual(closed,[True])
    def test_caller_owned_decoder_is_retained(self):
        import tempfile
        from ariadne_mark.verification.media import verify_file
        closed=[]
        class Supplied:
            algorithm='adobe.trustmark.Q.variax-bch5'
            def decode_frames(self,frames):return ([{'time':0,'token':None}],None)
            def close(self):closed.append(True)
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'fixture.mp4';file.touch()
            with patch('ariadne_mark.video.sample_frames',return_value=[(object(),0.)]),patch('ariadne_mark.verification.media.inspect_c2pa',return_value={'status':'verified_claim','issuer_trust':'trusted','watermark_algorithm':Supplied.algorithm}):
                verify_file(file,video_marker=Supplied())
        self.assertEqual(closed,[])
