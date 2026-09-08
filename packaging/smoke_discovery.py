"""Frozen onboarding/API smoke with synthetic settings and no model calls."""
import argparse
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError, URLError


def smoke(command, application=None):
    with tempfile.TemporaryDirectory(prefix='atlas-discovery-') as folder:
        root=Path(folder)
        config=root/'native.json'
        config.write_text(json.dumps({'provider':'hermes','command':[sys.executable],
            'display_name':'Synthetic local agent','model':'synthetic/model','state_dir':str(root/'state')}))
        result=subprocess.run([*command,'adapter','local','--config',str(config),'describe'],capture_output=True,timeout=30)
        assert result.returncode==0,result.stderr
        assert json.loads(result.stdout)['default_model']=='synthetic/model'
        with socket.socket() as available:
            available.bind(('127.0.0.1',0))
            port=available.getsockname()[1]
        env={**os.environ,'TA_HARNESS_CONFIG':str(root/'harnesses.json'),'TA_WORKER_BACKEND':'application'}
        app=subprocess.Popen([*(application or command),'--store',str(root/'store'),'launch','--no-browser','--port',str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL, start_new_session=(os.name != "nt"))
        url=f'http://127.0.0.1:{port}'
        def post(path,body,origin=None):
            headers={'Content-Type':'application/json'}
            if origin:headers['Origin']=origin
            with urlopen(Request(url+path,data=json.dumps(body).encode(),headers=headers),timeout=60) as r:return json.load(r)
        try:
            for _ in range(100):
                try:
                    with urlopen(url+'/api/workspace',timeout=3) as r:
                        assert 'available_harnesses' in json.load(r)
                    break
                except (URLError,TimeoutError):time.sleep(.2)
            else:raise AssertionError('Frozen app startup failed')
            with urlopen(url+'/agent-connect.js') as r:assert b'AtlasAgentConnect' in r.read()
            with urlopen(url+'/music.js') as r:music=r.read().decode()
            with urlopen(url+'/sound.js') as r:sound=r.read().decode()
            effects=re.findall(r'file: "([^"]+\.ogg)"',sound)
            songs=re.findall(r'\["(\d{2}-[^"]+)",',music)
            assert len(effects)==33 and len(songs)==13
            for name in [*effects, *(f'music/{song}.ogg' for song in songs)]:
                with urlopen(Request(url+'/assets/audio/'+name,headers={'Range':'bytes=0-63'})) as r:
                    assert r.status==206 and r.headers['Accept-Ranges']=='bytes'
                    data=r.read()
                    assert len(data)==64 and data.startswith(b'OggS'),name
            with urlopen(Request(url+'/assets/audio/music/'+songs[0]+'.ogg',headers={'Range':'bytes=-128'})) as r:
                assert r.status==206 and len(r.read())==128
            result=post('/api/onboarding/discover',{})
            assert isinstance(result['agents'],list)
            assert all('config' not in a for a in result['agents'])
            help=post('/api/onboarding/remote/help',{'platform':'wsl','port':2222})
            assert 'LocalPorts 2222' in json.dumps(help)
            assert 'Undo:' in json.dumps(help)
            try:post('/api/onboarding/discover',{},'https://untrusted.invalid')
            except HTTPError as e:assert e.code==400
            else:raise AssertionError('Cross-origin setup accepted')
            assert not (root/'harnesses.json').exists()
            post('/api/application/quit',{})
        finally:
            if app.poll() is None:
                app.terminate()
            app.wait(timeout=20)
    print('PASS: frozen local adapter, discovery UI/API, 33 effects and 13 music tracks with byte ranges, firewall guidance and same-origin protection; no registration or model calls.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application', help='Desktop executable when separate from the console bridge')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if not args.command:parser.error('a console command is required')
    smoke(args.command, [args.application] if args.application else None)
