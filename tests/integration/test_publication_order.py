"""Real process death against the SDK publication sequence (stubbed media only)."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
CHILD=r'''
import os,shutil,sys
from pathlib import Path
from unittest.mock import patch
from ariadne_mark.pipeline import SDK
from ariadne_mark.registry import Registry
from ariadne_mark.signing import SigningIdentity
from tests.provenance.test_records import example_record
p=Path(sys.argv[1]);mode=sys.argv[2];record=example_record();token='014d000000000001'
class Image:
 def getbands(self):return ('R','G','B')
 def save(self,p,*args,**kw):Path(p).write_bytes(b'content')
class Marker:
 def encode(self,image,token):return image
reg=Registry(p/'registry.sqlite')
real_add=reg.add
if mode=='registry':reg.add=lambda *a,**kw:os._exit(137)
real_link=os.link
def link(a,b):
 real_link(a,b)
 if mode=='after_media' and str(b).endswith('out.png'):os._exit(137)
 if mode=='after_receipt' and str(b).endswith('.receipt.json'):os._exit(137)
verified={'c2pa':{'status':'verified_claim','token':token,'record':record.to_dict()},'watermark':{'status':'recovered_claim','token':token,'samples':[{'token':token}]}}
with patch.object(SDK,'check_runtime'),patch('ariadne_mark.pipeline.inspect_c2pa',return_value={'status':'not_found'}),patch('ariadne_mark.pipeline.open_image',return_value=Image()),patch('ariadne_mark.pipeline.new_token',return_value=token),patch('ariadne_mark.pipeline.sign_file',side_effect=lambda a,b,*x,**kw:shutil.copyfile(a,b)),patch.object(SDK,'verify',return_value=verified),patch('ariadne_mark.pipeline.os.link',side_effect=link):
 SDK(Marker(),SigningIdentity(Path('c'),Path('k'),True),reg).mark(p/'in.png',p/'out.png',record)
'''
class PublicationTests(unittest.TestCase):
 def test_kill_at_each_boundary_never_exposes_media_without_receipt_and_registry(self):
  from ariadne_mark.registry import Registry
  for mode in ['registry','after_receipt','after_media']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
    p=Path(folder);(p/'in.png').write_bytes(b'source')
    proc=subprocess.run([sys.executable,'-c',CHILD,folder,mode],capture_output=True,text=True)
    self.assertEqual(proc.returncode,137,proc.stderr)
    if mode=='after_media':
     self.assertTrue((p/'out.png').exists());receipt=json.loads((p/'out.png.receipt.json').read_text());self.assertTrue(receipt['registry_recorded']);self.assertIsNotNone(Registry(p/'registry.sqlite',read_only=True).get(receipt['token']))
    else:self.assertFalse((p/'out.png').exists())
 def test_read_only_registry_sees_updates_but_rejects_writes(self):
  from ariadne_mark.registry import Registry
  from tests.provenance.test_records import example_record
  with tempfile.TemporaryDirectory() as folder:
   rw=Registry(Path(folder)/'registry.sqlite');ro=Registry(rw.path,read_only=True);record=example_record();token='014d000000000001'
   rw.add(token,record,'abc',{});self.assertEqual(ro.get(token)['sha256'],'abc')
   with self.assertRaises(PermissionError):ro.add(token,record,'abc',{})
   import sqlite3
   with ro.connect() as db:
    with self.assertRaises(sqlite3.OperationalError):db.execute('DELETE FROM assets')
