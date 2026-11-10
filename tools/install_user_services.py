"""Install user services for the current checkout without touching its data."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path


def unit_text(root: Path, config: Path, adapter: bool) -> str:
    python = root/'submission_strategy/.venv/bin/python'
    if adapter:
        description = 'LabUI LM Studio model adapter'
        ordering = ''
        command = f'"{python}" "{root}/tools/lm_studio_proxy.py" --port ${{LABUI_LM_PROXY_PORT}}'
        ready = ''
    else:
        description = 'LabUI research assistant'
        ordering = 'Wants=labui-model.service\nAfter=labui-model.service\n'
        command = f'/usr/bin/systemd-inhibit --what=sleep --mode=block --who=LabUI "--why=Serving LabUI on this PC" "{root}/start-lm-studio.sh" --app-only'
        ready = f'ExecStartPost="{python}" "{root}/tools/wait_ready.py" --url http://127.0.0.1:${{LABUI_PORT}}/api/ready --timeout 180\n'
    return f'''[Unit]
Description={description}
{ordering}StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory={root}
EnvironmentFile={config}
Environment=PYTHONUNBUFFERED=1
Environment=LABUI_PORT=8770 LABUI_LM_PROXY_PORT=11435
Environment="LABUI_ACCESS_POLICY={config.parent}/access.json"
ExecStart={command}
{ready}Restart=always
RestartSec=5
TimeoutStartSec=200
TimeoutStopSec=90
KillMode=control-group
UMask=0077

[Install]
WantedBy=default.target
'''


def main():
    root = Path(__file__).resolve().parents[1]
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))/'labui/labui.env'
    if not config.exists():
        raise SystemExit(f'Create {config} from deploy/labui.env.example first.')
    directory = Path.home()/'.config/systemd/user'
    directory.mkdir(parents=True, exist_ok=True)
    for adapter in (True, False):
        path = directory/('labui-model.service' if adapter else 'labui.service')
        content = unit_text(root, config, adapter)
        if path.exists() and path.read_text() != content:
            shutil.copy2(path, str(path)+'.bak.'+str(int(time.time())))
        path.write_text(content)
        print('Installed:', path)
    access = directory/'labui-private-access.service'
    access.write_text(f'''[Unit]
Description=Publish LabUI privately after Tailscale sign-in
After=labui.service

[Service]
Type=oneshot
EnvironmentFile={config}
Environment="LABUI_ACCESS_POLICY={config.parent}/access.json"
ExecStart="{root}/submission_strategy/.venv/bin/python" "{root}/tools/publish_private_access.py"
TimeoutStartSec=40
UMask=0077
''')
    timer = directory/'labui-private-access.timer'
    timer.write_text('''[Unit]
Description=Finish LabUI private access when the host joins Tailscale

[Timer]
OnBootSec=30
OnUnitInactiveSec=60
Unit=labui-private-access.service

[Install]
WantedBy=timers.target
''')
    subprocess.run(['systemd-analyze', '--user', 'verify', str(directory/'labui.service'), str(directory/'labui-model.service'), str(access), str(timer)], check=True)
    subprocess.run(['systemctl','--user','daemon-reload'], check=True)
    subprocess.run(['systemctl','--user','enable','labui-model.service','labui.service','labui-private-access.timer'], check=True)
    print('Services enabled. Start them with: systemctl --user start labui.service')


if __name__ == '__main__':
    main()
