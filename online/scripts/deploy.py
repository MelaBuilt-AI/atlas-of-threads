"""Deploy the Atlas preview to the user's Cloudflare account without logging secrets.

Uses only named Atlas preview resources. Does not enable a subscription or alter
existing domain routes. Resource identifiers are recorded in ignored local config.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--account-id', required=True)
parser.add_argument('--token-file', type=Path, required=True)
args = parser.parse_args()
key = args.token_file.read_text().strip()
base = f'https://api.cloudflare.com/client/v4/accounts/{args.account_id}'


def api(path, data=None):
    request = urllib.request.Request(base+path, data=None if data is None else json.dumps(data).encode(),
        headers={'Authorization':'Bearer '+key, 'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        # Do not dump requests or vendor diagnostic logs containing credentials.
        raise SystemExit(f'Cloudflare {path.split("?")[0]} returned HTTP {error.code}') from None
    if not result.get('success'):
        raise SystemExit('Cloudflare declined the requested preview operation')
    return result['result']

name = 'atlas-online-preview'
databases = api('/d1/database?per_page=100')
database = next((x for x in databases if x['name']==name), None)
if database is None:
    database = api('/d1/database', {'name':name})
print('Preview D1 database ready.')
buckets = api('/r2/buckets')['buckets']
if not any(x['name']==name for x in buckets):
    api('/r2/buckets', {'name':name})
print('Preview R2 bucket ready.')
subdomain = api('/workers/subdomain')['subdomain']
config = json.loads(Path('wrangler.json').read_text())
config['account_id'] = args.account_id
config['d1_databases'][0]['database_id'] = database['uuid']
config['vars']['SITE_ORIGIN'] = f'https://{name}.{subdomain}.workers.dev'
local = Path('wrangler.local.json')
if local.exists():
    old = json.loads(local.read_text())
    for setting in ('GITHUB_CLIENT_ID', 'MODERATOR_GITHUB_IDS'):
        if old.get('vars', {}).get(setting):
            config['vars'][setting] = old['vars'][setting]
local.write_text(json.dumps(config,indent=2)+'\n')
query = f'/d1/database/{database["uuid"]}/query'
api(query, {'sql':'CREATE TABLE IF NOT EXISTS atlas_schema_migrations (name TEXT PRIMARY KEY)'})
applied = {x['name'] for x in api(query, {'sql':'SELECT name FROM atlas_schema_migrations'})[0]['results']}
for migration in sorted(Path('migrations').glob('*.sql')):
    if migration.name not in applied:
        statements = migration.read_text() + '\nINSERT INTO atlas_schema_migrations(name) VALUES (' + "'" + migration.name + "');"
        api(query, {'sql':statements})
        print('Applied',migration.name)
log_directory = tempfile.TemporaryDirectory(prefix='atlas-wrangler-')
log_path = Path(log_directory.name) / 'wrangler.log'
log_path.symlink_to(os.devnull)
env = dict(os.environ, CLOUDFLARE_API_TOKEN=key, CLOUDFLARE_ACCOUNT_ID=args.account_id,
           WRANGLER_LOG_PATH=str(log_path), WRANGLER_SEND_METRICS='false')
process = subprocess.run(['node','node_modules/wrangler/bin/wrangler.js','deploy','--config','wrangler.local.json'],
                         env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
print(process.stdout.replace(key,'[redacted]'))
log_directory.cleanup()
raise SystemExit(process.returncode)
