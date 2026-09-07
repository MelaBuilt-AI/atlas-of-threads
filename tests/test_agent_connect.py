"""Synthetic discovery/onboarding acceptance. No provider or LAN dependency."""
import base64
import json
from pathlib import Path
import subprocess
import sys

import pytest

from thought_archaeology import agent_connect as connect
from thought_archaeology.adapters import host_probe
from thought_archaeology.harness import HarnessError, HarnessRegistry
from thought_archaeology.serve import InhabitHandler, ServeError
from thought_archaeology.store import Store


@pytest.fixture
def environment(monkeypatch, tmp_path):
    monkeypatch.setenv('TA_HARNESS_CONFIG',str(tmp_path/'config/harnesses.json'))
    connect._pending.clear()
    return Store(tmp_path/'store')


def inventory():
    return {'home':'/synthetic/home','platform':'linux','agents':[
        {'id':'openclaw:main','family':'openclaw','display_name':'Synthetic Jr',
         'model':'synthetic/model','ready':True,'detail':'Synthetic configured agent',
         'config':{'provider':'openclaw','display_name':'Synthetic Jr','model':'synthetic/model',
                   'command':['/private/native-cli'],'context_files':['/private/persona.md']}}]}


def test_discovery_is_read_only_and_hides_native_config(monkeypatch,environment):
    monkeypatch.setattr(host_probe,'discover',inventory)
    result=connect.local_discovery()
    assert result['agents'][0]['display_name']=='Synthetic Jr'
    assert 'config' not in result['agents'][0]
    assert '/private/' not in json.dumps(result)
    assert not environment.exists()
    assert not HarnessRegistry().path.exists()


@pytest.mark.parametrize('change',[{'host':'-oProxyCommand=bad'}, {'host':'host; touch bad'},
    {'user':'user@host'}, {'user':'$(bad)'}, {'port':0}, {'port':-1}, {'port':65536}, {'port':'bad'},
    {'platform':'windows'}, {'identity':'/nonexistent/synthetic/key'}])
def test_destination_validation_before_ssh(change):
    with pytest.raises(HarnessError):
        connect.settings({'host':'host.invalid','user':'test','port':22,**change})


def test_expired_scan_cannot_connect(monkeypatch,environment):
    token=connect.remember({'kind':'local','inventory':inventory()})
    connect._pending[token]['expires']=0
    with pytest.raises(HarnessError,match='expired'):
        connect.connect_agent({'token':token},environment,lambda _:None)
    assert not environment.exists()


def test_local_connect_uses_server_inventory_not_browser_commands(monkeypatch,environment):
    token=connect.remember({'kind':'local','inventory':inventory()})
    monkeypatch.setattr(connect,'describe_harness',lambda *a,**kw:{'default_model':'synthetic/model'})
    result=connect.connect_agent({'token':token,'agent_id':'openclaw:main','name':'synthetic',
        'command':['untrusted-browser-command'],'config':{'command':['bad']}},environment,
        lambda _: (sys.executable,('-m','thought_archaeology.launcher','adapter','local')))
    spec=HarnessRegistry().get('synthetic')
    assert result['ok'] and spec.session_only and not spec.memory_root
    config=json.loads(Path(spec.argv[-1]).read_text())
    assert config['command']==['/private/native-cli']
    assert not list(environment.iter_session_ids())
    with pytest.raises(HarnessError,match='already exists'):
        connect.connect_agent({'token':token,'agent_id':'openclaw:main','name':'synthetic'},environment,lambda _:None)


def test_failed_health_check_rolls_back_registration(monkeypatch,environment):
    token=connect.remember({'kind':'local','inventory':inventory()})
    def fail(*a,**kw):raise HarnessError('private native diagnostics')
    monkeypatch.setattr(connect,'describe_harness',fail)
    with pytest.raises(HarnessError,match='rolled back') as e:
        connect.connect_agent({'token':token,'agent_id':'openclaw:main','name':'broken'},environment,
                              lambda _: (sys.executable,()))
    assert not HarnessRegistry().specs()
    assert 'private native diagnostics' not in str(e.value)


def test_remote_install_uses_posix_path_and_stdin_payload(monkeypatch,environment):
    s=connect.settings({'host':'host.invalid','user':'synthetic'})
    token=connect.remember({'kind':'remote','settings':s,'inventory':inventory()})
    seen=[]
    def ssh(s,argv,**kwargs):
        seen.append((argv,kwargs))
        return subprocess.CompletedProcess(argv,0,'','')
    monkeypatch.setattr(connect,'ssh_run',ssh)
    monkeypatch.setattr(connect,'ssh_argv',lambda s:['synthetic-ssh'])
    monkeypatch.setattr(connect,'describe_harness',lambda *a,**kw:{'default_model':'synthetic/model'})
    connect.connect_agent({'token':token,'agent_id':'openclaw:main','name':'remote-test'},environment,
                          lambda _: (sys.executable,()))
    payload=json.loads(seen[0][1]['payload'])
    assert payload['root'].startswith('/synthetic/home/.local/share/atlas-of-threads/connections/')
    assert payload['config']['command']==['/private/native-cli']
    assert '/private/native-cli' not in ' '.join(seen[0][0])
    config=json.loads(Path(HarnessRegistry().get('remote-test').argv[-1]).read_text())
    assert config['host']=='synthetic@host.invalid'
    assert '\\' not in config['remote_command'][1]


