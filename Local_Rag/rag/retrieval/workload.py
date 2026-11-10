"""Let the bulk vector rebuild yield while users rerank search results.

Advisory file locks work across the web app and migration processes. The OS
releases them after a crash, so abandoned markers cannot stall the rebuild.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import time
from uuid import uuid4


def activity_directory():
    status = os.environ.get('RAG_EMBED_MIGRATION_STATUS')
    return Path(status).parent / 'interactive' if status else None


@contextmanager
def interactive_request():
    directory = activity_directory()
    if directory is None:
        yield
        return
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / (uuid4().hex + '.tmp')
    published = temporary.with_suffix('.lease')
    with temporary.open('x') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        temporary.replace(published)
        try:
            yield
        finally:
            published.unlink(missing_ok=True)


def interactive_active():
    directory = activity_directory()
    if directory is None or not directory.exists():
        return False
    active = False
    for path in directory.glob('*.lease'):
        try:
            with path.open('r') as lease:
                try:
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    active = True
                else:
                    path.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
    return active


def wait_for_interactive():
    while interactive_active():
        time.sleep(1)
