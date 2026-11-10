"""Resume the embedding build, then promote it with a short service outage.

Run under the target embedding environment, with the existing app configuration
file passed explicitly. Only derived vectors change. Failed cutovers restore the
previous index, memory database and configuration before resuming the importer.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.rebuild_embeddings import stage, activate
from retrieval.index_identity import profile, read_profile


def service(action, name):
    subprocess.run(['systemctl', '--user', action, name], check=True, timeout=250)


def is_active(name):
    return subprocess.run(['systemctl', '--user', 'is-active', '--quiet', name]).returncode == 0


def snapshot(source, destination):
    with sqlite3.connect(source, timeout=30) as original, sqlite3.connect(destination, timeout=30) as backup:
        original.backup(backup)


def replace_config(path, content):
    temporary = path.with_suffix('.upgrade-tmp')
    temporary.write_bytes(content)
    temporary.chmod(0o600)
    temporary.replace(path)


def target_config(content):
    expected = profile()
    updates = {
        'RAG_EMBED_PROVIDER': expected['provider'],
        'RAG_EMBED_MODEL': expected['model'],
        'RAG_EMBED_DIM': str(expected['dimensions']),
        'RAG_EMBED_REVISION': expected['revision'],
        'RAG_EMBED_BASE_URL': os.environ['RAG_EMBED_BASE_URL'],
        'RAG_EMBED_QUERY_INSTRUCTION': expected['query_instruction'],
    }
    text = content.decode()
    for key, value in updates.items():
        if '\n' in value or '"' in value or '$' in value or '`' in value or '\\' in value:
            raise ValueError('Unsafe environment value in target model configuration')
        line = key + '="' + value + '"'
        text, replaced = re.subn(r'^' + re.escape(key) + r'=.*$', lambda _: line, text, flags=re.M)
        if not replaced:
            text = text.rstrip('\n') + '\n' + line + '\n'
    return text.encode()


def wait_ready(base_url, timeout=240):
    session = requests.Session()
    session.trust_env = False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = session.get(base_url + '/api/ready', timeout=10)
            if result.status_code == 200:
                status = session.get(base_url + '/api/rag/status', timeout=15).json()
                if (status.get('embeddings') and status.get('reranker_ready')
                        and status.get('embed_model_name') == profile()['model']
                        and status.get('embed_dim') == profile()['dimensions']
                        and status.get('embedding_provider') == profile()['provider']):
                    return status
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2)
    raise RuntimeError('The upgraded application did not become healthy with the target models')


def validate_search(source, base_url):
    """Exercise the new live vector space and ranking path against a real paper."""
    with sqlite3.connect(source) as conn:
        row = conn.execute('''SELECT p.paper_id,p.title FROM papers p JOIN chunks c USING(paper_id)
            GROUP BY p.paper_id ORDER BY count(*),p.paper_id LIMIT 1''').fetchone()
    if row is None:
        return
    session = requests.Session()
    session.trust_env = False
    response = session.post(base_url + '/api/rag/search',
                            json={'query':row[1], 'selected_paper_ids':[row[0]], 'top_k':1}, timeout=240)
    response.raise_for_status()
    results = response.json().get('results')
    if not results or any(result.get('paper_id') != row[0] for result in results):
        raise RuntimeError('The upgraded vector search failed its real-paper scope check')


def save_state(staged, **values):
    path = staged.parent / 'cutover.json'
    current = json.loads(path.read_text()) if path.exists() else {}
    current.update(values)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(current, indent=2))
    temporary.replace(path)


def promote(source, staged, config_path, base_url):
    importer_running = is_active('labui-library-import.service')
    original_config = config_path.read_bytes()
    memory = source.parent / 'memory.db'
    backup_dir = staged.parent / ('cutover-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup_dir.mkdir(mode=0o700)
    (backup_dir / 'labui.env').write_bytes(original_config)
    (backup_dir / 'labui.env').chmod(0o600)
    save_state(staged, phase='pausing', backup_dir=str(backup_dir), importer_running=importer_running)
    stopped = False
    try:
        service('stop', 'labui-library-import.service')
        stopped = True
        service('stop', 'labui.service')
        # The stopped app's cgroup contains every ingestion subprocess. A final
        # snapshot catches PDFs added while the long build ran with live search.
        stage(source, staged)
        # Preserve settings edited while the long staging snapshot was built.
        original_config = config_path.read_bytes()
        new_config = target_config(original_config)
        (backup_dir / 'labui.env').write_bytes(original_config)
        if memory.exists():
            snapshot(memory, backup_dir / 'memory.db')
        snapshot(source, backup_dir / 'rag.db')
        save_state(staged, phase='cutover')
        activate(source, staged)
        replace_config(config_path, new_config)
        service('start', 'labui.service')
        status = wait_ready(base_url)
        validate_search(source, base_url)
        save_state(staged, phase='active', papers=status.get('papers'), chunks=status.get('chunks'))
        print(f"GPU embedding upgrade active: {status.get('papers')} papers, {status.get('chunks')} chunks", flush=True)
    except BaseException:
        if stopped:
            service('stop', 'labui.service')
            if (backup_dir / 'rag.db').exists():
                snapshot(backup_dir / 'rag.db', source)
            if (backup_dir / 'memory.db').exists():
                snapshot(backup_dir / 'memory.db', memory)
            replace_config(config_path, original_config)
            service('start', 'labui.service')
        save_state(staged, phase='rolled_back')
        progress = staged.parent / 'status.json'
        state = json.loads(progress.read_text()) if progress.exists() else {}
        state.update(running=False, phase='rolled_back')
        progress.write_text(json.dumps(state))
        raise
    finally:
        if importer_running:
            service('start', 'labui-library-import.service')


def recover_interrupted(source, staged, config_path):
    path = staged.parent / 'cutover.json'
    if not path.exists():
        return
    state = json.loads(path.read_text())
    if state['phase'] not in {'pausing', 'cutover'}:
        return
    # No app was restarted before the active checkpoint. Recover an interrupted
    # offline cutover before attempting any further build or model probes.
    backup = Path(state['backup_dir'])
    service('stop', 'labui-library-import.service')
    service('stop', 'labui.service')
    for name in ('rag.db', 'memory.db'):
        if (backup / name).exists():
            snapshot(backup / name, source if name == 'rag.db' else source.parent / name)
    replace_config(config_path, (backup / 'labui.env').read_bytes())
    service('start', 'labui.service')
    if state.get('importer_running'):
        service('start', 'labui-library-import.service')
    save_state(staged, phase='rolled_back')


def install_service(args):
    root = Path(__file__).resolve().parents[1]
    expected = profile()
    values = {'RAG_EMBED_PROVIDER': expected['provider'],
              'RAG_EMBED_MODEL': expected['model'], 'RAG_EMBED_DIM': str(expected['dimensions']),
              'RAG_EMBED_REVISION': expected['revision'],
              'RAG_EMBED_BASE_URL': os.environ['RAG_EMBED_BASE_URL'],
              'RAG_EMBED_QUERY_INSTRUCTION': expected['query_instruction']}
    def quote(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
    command = ['/usr/bin/env', *(key + '=' + value for key, value in values.items()),
               sys.executable, str(Path(__file__).resolve()), '--source-db', str(args.source_db.resolve()),
               '--stage-db', str(args.stage_db.resolve()), '--config', str(args.config.resolve()),
               '--app-url', args.app_url]
    unit = f'''[Unit]
Description=Build and activate LabUI GPU embeddings safely
Wants=labui.service
After=labui.service
StartLimitIntervalSec=0

[Service]
Type=simple
WorkingDirectory={root}
EnvironmentFile={args.config.resolve()}
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/systemd-inhibit --what=sleep --mode=block --who=LabUI "--why=Upgrading paper search" {' '.join(quote(part) for part in command)}
Restart=on-failure
RestartSec=120
RemainAfterExit=yes
TimeoutStopSec=300
KillMode=mixed
UMask=0077

[Install]
WantedBy=default.target
'''
    path = Path.home() / '.config/systemd/user/labui-embedding-upgrade.service'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix('.service.bak.' + str(time.time_ns())))
    path.write_text(unit)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', path.name], check=True)
    print(f'Installed resumable embedding upgrade: {path}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-db', type=Path, required=True)
    parser.add_argument('--stage-db', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--app-url', default='http://127.0.0.1:8770')
    parser.add_argument('--install-service', action='store_true')
    args = parser.parse_args()
    if args.install_service:
        install_service(args)
        return
    args.stage_db.parent.mkdir(parents=True, exist_ok=True)
    with (args.stage_db.parent / 'upgrade.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        recover_interrupted(args.source_db, args.stage_db, args.config)
        with sqlite3.connect(args.source_db) as conn:
            if read_profile(conn) == profile():
                print('Target embedding index is already active; no rebuild needed', flush=True)
                return
        stage(args.source_db, args.stage_db)
        # Fail before stopping the application if the remote model is unavailable.
        from retrieval.embed import load_embed_model
        from retrieval.rerank import load_reranker
        load_embed_model()
        load_reranker()
        promote(args.source_db, args.stage_db, args.config, args.app_url)


if __name__ == '__main__':
    def interrupted(*_):
        raise InterruptedError('Embedding upgrade interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    main()
