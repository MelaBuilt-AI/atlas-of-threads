"""Local discovery and explicit SSH onboarding. No subnet scans or model calls."""
import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid

from thought_archaeology.adapters import host_probe
from thought_archaeology.agent_bridge import register_collaborator
from thought_archaeology.harness import HarnessError, HarnessRegistry, HARNESS_NAME, describe_harness
from thought_archaeology.store import _write_private_json_atomic

_pending = {}
_lock = threading.Lock()
_connect_lock = threading.Lock()


def assets():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    return root/'agent-host' if getattr(sys, 'frozen', False) else root/'adapters'


def remember(data):
    token = uuid.uuid4().hex
    with _lock:
        for key in list(_pending):
            if _pending[key]['expires'] < time.monotonic():
                del _pending[key]
        _pending[token] = {**data, 'expires':time.monotonic()+900}
    return token


def pending(token):
    with _lock:
        value = _pending.get(str(token))
        if not value or value['expires'] < time.monotonic():
            raise HarnessError('This connection check expired. Scan again.')
        return value


def public_agents(data):
    return [{k:v for k,v in a.items() if k != 'config'} for a in data['agents']]


def local_discovery():
    data = host_probe.discover()
    token = remember({'kind':'local', 'inventory':data})
    return {'token':token, 'agents':public_agents(data)}


def settings(body):
    host = str(body.get('host') or '').strip()
    user = str(body.get('user') or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.:-]{0,252}', host):
        raise HarnessError('Enter a hostname or IP address, without a username or URL.')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}', user):
        raise HarnessError('Enter the SSH login name on the agent machine.')
    try:
        port = int(22 if body.get('port') in (None, '') else body['port'])
    except (ValueError, TypeError):
        raise HarnessError('SSH port must be a number.') from None
    if not 1 <= port <= 65535:
        raise HarnessError('SSH port must be between 1 and 65535.')
    identity = str(body.get('identity') or '').strip()
    if identity:
        identity = str(Path(identity).expanduser().absolute())
        if not Path(identity).is_file():
            raise HarnessError('The private-key file was not found on this Atlas PC.')
    platform = body.get('platform', 'linux')
    if platform not in {'linux','wsl','macos'}:
        raise HarnessError('Choose Linux, Windows with WSL, or macOS for the agent host.')
    return {'host':host, 'user':user, 'port':port, 'identity':identity, 'platform':platform}


def connection_root():
    root = HarnessRegistry().path.parent/'connections'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def ssh_argv(s):
    ssh = shutil.which('ssh')
    if not ssh:
        raise HarnessError('Install the OpenSSH client on this Atlas PC, then check again.')
    argv = [ssh, '-F', os.devnull, '-p', str(s['port']), '-o','BatchMode=yes',
            '-o','StrictHostKeyChecking=yes', '-o','ConnectTimeout=8',
            '-o','ServerAliveInterval=15', '-o','ServerAliveCountMax=2',
            '-o','UserKnownHostsFile='+str(connection_root()/'known_hosts')]
    if s['identity']:
        argv += ['-i',s['identity'],'-o','IdentitiesOnly=yes']
    return argv


def ssh_run(s, command, *, payload=None, timeout=50):
    return subprocess.run([*ssh_argv(s), '-T', s['user']+'@'+s['host'], shlex.join(command)],
                          input=payload, capture_output=True, text=True, encoding='utf-8',
                          timeout=timeout, check=False)


