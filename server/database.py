"""Optional read-only Turso transport; local SQLite remains the default."""
from __future__ import annotations
import base64, json, os, re, sqlite3, urllib.request, urllib.error
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=4)
def _config(path):
 # Hosted functions cannot rely on a file outside the deployment bundle.  Keep
 # the file form for local operation and accept the same object as a secret
 # environment variable for managed runtimes.
 if path.startswith('json:'):
  return json.loads(path[5:])['databases']
 return json.loads(Path(path).expanduser().read_text())['databases']

def route(path):
 config=os.environ.get('SEOUL_TURSO_CONFIG')
 if os.environ.get('SEOUL_TURSO_CONFIG_JSON'):
  config='json:'+os.environ['SEOUL_TURSO_CONFIG_JSON']
 return _config(config).get(Path(path).name) if config else None

def available(path):return route(path) is not None or Path(path).is_file()
def database_bytes(path):
 entry=route(path)
 return entry['bytes'] if entry else Path(path).stat().st_size

class Row:
 def __init__(self,names,values):self.names=names;self.values=values
 def __getitem__(self,key):return self.values[self.names.index(key)] if isinstance(key,str) else self.values[key]
 def keys(self):return self.names
 def __iter__(self):return iter(self.values)
 def __len__(self):return len(self.values)

class Cursor:
 def __init__(self,rows):self.rows=iter(rows)
 def fetchone(self):return next(self.rows,None)
 def fetchall(self):return list(self.rows)
 def __iter__(self):return self.rows

def encode(value):
 if value is None:return {'type':'null'}
 if isinstance(value,(bytes,bytearray,memoryview)):return {'type':'blob','base64':base64.b64encode(value).decode()}
 if isinstance(value,(int,bool)):return {'type':'integer','value':str(int(value))}
 if isinstance(value,float):return {'type':'float','value':value}
 if isinstance(value,str):return {'type':'text','value':value}
 raise TypeError('Unsupported SQL parameter type')
def decode(value):
 kind=value['type']
 if kind=='null':return None
 if kind=='blob':
  encoded=value['base64'];return base64.b64decode(encoded+'='*((-len(encoded))%4),altchars=b'-_')
 if kind=='integer':return int(value['value'])
 return value['value']

class Connection:
 def __init__(self,entry):self.entry=entry;self.row_factory=sqlite3.Row
 def execute(self,statement,parameters=()):
  if not (re.match(r'^\s*(SELECT|WITH)\b',statement,re.I) or re.fullmatch(r'\s*PRAGMA\s+table_info\([A-Za-z_][A-Za-z_0-9]*\)\s*;?\s*',statement,re.I)):
   raise sqlite3.OperationalError('Turso transport is read-only')
  statement=re.sub(r'\b(FROM|JOIN)\s+metadata\b',lambda m:m[1]+' "'+self.entry['metadata_table']+'"',statement,flags=re.I)
  stmt={'sql':statement,'want_rows':True}
  if isinstance(parameters,Mapping):stmt['named_args']=[{'name':k,'value':encode(v)} for k,v in parameters.items()]
  else:stmt['args']=[encode(v) for v in parameters]
  body={'requests':[{'type':'execute','stmt':stmt},{'type':'close'}]}
  request=urllib.request.Request('https://'+self.entry['hostname']+'/v2/pipeline',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+self.entry['token']})
  try:
   with urllib.request.urlopen(request,timeout=60) as response:payload=json.load(response)
  except (urllib.error.URLError,TimeoutError):raise sqlite3.OperationalError('Turso connection failed') from None
  result=payload['results'][0]
  if result['type']=='error':raise sqlite3.OperationalError(result['error'].get('message','Turso SQL error'))
  result=result['response']['result'];names=[c['name'] for c in result['cols']]
  return Cursor([Row(names,[decode(v) for v in row]) for row in result['rows']])
 def close(self):pass
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

def connect_readonly(path):
 entry=route(path)
 if entry:return Connection(entry)
 connection=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
 connection.row_factory=sqlite3.Row
 return connection
