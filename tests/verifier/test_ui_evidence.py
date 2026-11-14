"""Functional UI labels with Node and a minimal DOM; no browser dependencies."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from ariadne_mark.public_verifier import public_report
from ariadne_mark.verification.media import summarize_watermarks

A = '014d123456789abc'
B = '014d000000000001'
Q = 'adobe.trustmark.Q.variax-bch5'
SCRIPT = r"""
const fs=require('fs'), vm=require('vm'), elements=new Map();
function element() {return {textContent:'',children:[],append(...xs){this.children.push(...xs)},replaceChildren(){this.children=[]},focus(){},addEventListener(){}}}
const document={getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id)},createElement(){return element()},querySelectorAll(){return []}};
const context=vm.createContext({document,fetch:async()=>({ok:false})});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
context.render(JSON.parse(fs.readFileSync(0,'utf8')));
console.log(JSON.stringify(elements.get('provenance').children.map(x=>x.textContent)));
"""


@unittest.skipUnless(shutil.which('node'), 'requires Node.js UI functional probe')
class UiEvidenceTests(unittest.TestCase):
    def render(self, observations, aggregates):
        watermark = summarize_watermarks(observations, aggregates, video=True)
        report = public_report({'schema_version': 2, 'label': 'Multiple watermark IDs found',
                                'c2pa': {'status': 'not_found'}, 'watermark': watermark,
                                'recovery': {'status': 'not_attempted'}, 'token_mismatch': False})
        script = Path(__file__).resolve().parents[2] / 'src/ariadne_mark/verifier_assets/app.js'
        result = subprocess.run(['node', '-e', SCRIPT, str(script)], input=json.dumps(report),
                                text=True, capture_output=True, timeout=10, check=True)
        return json.loads(result.stdout)

    def test_aggregate_only_candidates_are_unconfirmed_not_single_reads(self):
        fields = self.render([{'time': 0, 'token': None, 'algorithm': Q}],
                             [{'token': A, 'algorithm': Q}, {'token': B, 'algorithm': Q}])
        self.assertEqual(fields.count('Watermark ID (unconfirmed)'), 2)
        self.assertFalse(any('single read' in s or 'seen' in s for s in fields))
        self.assertIn(A, fields)
        self.assertIn(B, fields)

    def test_confirmed_and_individual_unconfirmed_remain_distinct(self):
        fields = self.render([{'time': 0, 'token': A, 'algorithm': Q},
                              {'time': 1, 'token': A, 'algorithm': Q},
                              {'time': 2, 'token': B, 'algorithm': Q}], [])
        self.assertEqual(fields.count('Watermark ID (confirmed)'), 1)
        self.assertEqual(fields.count('Watermark ID (unconfirmed)'), 1)
        self.assertFalse(any('single read' in s for s in fields))

    def test_id_text_is_rendered_as_text_not_html(self):
        # Public result renderer must preserve literal text through textContent.
        text = '<img src=x onerror=alert(1)>'
        fields = self.render([{'time': 0, 'token': text, 'algorithm': Q},
                              {'time': 1, 'token': B, 'algorithm': Q}], [])
        self.assertTrue(any(text in s for s in fields))
