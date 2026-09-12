"""Publish only committed synthetic fixtures, then revoke their temporary device.

Requires the preview deployment's administrator token. No runtime auth bypass is
installed. The synthetic owner is explicitly distinguished from GitHub owners.
"""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import urllib.request
import urllib.error
import uuid

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--token-file',type=Path,required=True)
args=parser.parse_args()
config=json.loads(Path('wrangler.local.json').read_text())
cf_key=args.token_file.read_text().strip()
root=f'https://api.cloudflare.com/client/v4/accounts/{config["account_id"]}/d1/database/{config["d1_databases"][0]["database_id"]}/query'


def query(sql,params=()):
    request=urllib.request.Request(root,data=json.dumps({'sql':sql,'params':list(params)}).encode(),headers={'Authorization':'Bearer '+cf_key,'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=30) as response:
        result=json.load(response)
    if not result.get('success'):
        raise SystemExit('Preview fixture setup was rejected')
    return result['result']

query('INSERT INTO owners(id,login,kind,created_at) VALUES(?,?,?,?) ON CONFLICT DO NOTHING',('synthetic-publisher','Synthetic publisher','synthetic',1))
instance=str(uuid.uuid4());key=secrets.token_urlsafe(48)
query('INSERT INTO instances VALUES(?,?,?,?,?,NULL)',(instance,'synthetic-publisher','One-time synthetic preview seed',hashlib.sha256(key.encode()).hexdigest(),1))
try:
    for path in sorted(Path('test/fixtures').glob('*.json')):
        artifact=json.loads(path.read_text())
        request=urllib.request.Request(config['vars']['SITE_ORIGIN']+'/api/publications',data=json.dumps({'artifact':artifact,'reviewed':True}).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'application/json','User-Agent':'Atlas-of-Threads-Preview/0.1'})
        try:
            with urllib.request.urlopen(request,timeout=60) as response:
                result=json.load(response)
        except urllib.error.HTTPError as error:
            detail=error.read().decode('utf-8', errors='replace').replace(key,'[redacted]').replace(cf_key,'[redacted]')
            raise SystemExit(f'Fixture publication returned HTTP {error.code}: {detail[:600]}') from None
        print('Published synthetic fixture',path.name,result['id'][:12])
finally:
    query('UPDATE instances SET revoked_at=unixepoch() WHERE id=?',(instance,))
    print('Temporary fixture device revoked.')
