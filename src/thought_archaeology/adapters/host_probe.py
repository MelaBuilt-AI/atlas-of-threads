"""Read-only native-agent inventory; also sent over SSH as standalone Python.

Only selected public model/identity fields leave the host. No model is called.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys


def native_command(name):
    override = os.environ.get('TA_' + name.upper() + '_BIN')
    found = override or shutil.which(name)
    if found and Path(found).is_file():
        return [found]
    for folder in ['.local/bin', '.npm-global/bin', '.hermes/node/bin']:
        path = Path.home() / folder / name
        if path.is_file():
            return [str(path)]
    if name == 'openclaw':
        node = Path.home()/'.hermes/node/bin/node'
        entry = Path.home()/'.hermes/node/lib/node_modules/openclaw/dist/index.js'
        if node.is_file() and entry.is_file():
            return [str(node), str(entry)]
    return None


def run_json(argv):
    p = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8',
                       timeout=20, check=True, env={**os.environ, 'NO_COLOR': '1'})
    for i, char in enumerate(p.stdout):
        if char in '[{':
            try:
                return json.loads(p.stdout[i:])
            except ValueError:
                pass
    raise ValueError('No public JSON result')


def discover():
    agents = []
    for family in ['hermes', 'openclaw']:
        command = native_command(family)
        if not command:
            continue
        item = {'id': family, 'family': family, 'display_name': family.title(),
                'model': None, 'ready': False}
        if os.name == 'nt':
            item['detail'] = 'Detected on Windows. This session adapter requires Linux, macOS or WSL.'
            agents.append(item)
            continue
        try:
            if family == 'hermes':
                home = Path(os.environ.get('HERMES_HOME', str(Path.home()/'.hermes')))
                roots = [home/'hermes-agent', Path(command[0]).resolve().parent]
                root = next((p for p in roots if (p/'venv/bin/python').is_file()), None)
                if root is None:
                    raise ValueError('Hermes runtime environment not found')
                python = str(root/'venv/bin/python')
                # Use Hermes's installed YAML reader, never print the config.
                code = ('import yaml,json,sys; from pathlib import Path; '
                        'd=yaml.safe_load(Path(sys.argv[1]).read_text()) or {}; '
                        'm=d.get("model",{}); '
                        'print(json.dumps({"model":m if isinstance(m,str) else m.get("default")}))')
                data = run_json([python, '-c', code, str(home/'config.yaml')])
                config = {'provider':family, 'display_name':'Hermes', 'model':data['model'],
                          'command':command, 'python':python, 'runtime_root':str(root),
                          'state_db':str(home/'state.db')}
                item.update(model=data['model'], ready=bool(data['model']), config=config,
                            detail='Existing Hermes account and native persona; dedicated Atlas conversation.')
                agents.append(item)
            else:
                entries = run_json([*command, 'agents', 'list', '--json'])
                for entry in entries[:32]:
                    workspace = Path(entry['workspace']).expanduser()
                    model = entry.get('model')
                    name = entry.get('identityName') or entry.get('name') or entry['id']
                    config = {'provider':family, 'display_name':name, 'model':model,
                              'command':command, 'agent_id':entry['id'],
                              'context_files':[str(workspace/n) for n in ['IDENTITY.md','SOUL.md','USER.md'] if (workspace/n).is_file()]}
                    agents.append({'id':'openclaw:'+entry['id'], 'family':family,
                                   'display_name':name, 'model':model, 'ready':bool(model),
                                   'detail':'Existing OpenClaw agent; dedicated Atlas conversation. Identity, soul and user context stay on this host.',
                                   'config':config})
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            item['detail'] = 'Installed, but native setup could not be read. Finish agent setup in its own CLI, then scan again.'
            agents.append(item)
    return {'agents':agents, 'platform':sys.platform, 'home':str(Path.home())}


if __name__ == '__main__':
    print(json.dumps(discover(), ensure_ascii=True))
