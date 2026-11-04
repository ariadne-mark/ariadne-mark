"""Installed new profiles: real audio/PTS, signed records, recovery and isolation."""
import os,unittest,tempfile,json,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone
from . import test_media as fixtures
@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS')=='1','requires provisioned real media runtime')
class VideoProfileTests(unittest.TestCase):
 ffmpeg=fixtures.MediaTests.ffmpeg
 video=fixtures.MediaTests.video
 record=fixtures.MediaTests.record
 def setUp(self):
  from ariadne_mark.signing import create_development_identity,SigningIdentity
  from ariadne_mark.watermark import Watermarker
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);create_development_identity(self.path/'id');self.identity=SigningIdentity.from_directory(self.path/'id',allow_dev=True);self.marker=Watermarker()
 def tearDown(self):self.tmp.cleanup()
 def test_fast_resilient_audio_vfr_rotation_and_source_recovery(self):
  import av
  from ariadne_mark.pipeline import SDK
  from ariadne_mark.registry import Registry
  from ariadne_mark.video import probe
  for profile in ['fast','resilient']:
   sdk=SDK(self.marker,self.identity,Registry(self.path/(profile+'.sqlite')),video_profile=profile)
   try:
    for scenario in ['cfr','vfr','vertical','rotation']:
     with self.subTest(profile=profile,scenario=scenario):
      source=self.video(audio=True,vfr=scenario=='vfr',vertical=scenario=='vertical')
      if scenario=='rotation':
       rotated=self.path/'rotated.mp4';self.ffmpeg('-display_rotation','90','-i',source,'-c','copy',rotated);source=rotated
      out=self.path/f'{profile}-{scenario}.mp4';receipt=sdk.mark(source,out,self.record('video'),audio_kind='original')
      self.assertEqual(receipt['verification']['c2pa']['watermark_algorithm'],'adobe.trustmark.Q.variax-bch5')
      self.assertEqual(receipt['video']['profile'],profile)
      self.assertEqual(sdk.verify(out)['watermark']['token'],receipt['token'])
      def frames(p):
       with av.open(str(p)) as c:return [(float(f.pts*f.time_base),float(f.duration*f.time_base)) for f in c.decode(video=0)]
      a,b=frames(source),frames(out);self.assertEqual(len(a),len(b));self.assertEqual(receipt['video']['watermark_stats']['frames'],len(a))
      for x,y in zip(a,b):self.assertAlmostEqual(x[0],y[0],places=3)
      def audio(p):
       with av.open(str(p)) as c:return [(p.pts,p.dts,bytes(p)) for p in c.demux(audio=0) if p.size]
      self.assertEqual(audio(source),audio(out))
      if scenario=='rotation':self.assertEqual(probe(out)['rotation'],0);self.assertEqual((probe(out)['width'],probe(out)['height']),(320,512))
    # Remux/re-encode destroys credentials; blind watermark recovery must still
    # find the asset via local registry without borrowing the signed token.
    src=self.path/f'{profile}-cfr.mp4';dst=self.path/f'{profile}-stripped.mp4'
    self.ffmpeg('-i',src,'-map_metadata','-1','-c:v','libx264','-crf','28','-an',dst)
    v=sdk.verify(dst);self.assertEqual(v['c2pa']['status'],'not_found');self.assertEqual(v['recovery']['status'],'found')
   finally:sdk.video_marker.close()
 def test_no_cross_export_cache_and_worker_failure_publishes_nothing(self):
  from ariadne_mark.pipeline import SDK
  from ariadne_mark.errors import AriadneError
  sdk=SDK(self.marker,self.identity)
  try:
   source=self.video(audio=False);a=sdk.mark(source,self.path/'a.mp4',self.record('video'));b=sdk.mark(source,self.path/'b.mp4',self.record('video'))
   self.assertNotEqual(a['token'],b['token']);self.assertEqual(sdk.verify(self.path/'a.mp4')['watermark']['token'],a['token'])
   original=sdk.video_marker.encode_frames
   def crash(*args):
    sdk.video_marker._process.kill();raise AriadneError('injected worker exit')
   sdk.video_marker.encode_frames=crash
   with self.assertRaises(AriadneError):sdk.mark(source,self.path/'failed.mp4',self.record('video'))
   self.assertFalse((self.path/'failed.mp4').exists());self.assertFalse((self.path/'failed.mp4.receipt.json').exists())
   sdk.video_marker.encode_frames=original
   c=sdk.mark(source,self.path/'c.mp4',self.record('video'));self.assertEqual(sdk.verify(self.path/'c.mp4')['watermark']['token'],c['token'])
  finally:sdk.video_marker.close()
 def test_shared_worker_concurrent_exports_keep_ids_and_receipts_isolated(self):
  from concurrent.futures import ThreadPoolExecutor
  from ariadne_mark.pipeline import SDK
  from ariadne_mark.registry import Registry
  sdk=SDK(self.marker,self.identity,Registry(self.path/'threads.sqlite'))
  try:
   source=self.video(audio=False)
   def export(i):return sdk.mark(source,self.path/f'thread-{i}.mp4',self.record('video'))
   with ThreadPoolExecutor(max_workers=2) as pool:receipts=list(pool.map(export,[0,1]))
   self.assertNotEqual(receipts[0]['token'],receipts[1]['token'])
   for i,r in enumerate(receipts):
    self.assertEqual(sdk.verify(self.path/f'thread-{i}.mp4')['watermark']['token'],r['token'])
    self.assertEqual(r['video']['watermark_stats']['frames'],24)
  finally:sdk.video_marker.close()
 def test_worker_exit_after_last_frame_still_publishes_nothing(self):
  from ariadne_mark.pipeline import SDK
  from ariadne_mark.errors import AriadneError
  sdk=SDK(self.marker,self.identity)
  try:
   source=self.video(audio=False);original=sdk.video_marker.encode_frames;calls=0
   def last_frame_crash(*args):
    nonlocal calls
    rows=original(*args);calls+=len(rows)
    if calls==24:sdk.video_marker._process.kill()
    return rows
   sdk.video_marker.encode_frames=last_frame_crash
   with self.assertRaises(AriadneError):sdk.mark(source,self.path/'end-crash.mp4',self.record('video'))
   self.assertFalse((self.path/'end-crash.mp4').exists())
   self.assertFalse((self.path/'end-crash.mp4.receipt.json').exists())
  finally:sdk.close()

 def test_closed_worker_can_restart_without_retained_exit_callback(self):
  from ariadne_mark.videoq import VideoWatermarker
  marker=VideoWatermarker()
  try:
   marker._load();self.assertTrue(marker._cleanup_registered)
   first=marker._process
   marker.close();self.assertFalse(marker._cleanup_registered);self.assertIsNotNone(first.poll())
   marker._load();self.assertTrue(marker._cleanup_registered);self.assertIsNot(marker._process,first)
  finally:marker.close()
