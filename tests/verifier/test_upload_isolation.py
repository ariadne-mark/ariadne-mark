import http.client, socket, threading, time, unittest
from ariadne_mark.server import make_server
class UploadIsolationTests(unittest.TestCase):
    def test_slow_upload_does_not_lock_inference_and_has_total_deadline(self):
        class SDK:
            def verify(self,path):return {'label':'ok'}
        server=make_server(SDK(),port=0,upload_timeout=.6,upload_slots=2)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        slow=socket.create_connection(server.server_address,timeout=3)
        try:
            slow.sendall(b'POST /verify?format=png HTTP/1.0\r\nContent-Length: 100\r\n\r\nx')
            time.sleep(.08)
            connection=http.client.HTTPConnection(*server.server_address,timeout=2)
            connection.request('POST','/verify?format=png',b'valid')
            response=connection.getresponse();self.assertEqual(response.status,200);response.read();connection.close()
            self.assertIn(b'408',slow.recv(1024))
        finally:
            slow.close();server.shutdown();server.server_close();thread.join()
    def test_production_requires_roots(self):
        with self.assertRaisesRegex(ValueError,'trust anchors'):make_server(object(),production=True,port=0)
