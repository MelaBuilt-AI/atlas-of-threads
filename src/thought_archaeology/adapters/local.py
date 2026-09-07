"""Session-preserving local Hermes/OpenClaw adapter using the native host helper."""
import argparse
import json
import os
from pathlib import Path
import sys

from thought_archaeology.adapters.remote_host import handle
from thought_archaeology.adapters.ssh import prompt
from thought_archaeology.store import _write_private_json_atomic


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('operation', choices=['describe','continue','discuss'])
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding='utf-8'))
        request = {'operation':args.operation}
        if args.operation != 'describe':
            envelope = json.load(sys.stdin)
            if envelope.get('operation') != args.operation:
                raise ValueError('Operation mismatch')
            request.update(prompt=prompt(envelope), request_id=envelope['request']['id'])
        result = handle(config, request)
        if args.operation == "describe":
            result["connected_agent"]["memory_owner"] = "local_native_client"
        state = os.environ.get('TA_HARNESS_SESSION_STATE')
        if state and args.operation != 'describe':
            path = Path(state)
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_private_json_atomic(path, {'version':1, 'remote_session_id':result['remote_session_id'],
                'memory_owner':'local_native_client', 'agent_name':os.environ.get('TA_HARNESS_AGENT_NAME')})
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except Exception:
        print('Native agent connection failed; check its setup and private Atlas connection receipt.', file=sys.stderr)
        return 1