def firewall_help(s, source=None):
    # Commands contain only validated literal IPs/ports. Never a subnet-wide rule.
    try:
        source = str(ipaddress.ip_address(source)) if source else None
    except ValueError:
        source = None
    port = s['port']
    who = source or '<ATLAS_PC_LAN_IP>'
    rule = 'Atlas-SSH-'+str(port)
    family = 'ipv6' if source and ':' in source else 'ipv4'
    rich = f'rule family="{family}" source address="{who}" port port="{port}" protocol="tcp" accept'
    sections = [{'title':'Only SSH needs to be reachable', 'text':
        'Run host commands on the agent PC. Atlas uses an outbound SSH connection; its web port and the agent Gateway can stay private. A timeout can also mean a sleeping PC, wrong address, VPN or isolated Wi-Fi. These commands are guidance, not changes Atlas has applied.'},
        {'title':'Check the SSH service on the agent host', 'text':
         'Linux / WSL: ss -ltn | head\nUbuntu / Debian, if SSH is not installed: sudo apt install openssh-server\nStart its service: sudo systemctl enable --now ssh\nOther Linux distributions may call it sshd. Use the selected SSH port only if sshd is configured to listen there.'}]
    if s['platform'] == 'macos':
        sections.append({'title':'macOS', 'text':'On the agent Mac, open System Settings → General → Sharing → Remote Login. Allow the intended login user. Review any third-party firewall for inbound SSH from '+who+'.'})
    else:
        sections.append({'title':'Linux firewall — use only the firewall already active', 'text':
            f'Check: sudo ufw status\nAllow: sudo ufw allow from {who} to any port {port} proto tcp comment "Atlas SSH"\nUndo: sudo ufw delete allow from {who} to any port {port} proto tcp\n\nFor firewalld: sudo firewall-cmd --get-active-zones\nUse that zone with a source-specific SSH rule; do not enable a second firewall.'})
    if s['platform'] == 'wsl':
        sections.append({'title':'Windows + WSL networking', 'text':
            'In WSL, check: wslinfo --networking-mode\nMirrored networking can accept LAN connections directly. NAT also requires a port-forward to the current WSL IP; a firewall rule alone will not provide that route. Check the Microsoft networking guide below before changing modes. Restarting WSL interrupts its agents.'})
        sections.append({'title':'Mirrored WSL — Administrator PowerShell on the agent Windows PC', 'text':
            f'Get-NetFirewallHyperVRule -Name "{rule}" -ErrorAction SilentlyContinue\n'
            f'New-NetFirewallHyperVRule -Name "{rule}" -DisplayName "Atlas SSH" -Direction Inbound -VMCreatorId "{{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}}" -Protocol TCP -LocalPorts {port} -RemoteAddresses {who} -Action Allow\n'
            f'Undo: Remove-NetFirewallHyperVRule -Name "{rule}"\n\n'
            'If Windows host policy also blocks the connection, inspect its rules before adding:\n'
            f'New-NetFirewallRule -Name "{rule}" -DisplayName "Atlas SSH" -Direction Inbound -Protocol TCP -LocalPort {port} -RemoteAddress {who} -Profile Private -Action Allow\n'
            f'Undo: Remove-NetFirewallRule -Name "{rule}"\n'
            'Use the Private profile only on your trusted LAN. Keep existing broader rules and managed policy under the host administrator’s control.'})
    if s['platform'] == 'wsl':
        sections.append({'title':'NAT WSL — optional route, Administrator PowerShell on the agent PC', 'text':
            'Use only if WSL reports NAT. Choose an unused Windows listening port (the SSH port entered above). The WSL SSH service may still use port 22. Record the current WSL IPv4 address from wsl -d <Distro> hostname -I; it can change after a WSL restart.\n'
            '$agentLanIp = Read-Host "Agent Windows PC LAN IPv4 address"\n'
            '$agentWslIp = Read-Host "Current WSL IPv4 address"\n'
            '$agentWslSshPort = Read-Host "SSH port inside WSL (usually 22)"\n'
            'netsh interface portproxy show v4tov4\n'
            f'netsh interface portproxy add v4tov4 listenaddress=$agentLanIp listenport={port} connectaddress=$agentWslIp connectport=$agentWslSshPort\n'
            f'Undo: netsh interface portproxy delete v4tov4 listenaddress=$agentLanIp listenport={port}\n'
            f'For this Windows listener, allow only the Atlas PC: New-NetFirewallRule -Name "{rule}" -DisplayName "Atlas SSH" -Direction Inbound -Protocol TCP -LocalPort {port} -RemoteAddress {who} -Profile Private -Action Allow\n'
            f'Undo: Remove-NetFirewallRule -Name "{rule}"\n'
            'If a firewall inside WSL is active, inspect which source address the Windows proxy presents before allowing that source to the internal SSH port. Do not reuse an existing listener or replace its rules.'})
    sections.append({'title':'Verify the host and set up key access', 'text':
        'On Linux / WSL, compare the host fingerprint with: ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub\n'
        'Use your existing SSH key or SSH agent on the Atlas PC. For a new key, run ssh-keygen -t ed25519 there. Add only its .pub line to ~/.ssh/authorized_keys on the agent host (directory mode 700; file mode 600). Keep the private key on the Atlas PC. Test the same host, login, port and key in a terminal first; unlock an encrypted key through your SSH agent.'})
    return {'source_ip':source, 'sections':sections, 'links':[
        {'title':'Microsoft WSL networking', 'url':'https://learn.microsoft.com/en-us/windows/wsl/networking'},
        {'title':'Microsoft Hyper-V firewall', 'url':'https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/hyper-v-firewall'}]}


