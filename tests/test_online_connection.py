"""Synthetic HTTP pairing exercises the local credential boundary and offline behavior."""
import json
import stat
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from thought_archaeology import online_connection as connection
from thought_archaeology.serve import make_server, viz_dist_path
from thought_archaeology.store import Store, StoreError


@pytest.fixture
def paired_service(tmp_path, monkeypatch):
    state = {'active': False, 'used': False, 'offline': False, 'calls': []}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_GET(self):
            self.respond()
        def do_POST(self):
            self.respond()
        def respond(self):
            state['calls'].append(self.path)
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or '{}')
            status = 200
            if state['offline']:
                status, result = 503, {}
            elif self.path == '/api/pairings/exchange':
                if state['used'] or data.get('code') != 'synthetic-single-use-code':
                    status, result = 403, {}
                else:
                    state.update(active=True, used=True)
                    status, result = 201, {'id':'synthetic-device','token':'synthetic-private-token',
                                           'name':'Synthetic laptop','service':connection.SERVICE}
            elif self.path == '/api/me':
                result = {'owner':{'id':'42','login':'synthetic-owner','instance_id':'synthetic-device'}
                          if state['active'] and self.headers.get('Authorization') == 'Bearer synthetic-private-token' else None}
            elif self.path == '/api/instances/synthetic-device/revoke':
                state['active'] = False
                result = {'revoked':True}
            else:
                status, result = 404, {}
            body = json.dumps(result).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    monkeypatch.setattr(connection,'SERVICE',f'http://127.0.0.1:{server.server_port}')
    store = Store(tmp_path/'atlas'); store.initialize()
    yield store, state
    server.shutdown(); server.server_close()


def test_pairing_private_save_restart_check_and_disconnect(paired_service):
    store, state = paired_service
    assert connection.status(store)['connected'] is False
    assert state['calls'] == []
    result = connection.connect(store,'synthetic-single-use-code')
    assert result['device']['owner'] == {'id':'42','login':'synthetic-owner'}
    assert 'token' not in json.dumps(result)
    path = store.root/connection.CONNECTION_FILE
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert 'synthetic-private-token' in path.read_text()
    assert connection.status(Store(store.root)) == result
    assert connection.check(Store(store.root))['verified_now']
    with pytest.raises(StoreError,match='Disconnect the current'):
        connection.connect(store,'synthetic-single-use-code')
    assert connection.disconnect(store)['connected'] is False
    assert not state['active'] and not path.exists()
    with pytest.raises(StoreError,match='expired or already used'):
        connection.connect(store,'synthetic-single-use-code')


def test_offline_local_use_and_explicit_forget_preserve_boundaries(paired_service):
    store, state = paired_service
    connection.connect(store,'synthetic-single-use-code')
    state['offline'] = True
    calls = len(state['calls'])
    assert connection.status(store)['connected']  # Startup is a local read.
    assert len(state['calls']) == calls
    with pytest.raises(StoreError,match='could not complete'):
        connection.disconnect(store)
    assert connection.status(store)['connected']
    calls = len(state['calls'])
    assert connection.disconnect(store,forget_only=True)['forgot_only']
    assert len(state['calls']) == calls and state['active']


def test_remote_revocation_is_detected_and_can_be_removed(paired_service):
    store, state = paired_service
    connection.connect(store,'synthetic-single-use-code')
    state['active'] = False
    with pytest.raises(StoreError,match='revoked'):
        connection.check(store)
    assert connection.disconnect(store)['connected'] is False


def test_local_http_never_returns_credential_and_rejects_foreign_origin(paired_service):
    store, state = paired_service
    server = make_server(store,port=0,dist=viz_dist_path())
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base = f'http://127.0.0.1:{server.server_address[1]}'
    def post(path,data,origin=base):
        return urlopen(Request(base+path,json.dumps(data).encode(),
                               headers={'Content-Type':'application/json','Origin':origin}))
    try:
        with pytest.raises(HTTPError):
            post('/api/online/connect',{'code':'synthetic-single-use-code'},'https://foreign.example')
        assert state['calls'] == []
        with post('/api/online/connect',{'code':'synthetic-single-use-code'}) as response:
            data = json.load(response)
        assert data['connected'] and 'token' not in json.dumps(data)
        with urlopen(base+'/api/online/connection') as response:
            assert 'synthetic-private-token' not in response.read().decode()
        # The ordinary static server cannot expose store files.
        with pytest.raises(HTTPError):
            urlopen(base+'/online-connection.json')
        with post('/api/online/disconnect',{}) as response:
            assert json.load(response)['connected'] is False
    finally:
        server.shutdown();server.server_close()
