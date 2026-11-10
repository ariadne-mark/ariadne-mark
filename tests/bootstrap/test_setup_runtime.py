"""Installed-wheel installer resources and explicit-only provisioning policy."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ariadne_mark import setup_runtime as setup


class SetupTests(unittest.TestCase):
    def contexts(self):
        stack=ExitStack()
        for context in [patch.object(setup.platform,'system',return_value='Linux'),
                        patch.object(setup.platform,'machine',return_value='x86_64'),
                        patch.object(setup.sys,'version_info',(3,12)),
                        patch.object(setup.sys,'prefix','/venv'),patch.object(setup.sys,'base_prefix','/system')]:
            stack.enter_context(context)
        return stack

    def test_both_packaged_locks_have_qualified_hashes(self):
        pins=json.loads((setup.ROOT/'runtime-locks.json').read_text())['locks']
        for kind in ['media','video']:
            content=(setup.ROOT/pins[kind]['filename']).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(),pins[kind]['sha256'])
            self.assertNotIn(b'c2pa-python==',content)
        self.assertNotIn(b'torch==',(setup.ROOT/pins['video']['filename']).read_bytes())

    def test_explicit_setup_orders_bootstrap_pinned_install_check_and_preflight(self):
        with self.contexts(),patch.object(setup.subprocess,'run') as run:
            report=setup.install('media')
        calls=[c.args[0] for c in run.call_args_list]
        self.assertEqual(len(calls),4)
        self.assertEqual(calls[0][1:3],['-m','ariadne_mark.bootstrap_c2pa'])
        self.assertIn('--require-hashes',calls[1]);self.assertIn('--only-binary=:all:',calls[1])
        self.assertIn('--no-binary=trustmark',calls[1])
        self.assertEqual(calls[-1][-2:],['runtime','check'])
        self.assertFalse(report['models_provisioned'])

    def test_video_wheelhouse_and_fetch_do_not_select_image_or_legacy_models(self):
        with tempfile.TemporaryDirectory() as folder,self.contexts(),patch.object(setup.shutil,'which',return_value='/bin/tool'),patch.object(setup.subprocess,'run') as run:
            report=setup.install('video',wheelhouse=folder,fetch_models=True)
            calls=run.call_args_list
            self.assertEqual(calls[-1].args[0][-2:],['--engine','video'])
            self.assertNotIn('--no-binary=trustmark',calls[1].args[0])
            self.assertTrue(all(c.kwargs['env']['PIP_NO_INDEX']=='1' for c in calls))
            self.assertFalse(report['legacy_decoders_included'])

    def test_tampered_lock_rejected_before_network_or_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);pins=json.loads((setup.ROOT/'runtime-locks.json').read_text())
            (root/'runtime-locks.json').write_text(json.dumps(pins))
            (root/pins['locks']['media']['filename']).write_text('tampered')
            with self.contexts(),patch.object(setup,'ROOT',root),patch.object(setup.subprocess,'run') as run:
                with self.assertRaisesRegex(ValueError,'checksum'):setup.install()
                run.assert_not_called()

    def test_unsupported_platform_and_unapproved_system_install_do_not_mutate(self):
        with patch.object(setup.platform,'system',return_value='Darwin'),patch.object(setup.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'Linux'):setup.install()
            run.assert_not_called()
        with self.contexts(),patch.object(setup.sys,'prefix','/system'),patch.object(setup.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'virtualenv'):setup.install()
            run.assert_not_called()