def check_remote(body):
    s = settings(body)
    source = None
    try:
        for family, kind, proto, _, address in socket.getaddrinfo(s['host'],s['port'],type=socket.SOCK_DGRAM):
            with socket.socket(family,kind,proto) as route:
                route.connect(address)
                source = route.getsockname()[0]
                break
    except OSError:
        pass
    try:
        with socket.create_connection((s['host'],s['port']),timeout=5) as sock:
            source = sock.getsockname()[0]
    except OSError as exc:
        status = 'refused' if isinstance(exc, ConnectionRefusedError) else 'unreachable'
        return {'status':status, 'message':('The host refused this port. Check the SSH service and port.' if status=='refused' else
            'Could not reach this SSH port. Check the address, power, network route and host firewall.'), 'help':firewall_help(s, source)}
    help = firewall_help(s, source)
    try:
        result = ssh_run(s, ['python3','-c',(assets()/'host_probe.py').read_text(encoding='utf-8')], timeout=65)
    except subprocess.TimeoutExpired:
        return {'status':'timeout','message':'SSH or native inventory timed out. Check SSH in a terminal and the native agent setup.', 'help':help}
    detail = result.stderr.lower()
    if result.returncode:
        if 'remote host identification has changed' in detail:
            return {'status':'host_changed','message':'The saved host key changed. Verify the machine independently; Atlas has kept the trusted key.', 'help':help}
        if 'host key verification failed' in detail or 'no ed25519 host key is known' in detail or 'no ecdsa host key is known' in detail or 'no rsa host key is known' in detail:
            scan = shutil.which('ssh-keyscan')
            if not scan:
                raise HarnessError('Install OpenSSH ssh-keyscan to verify this host.')
            keys = subprocess.run([scan,'-T','5','-p',str(s['port']),'-t','ed25519',s['host']],
                capture_output=True,text=True,timeout=8,check=False).stdout
            lines = [line for line in keys.splitlines() if len(line.split())==3 and line.split()[1]=='ssh-ed25519']
            if not lines:
                return {'status':'host_key','message':'Could not obtain an Ed25519 host key. Verify and configure SSH in a terminal.', 'help':help}
            fingerprints = sorted({'SHA256:'+base64.b64encode(hashlib.sha256(base64.b64decode(line.split()[2],validate=True)).digest()).decode().rstrip('=') for line in lines})
            token = remember({'kind':'trust','settings':s,'keys':'\n'.join(lines)+'\n'})
            return {'status':'verify_host','token':token,'fingerprints':fingerprints,
                'message':'Compare this fingerprint with the agent PC before trusting it. Discovery alone does not verify identity.', 'help':help}
        return {'status':'authentication' if 'permission denied' in detail else 'host_setup',
                'message':('SSH reached the host, but key authentication failed. Check the login and key; firewall changes will not fix authentication.' if 'permission denied' in detail else
                'SSH could not run the agent inventory. The host needs a POSIX shell and Python 3.11+, plus its configured native agents. Check the same SSH command in a terminal.'), 'help':help}
    try:
        data = json.loads(result.stdout)
    except ValueError:
        raise HarnessError('The host returned unexpected output. Check SSH startup scripts for extra stdout.') from None
    token = remember({'kind':'remote','settings':s,'inventory':data})
    return {'status':'ready','token':token,'agents':public_agents(data),'help':help,
            'message':'SSH verified. Choose an agent to connect; this installs a private Atlas helper. The first request starts a dedicated conversation on that host.'}


