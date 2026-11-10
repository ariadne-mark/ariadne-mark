import base64
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.parse import urlencode, quote

from ariadne_mark.registry import Registry
from ariadne_mark.server import make_server
from ariadne_mark.softbinding import ALGORITHMS, assertion, decode_query, query_value, validate_match
from tests.provenance.test_records import example_record

TOKEN = '014d000000000001'
ALG = ALGORITHMS['adobe.trustmark.Q.bch5']
MID = 'urn:c2pa:00000000-0000-4000-8000-000000000001'


class SoftBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.registry = Registry(self.root / 'registry.sqlite')
        self.record = example_record()
        self.bundle = {'id': MID, 'bytes': b'opaque-native-manifest', 'algorithm': ALG, 'public': True}

    def tearDown(self): self.temp.cleanup()

    def test_atomic_retry_conflict_and_rollback(self):
        self.registry.add(TOKEN, self.record, 'sha', {}, self.bundle)
        self.registry.add(TOKEN, self.record, 'sha', {}, self.bundle)
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.registry.add(TOKEN, self.record, 'different', {}, self.bundle)
        with self.assertRaises(ValueError):
            self.registry.add(TOKEN, self.record, 'sha', {}, {**self.bundle, 'bytes': b'different'})
        self.registry.remove(TOKEN, 'wrong')
        self.assertIsNotNone(self.registry.get_manifest(token=TOKEN))
        self.registry.remove(TOKEN, 'sha')
        self.assertIsNone(self.registry.get(TOKEN))
        self.assertIsNone(self.registry.get_manifest(manifest_id=MID))

    def test_manifest_conflict_rolls_back_asset_insert(self):
        self.registry.add(TOKEN, self.record, 'sha', {}, self.bundle)
        with self.assertRaises(sqlite3.IntegrityError):
            self.registry.add('014d000000000002', example_record(), 'sha2', {}, self.bundle)
        self.assertFalse(self.registry.contains('014d000000000002'))

    def test_private_manifests_are_not_returned_publicly(self):
        self.registry.add(TOKEN, self.record, 'sha', {}, {**self.bundle, 'public': False})
        self.assertIsNone(self.registry.get_manifest(token=TOKEN, public_only=True))
        self.assertEqual(self.registry.get_manifest(token=TOKEN)['bytes'], self.bundle['bytes'])
        ro = Registry(self.registry.path, read_only=True)
        with self.assertRaises(PermissionError): ro.add(TOKEN, self.record, 'sha', {})

    def test_tampered_stored_manifest_is_not_served(self):
        self.registry.add(TOKEN, self.record, 'sha', {}, self.bundle)
        with self.registry.connect() as db: db.execute('UPDATE manifests SET store=?', (b'changed',))
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.registry.get_manifest(token=TOKEN)

    def test_legacy_read_only_database_is_usable(self):
        path = self.root/'old.sqlite'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE assets (token TEXT PRIMARY KEY, asset_id TEXT, record TEXT, sha256 TEXT, receipt TEXT)')
        self.assertIsNone(Registry(path, read_only=True).get_manifest(token=TOKEN))

    def test_binding_queries_are_strict_and_formats_are_distinct(self):
        self.assertEqual(decode_query(ALG, query_value(TOKEN)), TOKEN)
        for alg, value in [('com.adobe.trustmark.Q',query_value(TOKEN)),(ALG,TOKEN),(ALG,'////'),(ALG,query_value(TOKEN)+'=')]:
            with self.subTest(alg=alg,value=value), self.assertRaises(ValueError): decode_query(alg,value)
        active = {'active_manifest': MID, 'manifests': {MID: {'assertions': [assertion('adobe.trustmark.Q.bch5', TOKEN)]}}}
        self.assertEqual(validate_match(active, ALG, TOKEN), MID)
        with self.assertRaises(ValueError): validate_match(active, ALG, '014d000000000002')
        extra = assertion('adobe.trustmark.Q.variax-bch5', TOKEN)
        extra['label'] = 'c2pa.soft-binding__1'
        active['manifests'][MID]['assertions'].append(extra)
        with self.assertRaises(ValueError): validate_match(active, ALG, TOKEN)

    def test_read_only_http_resolution_and_disabled_writes(self):
        self.registry.add(TOKEN, self.record, 'sha', {}, self.bundle)
        registry = self.registry
        class SDK:
            def __init__(self): self.registry = registry
            def verify(self,path):
                return {'watermark': {'status':'recovered_claim','token':TOKEN,
                    'samples':[{'token':TOKEN,'algorithm':'adobe.trustmark.Q.bch5'}]}}
        server = make_server(SDK(), port=0, public_manifests=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def request(method,path,body=None,headers=None):
            conn=http.client.HTTPConnection(*server.server_address,timeout=5)
            conn.request(method,path,body,headers or {});r=conn.getresponse()
            result=(r.status,r.getheader('Content-Type'),r.read());conn.close();return result
        try:
            query=urlencode({'alg':ALG,'value':query_value(TOKEN)})
            status,_,raw=request('GET','/matches/byBinding?'+query)
            self.assertEqual(status,200);self.assertEqual(json.loads(raw),{'matches':[{'manifestId':MID}]})
            status,ct,raw=request('GET','/manifests/'+quote(MID,safe=''))
            self.assertEqual((status,ct,raw),(200,'application/c2pa',self.bundle['bytes']))
            self.assertEqual(request('GET','/manifests/../../secret')[0],400)
            self.assertEqual(request('GET','/manifests/'+MID+'?returnActiveManifest=true')[0],400)
            self.assertEqual(request('POST','/manifests',b'overwrite')[0],404)
            status,_,raw=request('POST','/matches/byBinding',json.dumps({'alg':ALG,'value':query_value(TOKEN)}))
            self.assertEqual(status,200);self.assertEqual(json.loads(raw)['matches'][0]['manifestId'],MID)
            status,_,raw=request('POST','/matches/byContent',b'asset',{'Content-Type':'image/png'})
            self.assertEqual(status,200);self.assertEqual(json.loads(raw)['matches'][0]['manifestId'],MID)
            self.assertEqual(request('GET','/matches/byBinding?alg=unknown&value=x')[0],400)
            self.assertEqual(request('POST','/matches/byContent?maxResults='+'9'*5000,b'asset',{'Content-Type':'image/png'})[0],400)
            self.assertEqual(request('POST','/matches/byBinding','{"alg":"a","alg":"b","value":"x"}')[0],400)
        finally: server.shutdown();server.server_close();thread.join()
