"""Real configuration loading must warn when public provenance is withheld."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ariadne_mark.server import serve


class StartupWarningTests(unittest.TestCase):
    def test_unconfigured_sources_warn_and_reviewed_sources_remove_warning(self):
        class SDK:
            def close(self):
                self.closed = True
        with tempfile.TemporaryDirectory() as folder:
            approved = Path(folder) / 'sources.json'
            approved.write_text(json.dumps({'schema_version': 1, 'sources': [
                {'publisher': 'Fixture', 'system': {'name': 'Generator', 'version': '1'}}]}))
            for source, warning in [(None, True), (approved, False)]:
                with self.subTest(configured=source is not None), patch('socketserver.BaseServer.serve_forever'):
                    stderr = io.StringIO(); sdk = SDK()
                    with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                        serve(sdk, port=0, public_sources=source)
                    self.assertEqual('No reviewed public sources configured' in stderr.getvalue(), warning)
                    self.assertTrue(sdk.closed)