def trust_remote(token):
    p = pending(token)
    if p['kind'] != 'trust':
        raise HarnessError('Check the host fingerprint first.')
    path = connection_root()/'known_hosts'
    with _lock:
        with path.open('a', encoding='utf-8') as stream:
            stream.write(p['keys'])
        path.chmod(0o600)
    return check_remote(p['settings'])


def connect_agent(body, store, adapter_command):
    with _connect_lock:
        return _connect_agent(body, store, adapter_command)


def _connect_agent(body, store, adapter_command):
    p = pending(body.get('token'))
    if p['kind'] not in {'local','remote'}:
        raise HarnessError('Discover agents before connecting.')
    agent = next((a for a in p['inventory']['agents'] if a['id']==body.get('agent_id')),None)
    if not agent or not agent['ready'] or 'config' not in agent:
        raise HarnessError('Choose an available discovered agent.')
    name = str(body.get('name') or '').strip()
    if not HARNESS_NAME.fullmatch(name):
        raise HarnessError('Connection name must use 1–64 letters, numbers, dots, hyphens or underscores.')
    display = str(body.get('display_name') or agent['display_name']).strip()
    if not display or len(display)>100:
        raise HarnessError('Agent display name must have 1–100 characters.')
    registry = HarnessRegistry()
    if name in {spec.name for spec in registry.specs()}:
        raise HarnessError('That connection name already exists. Choose another name or use the existing agent.')
    executable, args = adapter_command('ta-harness-'+('ssh' if p['kind']=='remote' else 'local')) or (None,())
    if not executable:
        raise HarnessError('The packaged agent adapter is unavailable. Reinstall Atlas.')
    uid = uuid.uuid4().hex
    config = {**agent['config'], 'display_name':display}
    directory = connection_root()/uid
    directory.mkdir(mode=0o700)
    config_path = directory/'connection.json'
    if p['kind']=='remote':
        remote = str(PurePosixPath(p['inventory']['home'])/'.local/share/atlas-of-threads/connections'/uid)
        config['state_dir'] = remote+'/state'
        payload = json.dumps({'root':remote,'config':config,'helper':(assets()/'remote_host.py').read_text(encoding='utf-8')})
        code = ('import json,os,sys; from pathlib import Path, PurePosixPath; os.umask(0o077); '
                'd=json.load(sys.stdin); p=Path(d["root"]); p.mkdir(parents=True,exist_ok=False); '
                '(p/"remote_host.py").write_text(d["helper"],encoding="utf-8"); '
                '(p/"config.json").write_text(json.dumps(d["config"]),encoding="utf-8")')
        result = ssh_run(p['settings'], ['python3','-c',code],payload=payload)
        if result.returncode:
            raise HarnessError('Could not install the private connection helper. Check write access to the agent home directory.')
        config = {'ssh_argv':ssh_argv(p['settings']), 'host':p['settings']['user']+'@'+p['settings']['host'],
                  'remote_command':['python3',remote+'/remote_host.py','--config',remote+'/config.json']}
    else:
        config['state_dir'] = str(directory/'state')
    _write_private_json_atomic(config_path,config)
    collaborator = register_collaborator(store, display_name=display,client_family=agent['family'],scopes=['atlas:read'])
    spec = registry.register(name,executable,args=(*args,'--config',str(config_path)),
        collaborator_id=collaborator.id,agent_name=display,session_only=True,model=agent['model'])
    try:
        description = describe_harness(spec, timeout=35)
        registry.record_model(name, description.get('default_model') or agent['model'],
                              cli_version=description.get('cli_version'))
    except HarnessError:
        registry.remove(name)
        raise HarnessError('The agent did not pass its connection check. Registration was rolled back; repair its native setup and try again.') from None
    return {'ok':True, 'name':spec.name}
