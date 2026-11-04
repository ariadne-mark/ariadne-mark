import hashlib,io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from ariadne_mark import bootstrap_c2pa as bootstrap
class BootstrapTests(unittest.TestCase):
 def test_checksum_failure_never_leaves_an_installable_archive(self):
  spec={'url':'https://example.invalid/archive','filename':'source.zip','sha256':hashlib.sha256(b'expected').hexdigest()}
  with tempfile.TemporaryDirectory() as folder,patch('urllib.request.urlopen',return_value=io.BytesIO(b'wrong')):
   with self.assertRaisesRegex(ValueError,'checksum'):bootstrap.download(spec,Path(folder))
   self.assertEqual(list(Path(folder).iterdir()),[])
 def test_source_zip_cannot_write_outside_build_directory(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);archive=root/'source.zip'
   with zipfile.ZipFile(archive,'w') as z:z.writestr('../escaped.txt','bad')
   with self.assertRaisesRegex(ValueError,'Unsafe'):bootstrap.extract_source(archive,root/'output')
   self.assertFalse((root/'escaped.txt').exists())
 def test_system_install_requires_explicit_isolated_build_flag(self):
  with patch.object(bootstrap.platform,'system',return_value='Linux'),patch.object(bootstrap.platform,'machine',return_value='x86_64'),patch.object(bootstrap.sys,'prefix','/system'),patch.object(bootstrap.sys,'base_prefix','/system'),patch.object(bootstrap,'run') as run:
   with self.assertRaisesRegex(RuntimeError,'virtualenv'):bootstrap.install()
   run.assert_not_called()
 def test_stale_dependency_policy_is_not_accepted_as_provisioned(self):
  from ariadne_mark.videoq import installation_matches,ROOT,digest
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder);p=d/'runtime/node_modules/adm-zip';p.mkdir(parents=True)
   (p/'package.json').write_text(json.dumps({'version':'0.5.18'}))
   (d/'runtime/ariadne-install.json').write_text(json.dumps({'lock_sha256':digest(ROOT/'package-lock.json')}))
   self.assertFalse(installation_matches(d))
