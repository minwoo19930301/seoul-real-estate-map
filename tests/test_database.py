import json, os, sqlite3, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from server.database import Connection, encode, decode, connect_readonly, available

class DatabaseTests(unittest.TestCase):
 def test_types_preserve_blob_large_integer_and_null(self):
  for value in [None,2**62,-5,1.5,'서울',b'\x00\xff']:
   self.assertEqual(decode(encode(value)),value)
 def test_unpadded_remote_blob(self):
  self.assertEqual(decode({'type':'blob','base64':'AP8'}),b'\x00\xff')
 def test_local_default(self):
  with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{},clear=True):
   p=Path(d)/'a.sqlite'
   with sqlite3.connect(p) as c:c.execute('CREATE TABLE x(v)');c.execute('INSERT INTO x VALUES (7)')
   with connect_readonly(p) as c:self.assertEqual(c.execute('SELECT v FROM x').fetchone()['v'],7)
   self.assertTrue(available(p))
 def test_metadata_and_named_parameters(self):
  payload={'results':[{'type':'ok','response':{'result':{'cols':[{'name':'key'},{'name':'value'}],'rows':[[encode('서울'),encode(12)]]}}}]}
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return json.dumps(payload).encode()
  with patch('urllib.request.urlopen',return_value=Response()) as request:
   c=Connection({'hostname':'example.invalid','token':'test','metadata_table':'terrain_metadata'})
   r=c.execute('SELECT key,value FROM metadata WHERE key=:key',{'key':'서울'}).fetchone()
   self.assertEqual(dict(r),{'key':'서울','value':12});self.assertEqual(r[1],12)
   body=json.loads(request.call_args.args[0].data)
   self.assertIn('terrain_metadata',body['requests'][0]['stmt']['sql'])
   self.assertEqual(body['requests'][0]['stmt']['named_args'][0]['value']['value'],'서울')
 def test_no_remote_writes(self):
  with self.assertRaises(sqlite3.OperationalError):Connection({}).execute('DELETE FROM buildings')

if __name__=='__main__':unittest.main()
