"""ISS-12: video presets of one SDK share a single Node worker process."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

FAKE_WORKER = r'''
import json, os, struct, sys
log = open(sys.argv[1], "a")
def send(h):
    data = json.dumps({**h, "n": 0}).encode()
    sys.stdout.buffer.write(struct.pack(">I", len(data)) + data); sys.stdout.buffer.flush()
send({"ready": True})
while True:
    head = sys.stdin.buffer.read(4)
    if len(head) < 4: break
    h = json.loads(sys.stdin.buffer.read(struct.unpack(">I", head)[0]))
    if h.get("n"): sys.stdin.buffer.read(h["n"])
    log.write(json.dumps({"pid": os.getpid(), "op": h["op"], "profile": h.get("profile")}) + "\n"); log.flush()
    send({"ok": True} if h["op"] == "begin" else {"frames": 0, "profile": None})
'''


class SharedWorkerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.log = Path(self.folder.name) / 'worker.log'
        self.spawned = []

    def popen(self, real):
        def start(command, **kwargs):
            process = real([sys.executable, '-c', FAKE_WORKER, str(self.log)], **kwargs)
            self.spawned.append(process.pid)
            return process
        return start

    def sdk(self):
        from ariadne_mark.pipeline import SDK
        from ariadne_mark.videoq import VideoWatermarker
        return SDK(video_marker=VideoWatermarker(profile='economy_5s'))

    def test_all_presets_use_one_process_and_send_their_own_preset(self):
        from ariadne_mark import videoq
        token = '014d123456789abc'
        with patch.object(videoq, 'check_models'), \
             patch.object(videoq.subprocess, 'Popen', side_effect=self.popen(subprocess.Popen)):
            sdk = self.sdk()
            try:
                views = [sdk._select_video_marker(p) for p in ('economy_5s', 'economy_2s', 'resilient')]
                for view in views:
                    with view.encoding_session(token):
                        pass
                self.assertEqual(len(self.spawned), 1)
                self.assertEqual(len({id(v._worker) for v in views}), 1)
                self.assertIs(views[1]._lock, views[2]._lock)
                rows = [json.loads(l) for l in self.log.read_text().splitlines()]
                begins = [r for r in rows if r['op'] == 'begin']
                self.assertEqual([r['profile'] for r in begins], ['economy_5s', 'economy_2s', 'resilient'])
                self.assertEqual({r['pid'] for r in rows}, {self.spawned[0]})
                self.assertEqual([v.profile for v in views], ['economy_5s', 'economy_2s', 'resilient'])
                self.assertEqual(views[2].profile_id, 'resilient-cpu-candidate-v1')
            finally:
                sdk.close()

    def test_closing_any_view_stops_the_shared_child_and_a_new_request_restarts_it(self):
        from ariadne_mark import videoq
        with patch.object(videoq, 'check_models'), \
             patch.object(videoq.subprocess, 'Popen', side_effect=self.popen(subprocess.Popen)):
            sdk = self.sdk()
            resilient = sdk._select_video_marker('resilient')
            resilient._load()
            process = resilient._process
            sdk.video_marker.close()
            self.assertIsNone(resilient._process)
            self.assertIsNotNone(process.poll())  # child really exited
            resilient._load()
            self.assertEqual(len(self.spawned), 2)
            sdk.close()
            self.assertIsNone(sdk.video_marker._process)

    def test_with_profile_validates_the_preset(self):
        from ariadne_mark.videoq import VideoWatermarker
        with self.assertRaises(ValueError):
            VideoWatermarker().with_profile('compliant')
