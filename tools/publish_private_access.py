"""Finish persistent, owner-only HTTPS access once Tailscale is signed in."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


def command(*arguments):
    return subprocess.run(['tailscale', *arguments], capture_output=True, text=True, timeout=20)


def main():
    result = command('status', '--json')
    status = json.loads(result.stdout or '{}')
    if status.get('BackendState') != 'Running':
        print('Private access awaits Tailscale sign-in:', status.get('AuthURL') or 'run tailscale up')
        return 0
    identity = status.get('Self') or {}
    user = (status.get('User') or {}).get(str(identity.get('UserID')), {})
    owner = user.get('LoginName')
    hostname = identity.get('DNSName', '').rstrip('.')
    if not owner or not hostname:
        raise RuntimeError('Tailscale has not supplied the host owner and private DNS name yet')
    policy_path = Path(os.environ.get('LABUI_ACCESS_POLICY', str(Path.home()/'.config/labui/access.json')))
    policy = {'owner_login': owner, 'url': 'https://' + hostname}
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    if not policy_path.exists() or json.loads(policy_path.read_text()) != policy:
        with tempfile.NamedTemporaryFile(mode='w', dir=policy_path.parent, delete=False) as temporary:
            json.dump(policy, temporary)
            temporary.write('\n')
        os.chmod(temporary.name, 0o600)
        Path(temporary.name).replace(policy_path)
    port = os.environ.get('LABUI_PORT', '8770')
    target = f'http://127.0.0.1:{port}'
    current = command('serve', 'status', '--json')
    configuration = json.loads(current.stdout or '{}') if current.returncode == 0 else {}
    handler = configuration.get('Web', {}).get(hostname + ':443', {}).get('Handlers', {}).get('/', {})
    if handler.get('Proxy') == target:
        print('Private LabUI URL:', policy['url'])
        return 0
    served = command('serve', '--bg', '--yes', target)
    print(served.stdout.strip())
    if served.returncode:
        print(served.stderr.strip())
        raise RuntimeError('Tailscale HTTPS setup still needs the account-owner action shown above')
    print('Private LabUI URL:', policy['url'])
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        for output in (exc.stdout, exc.stderr):
            if output:
                print(output.decode() if isinstance(output, bytes) else output)
        raise SystemExit('Tailscale setup is waiting for account authorization; inspect the link above.')
