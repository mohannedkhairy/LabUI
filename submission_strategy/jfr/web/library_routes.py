"""Browse indexed PDFs and organize them without moving source files."""
import sqlite3
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from jfr.config import get_settings
from jfr.db import get_conn

router = APIRouter()

class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class MembershipIn(BaseModel):
    paper_ids: list[str] = Field(max_length=1000)
    folder_id: str | None = None


def _conn():
    return get_conn(get_settings().db_path)


def _papers():
    from config import DB_PATH
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        columns = {r[1] for r in conn.execute('PRAGMA table_info(papers)')}
        fields = [x for x in ['paper_id', 'title', 'authors', 'year', 'doi', 'journal', 'abstract', 'source_pdf'] if x in columns]
        if 'paper_id' not in fields:
            return []
        return [dict(r) for r in conn.execute('SELECT '+','.join(fields)+' FROM papers ORDER BY title COLLATE NOCASE, paper_id')]
    finally:
        conn.close()


@router.get('/library')
def library_list(q: str = '', folder: str = '', page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100)):
    papers = _papers()
    conn = _conn()
    try:
        membership = {r['paper_id']: r['folder_id'] for r in conn.execute('SELECT * FROM library_membership')}
        reviews = {r['paper_id']: dict(r) for r in conn.execute('SELECT paper_id, COUNT(*) AS note_count FROM review_note GROUP BY paper_id')}
        folders = [dict(r) for r in conn.execute('SELECT * FROM library_folder ORDER BY name COLLATE NOCASE')]
    finally:
        conn.close()
    valid_ids = {p['paper_id'] for p in papers}
    for f in folders:
        f['count'] = sum(pid in valid_ids and fid == f['id'] for pid, fid in membership.items())
    total_all = len(papers)
    unfiled = sum(p['paper_id'] not in membership for p in papers)
    query = q.casefold().strip()
    papers = [p for p in papers if (not folder or (folder == 'unfiled' and p['paper_id'] not in membership) or membership.get(p['paper_id']) == folder) and (not query or query in ' '.join(str(p.get(k) or '') for k in ['title','authors','year','doi','journal']).casefold())]
    total = len(papers)
    for p in papers:
        p['folder_id'] = membership.get(p['paper_id'])
        p['note_count'] = reviews.get(p['paper_id'], {}).get('note_count', 0)
        p['has_pdf'] = bool(p.pop('source_pdf', None))
    return {'papers': papers[(page-1)*page_size:page*page_size], 'total': total, 'total_all': total_all, 'unfiled': unfiled, 'folders': folders, 'page': page, 'page_size': page_size}


@router.post('/library/folders', status_code=201)
def create_folder(body: FolderIn):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, 'Enter a folder name')
    conn = _conn()
    try:
        fid = str(uuid4())
        conn.execute('INSERT INTO library_folder(id,name) VALUES(?,?)', (fid, name))
        conn.commit()
        return {'id': fid, 'name': name}
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'A folder with this name already exists')
    finally:
        conn.close()


@router.delete('/library/folders/{folder_id}')
def delete_folder(folder_id: str):
    conn = _conn()
    try:
        conn.execute('DELETE FROM library_membership WHERE folder_id=?', (folder_id,))
        conn.execute('DELETE FROM library_folder WHERE id=?', (folder_id,))
        conn.commit()
        return {'ok': True}
    finally:
        conn.close()


@router.put('/library/membership')
def assign_folder(body: MembershipIn):
    valid_ids = {p['paper_id'] for p in _papers()}
    if any(pid not in valid_ids for pid in body.paper_ids):
        raise HTTPException(404, 'Paper not found')
    conn = _conn()
    try:
        if body.folder_id and not conn.execute('SELECT 1 FROM library_folder WHERE id=?', (body.folder_id,)).fetchone():
            raise HTTPException(404, 'Folder not found')
        for pid in body.paper_ids:
            if body.folder_id:
                conn.execute('INSERT INTO library_membership(paper_id,folder_id) VALUES(?,?) ON CONFLICT(paper_id) DO UPDATE SET folder_id=excluded.folder_id', (pid, body.folder_id))
            else:
                conn.execute('DELETE FROM library_membership WHERE paper_id=?', (pid,))
        conn.commit()
        return {'ok': True}
    finally:
        conn.close()
