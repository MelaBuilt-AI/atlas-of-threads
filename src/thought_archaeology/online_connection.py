"""Explicit Personal Atlas pairing; credentials never enter browser payloads or exports."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from thought_archaeology import __version__
from thought_archaeology.store import Store, StoreError, _write_private_json_atomic
from thought_archaeology.updates import _ssl_context

SERVICE = 'https://atlas-online-preview.aarondkv.workers.dev'
CONNECTION_FILE = 'online-connection.json'


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a device credential to a redirected destination.


def _request(path: str, data: dict | None = None, token: str | None = None) -> dict:
    headers = {'Content-Type': 'application/json', 'Origin': SERVICE,
               'User-Agent': f'Atlas-of-Threads/{__version__}'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(SERVICE + path, headers=headers,
                      data=None if data is None else json.dumps(data).encode('utf-8'))
    try:
        with build_opener(_NoRedirect(), HTTPSHandler(context=_ssl_context())).open(request, timeout=15) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 401:
            raise StoreError('This device is no longer connected. Disconnect it here, then pair again.') from None
        if error.code == 403 and path == '/api/pairings/exchange':
            raise StoreError('Pairing code expired or already used. Create a new code in your signed-in Atlas.') from None
        if error.code == 429:
            raise StoreError('Device limit reached. Disconnect an unused device in your Atlas account.') from None
        raise StoreError(f'The online Atlas could not complete this action (HTTP {error.code}).') from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise StoreError('The online Atlas is unavailable. Your local inquiries remain available; try connecting again later.') from None


def _saved(store: Store) -> dict | None:
    path = store.root / CONNECTION_FILE
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def status(store: Store) -> dict:
    saved = _saved(store)
    return {'connected': bool(saved), 'service': SERVICE,
            'device': {key: saved[key] for key in ('id', 'name', 'owner')} if saved else None}


def connect(store: Store, code: str) -> dict:
    if not isinstance(code, str) or not code.strip() or len(code) > 100:
        raise StoreError('Paste the single-use pairing code from your signed-in Atlas.')
    with store.continuation_inbox_lock():
        if _saved(store):
            raise StoreError('Disconnect the current account before pairing another one.')
        credential = _request('/api/pairings/exchange', {'code': code.strip()})
        try:
            owner = _request('/api/me', token=credential['token'])['owner']
            if not owner or owner['instance_id'] != credential['id']:
                raise StoreError('The Atlas could not verify this device.')
            _write_private_json_atomic(store.root / CONNECTION_FILE,
                                       {**credential, 'owner': {'id': owner['id'], 'login': owner['login']}})
        except Exception:
            # A failed local save must not intentionally leave a usable orphan credential.
            try:
                _request('/api/instances/' + credential['id'] + '/revoke', {}, credential['token'])
            except StoreError:
                pass
            raise
    return status(store)


def check(store: Store) -> dict:
    saved = _saved(store)
    if not saved:
        return status(store)
    owner = _request('/api/me', token=saved['token'])['owner']
    if not owner:
        raise StoreError('This device has been revoked. Disconnect it here, then pair again.')
    return {**status(store), 'verified_now': True}


def disconnect(store: Store, *, forget_only: bool = False) -> dict:
    with store.continuation_inbox_lock():
        saved = _saved(store)
        if saved:
            if not forget_only:
                # A 401 also means the saved device credential is already unusable.
                owner = _request('/api/me', token=saved['token'])['owner']
                if owner:
                    _request('/api/instances/' + saved['id'] + '/revoke', {}, saved['token'])
            (store.root / CONNECTION_FILE).unlink()
    return {**status(store), 'forgot_only': forget_only}