class Socket:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def getsockname(self):return ('192.0.2.10',12345)


@pytest.mark.parametrize('stderr,status',[
    ('Permission denied (publickey).','authentication'),
    ('WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!','host_changed'),
    ('python3: command not found','host_setup')])
def test_connection_errors_are_specific_without_private_stderr(monkeypatch,environment,stderr,status):
    monkeypatch.setattr(connect.socket,'getaddrinfo',lambda *a,**k:[])
    monkeypatch.setattr(connect.socket,'create_connection',lambda *a,**k:Socket())
    monkeypatch.setattr(connect,'ssh_run',lambda *a,**k:subprocess.CompletedProcess([],255,'',stderr+' private-token'))
    result=connect.check_remote({'host':'host.invalid','user':'synthetic','platform':'wsl'})
    assert result['status']==status
    assert 'private-token' not in json.dumps(result)
    assert result['help']['source_ip']=='192.0.2.10'
    assert not (connect.connection_root()/'known_hosts').exists()


def test_host_key_requires_separate_explicit_trust(monkeypatch,environment):
    monkeypatch.setattr(connect.socket,'getaddrinfo',lambda *a,**k:[])
    monkeypatch.setattr(connect.socket,'create_connection',lambda *a,**k:Socket())
    monkeypatch.setattr(connect,'ssh_run',lambda *a,**k:subprocess.CompletedProcess([],255,'','Host key verification failed.'))
    monkeypatch.setattr(connect.shutil,'which',lambda _: '/synthetic/ssh-keyscan')
    key='host.invalid ssh-ed25519 '+base64.b64encode(b'synthetic-public-key').decode()+'\n'
    monkeypatch.setattr(connect.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess([],0,key,''))
    result=connect.check_remote({'host':'host.invalid','user':'synthetic'})
    assert result['status']=='verify_host' and result['fingerprints'][0].startswith('SHA256:')
    path=connect.connection_root()/'known_hosts'
    assert not path.exists()
    monkeypatch.setattr(connect,'check_remote',lambda s:{'status':'ready'})
    assert connect.trust_remote(result['token'])['status']=='ready'
    assert path.read_text()==key


def test_firewall_help_is_scoped_and_never_disables_firewalls():
    result=connect.firewall_help({'port':2222,'platform':'wsl'},'192.0.2.10')
    output=json.dumps(result)
    assert '-RemoteAddresses 192.0.2.10' in output
    assert '-LocalPorts 2222' in output and '-Profile Private' in output
    assert 'Undo:' in output and 'NAT' in output
    assert 'DefaultInboundAction Allow' not in output
    assert 'ufw disable' not in output
    assert connect.firewall_help({'port':22,'platform':'linux'},'$(bad)')['source_ip'] is None


def test_new_onboarding_endpoint_rejects_cross_origin_before_discovery(monkeypatch,environment):
    handler=object.__new__(InhabitHandler)
    handler.path='/api/onboarding/discover'
    handler.headers={'Host':'127.0.0.1:7462','Content-Type':'application/json','Origin':'https://untrusted.invalid'}
    handler.store=environment
    replies=[]
    handler._json=lambda code,body:replies.append((code,body))
    monkeypatch.setattr(connect,'local_discovery',lambda:pytest.fail('Must reject before scan'))
    handler.do_POST()
    assert replies[0][0]==400


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX native host inventory")
def test_host_probe_never_returns_unselected_native_fields(monkeypatch,tmp_path):
    monkeypatch.setattr(host_probe,'native_command',lambda name:['fake'] if name=='openclaw' else None)
    monkeypatch.setattr(host_probe.os,'name','posix')
    monkeypatch.setattr(host_probe,'run_json',lambda argv:[{'id':'main','identityName':'Synthetic',
        'workspace':str(tmp_path),'model':'test/model','apiKey':'never-return-this','bindings':['private']}])
    result=host_probe.discover()
    assert result['agents'][0]['ready']
    assert 'never-return-this' not in json.dumps(result)
    assert 'bindings' not in json.dumps(result)


def test_frozen_windows_uses_console_adapter(monkeypatch,tmp_path):
    from thought_archaeology.serve import _packaged_harness_command
    console=tmp_path/'AtlasOfThreadsMCP.exe'
    console.touch()
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'platform','win32')
    monkeypatch.setattr(sys,'executable',str(tmp_path/'AtlasOfThreads.exe'))
    assert _packaged_harness_command('ta-harness-ssh')==(str(console),('adapter','ssh'))


def test_local_discovery_finds_cli_outside_desktop_path(monkeypatch,tmp_path):
    from thought_archaeology.adapters import provider_command as providers
    executable=tmp_path/'.opencode/bin/opencode'
    executable.parent.mkdir(parents=True)
    executable.write_text('synthetic')
    executable.chmod(0o700)
    monkeypatch.setattr(sys,'platform','linux')
    monkeypatch.setattr(Path,'home',lambda:tmp_path)
    monkeypatch.setattr(providers,'_safe_which',lambda name:None)
    assert providers.discover_provider_commands([('opencode',None)])['opencode']==str(executable)
