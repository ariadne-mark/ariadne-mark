import http.client,socket,threading,time,unittest
from ariadne_mark.server import make_server
class HeaderDeadlineTests(unittest.TestCase):
 def test_all_handler_slots_recover_after_total_header_deadline(self):
  server=make_server(object(),port=0,header_timeout=.35)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();clients=[]
  try:
   for _ in range(16):
    connection=socket.create_connection(server.server_address,timeout=2);connection.sendall(b'GET /health HTTP/1.0\r\nX-Slow: ');clients.append(connection)
   # Keep sending within each recv timeout; a total deadline must still win.
   start=time.monotonic()
   while time.monotonic()-start<.65:
    for connection in clients:
     try:connection.sendall(b'x')
     except OSError:pass
    time.sleep(.05)
   healthy=http.client.HTTPConnection(*server.server_address,timeout=2)
   healthy.request('GET','/health');response=healthy.getresponse();self.assertEqual(response.status,200);response.read();healthy.close()
  finally:
   for connection in clients:connection.close()
   server.shutdown();server.server_close();thread.join()
