"""Offline RFC3161 TSA regression: expired signer with/without trusted time."""
import os,unittest,tempfile,subprocess,threading,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
@unittest.skipUnless(os.environ.get('ARIADNE_MEDIA_TESTS')=='1','requires OpenSSL, C2PA and Pillow')
class TimestampExpiryTests(unittest.TestCase):
 def test_trusted_time_preserves_expired_signer_but_unstamped_file_is_not_tampering(self):
  from cryptography import x509
  from cryptography.hazmat.primitives import hashes,serialization
  from cryptography.hazmat.primitives.asymmetric import ec,rsa
  from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
  from ariadne_mark.signing import SigningIdentity,sign_file
  from ariadne_mark.verification.media import inspect_c2pa
  from tests.provenance.test_records import example_record
  from PIL import Image
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);now=datetime.now(timezone.utc);pem=serialization.Encoding.PEM
   root_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
   root_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Offline TSA test root')])
   root=(x509.CertificateBuilder().subject_name(root_name).issuer_name(root_name).public_key(root_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.KeyUsage(False,False,False,False,False,True,True,False,False),critical=True).add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()),critical=False).sign(root_key,hashes.SHA256()))
   def leaf(key,name,eku,expire,critical=False):
    return (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)])).issuer_name(root_name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(expire).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.KeyUsage(True,False,False,False,False,False,False,False,False),critical=True).add_extension(x509.ExtendedKeyUsage([eku]),critical=critical).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),critical=False).add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False).sign(root_key,hashes.SHA256()))
   key=ec.generate_private_key(ec.SECP256R1());tsa_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
   expiry=now+timedelta(seconds=10)
   signer=leaf(key,'Short lived signer',ExtendedKeyUsageOID.EMAIL_PROTECTION,expiry)
   tsa=leaf(tsa_key,'Offline trusted TSA',ExtendedKeyUsageOID.TIME_STAMPING,now+timedelta(days=1),True)
   (p/'root.pem').write_bytes(root.public_bytes(pem));(p/'cert.pem').write_bytes(signer.public_bytes(pem)+root.public_bytes(pem));(p/'tsa.pem').write_bytes(tsa.public_bytes(pem))
   for name,k in [('key',key),('tsa',tsa_key)]:
    (p/(name+'.key')).write_bytes(k.private_bytes(pem,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
   (p/'serial').write_text('01\n')
   (p/'tsa.cnf').write_text(f'''[tsa]\nserial = {p/'serial'}\nsigner_cert = {p/'tsa.pem'}\ncerts = {p/'root.pem'}\nsigner_key = {p/'tsa.key'}\nsigner_digest = sha256\ndefault_policy = 1.2.3.4.1\nother_policies = 1.2.3.4.5\ndigests = sha256,sha384,sha512\naccuracy = secs:1\nordering = yes\ntsa_name = yes\ness_cert_id_chain = yes\ness_cert_id_alg = sha256\n''')
   class TSA(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
     (p/'request.tsq').write_bytes(self.rfile.read(int(self.headers['Content-Length'])))
     done=subprocess.run(['openssl','ts','-reply','-config',str(p/'tsa.cnf'),'-section','tsa','-queryfile',str(p/'request.tsq'),'-out',str(p/'reply.tsr')],capture_output=True)
     if done.returncode:self.send_error(500);return
     body=(p/'reply.tsr').read_bytes();self.send_response(200);self.send_header('Content-Type','application/timestamp-reply');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   server=HTTPServer(('127.0.0.1',0),TSA);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   try:
    Image.new('RGB',(256,256),'gray').save(p/'input.png')
    for name,url in [('plain',None),('stamped',f'http://127.0.0.1:{server.server_port}')]:
     sign_file(p/'input.png',p/(name+'.png'),example_record(),'014d000000000001',SigningIdentity(p/'cert.pem',p/'key.key',True,url))
    before=inspect_c2pa(p/'stamped.png',trust_anchors=p/'root.pem')
    self.assertEqual(before['timestamp_trust'],'trusted',before)
    time.sleep(max(0,(expiry+timedelta(seconds=1)-datetime.now(timezone.utc)).total_seconds()))
    stamped=inspect_c2pa(p/'stamped.png',trust_anchors=p/'root.pem');plain=inspect_c2pa(p/'plain.png',trust_anchors=p/'root.pem')
    self.assertEqual(stamped['status'],'verified_claim',stamped)
    self.assertEqual(plain['status'],'expired_credential',plain)
   finally:server.shutdown();server.server_close();thread.join()
