"""ISS-08: resource cache placement honours XDG and never moves existing caches."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ariadne_mark import paths


class CachePathTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.home = Path(self.folder.name) / 'home'
        self.xdg = Path(self.folder.name) / 'xdg'
        self.home.mkdir()

    def env(self, **values):
        return patch.dict(os.environ, {'HOME': str(self.home), **values}, clear=False)

    def test_xdg_cache_home_is_used_when_set(self):
        with self.env(XDG_CACHE_HOME=str(self.xdg)):
            self.assertEqual(paths.cache_path('video-v1'), self.xdg / 'ariadne-mark/video-v1')

    def test_default_is_home_cache_without_xdg(self):
        with self.env(XDG_CACHE_HOME=''):
            self.assertEqual(paths.cache_path('video-v1'), self.home / '.cache/ariadne-mark/video-v1')

    def test_relative_xdg_is_ignored_as_the_spec_requires(self):
        with self.env(XDG_CACHE_HOME='relative/cache'):
            self.assertEqual(paths.cache_root(), self.home / '.cache/ariadne-mark')

    def test_existing_legacy_install_is_reused_not_moved(self):
        legacy = self.home / '.cache/ariadne-mark/video-v1'
        legacy.mkdir(parents=True)
        with self.env(XDG_CACHE_HOME=str(self.xdg)):
            self.assertEqual(paths.cache_path('video-v1'), legacy)
            self.assertFalse((self.xdg / 'ariadne-mark').exists())
            (self.xdg / 'ariadne-mark/video-v1').mkdir(parents=True)
            self.assertEqual(paths.cache_path('video-v1'), self.xdg / 'ariadne-mark/video-v1')

    def test_explicit_video_data_wins(self):
        from ariadne_mark.videoq import data_dir
        with self.env(XDG_CACHE_HOME=str(self.xdg), ARIADNE_VIDEO_DATA='/opt/explicit'):
            self.assertEqual(data_dir(), Path('/opt/explicit'))
        with patch.dict(os.environ, {'HOME': str(self.home), 'XDG_CACHE_HOME': str(self.xdg)}):
            os.environ.pop('ARIADNE_VIDEO_DATA', None)
            self.assertEqual(data_dir(), self.xdg / 'ariadne-mark/video-v1')

    def test_standalone_bootstrap_uses_the_same_rule(self):
        from ariadne_mark.bootstrap_c2pa import _default_cache
        with self.env(XDG_CACHE_HOME=str(self.xdg)):
            self.assertEqual(_default_cache(), self.xdg / 'ariadne-mark/c2pa-bootstrap-v1')
        (self.home / '.cache/ariadne-mark/c2pa-bootstrap-v1').mkdir(parents=True)
        with self.env(XDG_CACHE_HOME=str(self.xdg)):
            self.assertEqual(_default_cache(), self.home / '.cache/ariadne-mark/c2pa-bootstrap-v1')

    def test_video_provisioning_uses_a_throwaway_npm_cache(self):
        from ariadne_mark import videoq
        seen = {}

        def run(args, **kwargs):
            seen['cache'] = kwargs['env']['npm_config_cache']
            raise OSError('stop after capturing the environment')
        with self.env(ARIADNE_VIDEO_DATA=str(self.xdg / 'video')), \
             patch.object(videoq, 'check_models', side_effect=videoq.MissingModel('absent')), \
             patch.object(videoq.shutil, 'which', return_value='/usr/bin/true'), \
             patch.object(videoq.subprocess, 'run', side_effect=run):
            with self.assertRaises(videoq.MissingModel):
                videoq.fetch_models()
        self.assertTrue(seen['cache'].startswith(str(self.xdg / 'video')))
        self.assertFalse(Path(seen['cache']).exists())  # removed after provisioning
        self.assertFalse((self.home / '.npm').exists())
