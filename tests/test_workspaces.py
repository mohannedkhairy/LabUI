"""Workspace ownership, focused overviews, and cross-space navigation."""
import sqlite3
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# The launcher exposes the sibling RAG package on PYTHONPATH as well.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag' / 'rag'))

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from jfr.db.schema import init_db
from jfr.web import workspace_routes
from jfr.web.templating import make_templates
from jfr.web.workspaces import (
    WORKSPACES,
    active_navigation,
    workspace_context,
    workspace_for_path,
)


def request(path, query=''):
    return Request({'type':'http','scheme':'http','method':'GET','path':path,
                    'query_string':query.encode(), 'headers':[], 'server':('testserver',80)})


class Nav(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.links = []
    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == 'nav' and attr.get('id') == 'workspace-navigation':
            self.inside = True
        if self.inside and tag == 'a':
            self.links.append(attr)
    def handle_endtag(self, tag):
        if tag == 'nav':
            self.inside = False


class WorkspaceNavigationTests(unittest.TestCase):
    def test_existing_deep_links_choose_the_correct_workspace(self):
        examples = {
            'lab':['/plan','/tasks/task-1','/experiments/exp-1/edit','/schedule','/spaces/lab','/equipment','/equipment/one/edit'],
            'research':['/library','/review','/research/paper/paper-id/view','/research/chat',
                        '/research/scout','/research/graph','/lab','/spaces/research'],
            'writing':['/write/project-id','/manuscripts/one/edit','/recommend','/submissions/one',
                       '/publications','/journals','/research/style','/research/phrasebank','/spaces/writing'],
        }
        for space, paths in examples.items():
            for path in paths:
                with self.subTest(path=path):
                    self.assertEqual(workspace_for_path(path, 'research')['id'], space)

    def test_path_prefixes_have_boundaries(self):
        self.assertEqual(workspace_for_path('/writeup', 'lab')['id'], 'lab')
        self.assertEqual(workspace_for_path('/research/styles', 'lab')['id'], 'research')

    def test_planner_filters_only_highlight_one_navigation_item(self):
        for query, label in [('view=board&kind=task','Tasks'),('kind=experiment&view=list','Experiments'),('view=week','Calendar'),('','Calendar')]:
            req = request('/plan', query)
            links = [link['label'] for link in WORKSPACES['lab']['nav'] if active_navigation(req, link)]
            self.assertEqual(links, [label])

    def test_command_palette_keeps_tools_from_every_workspace(self):
        commands = workspace_context(request('/plan'))['workspace_commands']
        hrefs = {command[1] for command in commands}
        for href in ['/write','/research/chat','/library','/submissions','/plan?view=board&kind=task','/spaces/research','/equipment']:
            self.assertIn(href, hrefs)
        self.assertEqual({command[2] for command in commands}, {'Lab','Research & AI','Writing & Publishing'})


class WorkspaceRoutesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / 'jfr.sqlite'
        self.conn = init_db(self.db)
        self.addCleanup(self.conn.close)
        self.paths = {name:self.root/(name+'.sqlite') for name in ['papers','memory','writing']}
        patches = [patch.object(workspace_routes,'get_settings',return_value=SimpleNamespace(db_path=self.db)),
                   patch.object(workspace_routes,'research_paths',return_value=self.paths)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(workspace_routes.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def nav(self, html):
        parser = Nav()
        parser.feed(html)
        return parser.links

    def test_default_home_and_preferred_workspace_are_safe_redirects(self):
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.headers['location'],'/spaces/lab')
        self.client.get('/spaces/writing')
        self.assertEqual(self.client.get('/',follow_redirects=False).headers['location'],'/spaces/writing')
        self.client.cookies.set('labui_workspace','https://other.example')
        self.assertEqual(self.client.get('/',follow_redirects=False).headers['location'],'/spaces/lab')
        self.assertEqual(self.client.get('/spaces/not-real').status_code,404)

    def test_empty_installation_renders_three_distinct_dashboards(self):
        for space in WORKSPACES:
            response = self.client.get('/spaces/'+space)
            self.assertEqual(response.status_code,200,response.text)
            self.assertIn(f'data-workspace="{space}"',response.text)
            self.assertIn(f'data-space-overview="{space}"',response.text)
            self.assertIn('Switch workspace',response.text)
            hrefs = {link['href'] for link in self.nav(response.text)}
            self.assertEqual(hrefs,{entry['href'] for entry in WORKSPACES[space]['nav']})
            self.assertEqual(sum('aria-current' in entry for entry in self.nav(response.text)),1)
            self.assertEqual('id="scout-panel"' in response.text,space=='research')
            self.assertEqual('id="active-model-label"' in response.text,space=='research')
        self.assertFalse(any(path.exists() for path in self.paths.values()),'An overview created or changed an optional database')

    def seed_lab(self):
        self.conn.execute("INSERT INTO manuscript(id,title,abstract,principal_claim,created_at,updated_at) VALUES('m','Linked manuscript','abstract','claim','2026-01-01','2026-01-01')")
        self.conn.executemany('INSERT INTO task(id,title,status,priority,due_date,manuscript_id) VALUES(?,?,?,?,?,?)',[
            ('overdue','Prepare saline solutions','todo','high','2020-01-01','m'),
            ('undated','Calibrate the instrument','todo','normal','','m'),
            ('closed','Finished task','done','normal','2020-01-01','m')])
        self.conn.executemany('INSERT INTO experiment(id,name,status,equipment,manuscript_id,results_md) VALUES(?,?,?,?,?,?)',[
            ('planned','Nanobubble preparation','planned','NTA','m',''),
            ('running','Stability measurements','in_progress','Zetasizer','m',''),
            ('done','Completed experiment','done','NTA','m','Results recorded')])
        self.conn.commit()

    def test_lab_lists_only_open_tasks_and_preparation_with_real_counts(self):
        self.seed_lab()
        before = self.conn.total_changes
        data = workspace_routes.lab_overview(self.db)
        self.assertEqual((data['open_tasks'],data['overdue'],data['planned'],data['running']),(2,1,1,1))
        self.assertEqual(data['tasks'][0]['id'],'overdue')
        self.assertEqual(len(data['preparation']),2)
        self.assertEqual(data['results'][0]['name'],'Completed experiment')
        html = self.client.get('/spaces/lab').text
        self.assertIn('Prepare saline solutions',html)
        self.assertIn('/plan?open=experiment:planned',html)
        self.assertIn('Linked manuscript',html)
        self.assertNotIn('Finished task',html)
        self.assertEqual(self.conn.total_changes,before)

    def seed_research(self):
        with sqlite3.connect(self.paths['papers']) as conn:
            conn.execute('CREATE TABLE papers(paper_id TEXT,title TEXT,authors TEXT,year INTEGER)')
            conn.executemany('INSERT INTO papers VALUES(?,?,?,?)',[('one','Saline nanobubble stability','Cai',2024),('two','Wettability experiments','Khairy',2025)])
        with sqlite3.connect(self.paths['memory']) as conn:
            conn.executescript('''CREATE TABLE sessions(session_id TEXT,title TEXT,agent_id TEXT,turn_count INTEGER,updated_at REAL);
                CREATE TABLE memories(content TEXT,memory_type TEXT,created_at REAL);''')
            conn.execute("INSERT INTO sessions VALUES('session-1','Salinity question','evidence',4,1)")
            conn.execute("INSERT INTO memories VALUES('An existing finding','finding',1)")

    def test_research_uses_existing_agents_conversations_and_memories(self):
        self.seed_research()
        data = workspace_routes.research_overview(self.paths)
        self.assertEqual((data['paper_count'],data['session_count'],data['memory_count']),(2,1,1))
        self.assertEqual(data['sessions'][0]['href'],'/research/chat?session=session-1')
        html = self.client.get('/spaces/research').text
        self.assertIn('An existing finding',html)
        self.assertIn('/research/chat?agent=evidence',html)
        self.assertIn('Salinity question',html)
        self.assertNotIn('Experiment preparation',html)

    def test_writing_reads_projects_and_keeps_publication_workflow_links(self):
        self.seed_lab()
        with sqlite3.connect(self.paths['writing']) as conn:
            conn.executescript('''CREATE TABLE writing_projects(id TEXT,title TEXT,updated_at REAL);
                CREATE TABLE writing_files(project_id TEXT);''')
            conn.execute("INSERT INTO writing_projects VALUES('wp-example','A nanobubble manuscript',1)")
            conn.executemany('INSERT INTO writing_files VALUES(?)',[('wp-example',),('wp-example',)])
        self.conn.execute("INSERT INTO journal(id,name,publisher,publisher_family) VALUES('j','Surface Science','Publisher','publisher')")
        self.conn.execute("INSERT INTO submission(id,manuscript_id,journal_id,current_state,created_at,updated_at) VALUES('s','m','j','under_review','2026-01-01','2026-01-01')")
        self.conn.commit()
        html = self.client.get('/spaces/writing').text
        self.assertIn('/write/wp-example',html)
        self.assertIn('2 sections',html)
        self.assertIn('/submissions/s',html)
        self.assertIn('Surface Science',html)
        self.assertNotIn('id="scout-panel"',html)

    def test_global_search_finds_saved_items_across_all_spaces(self):
        self.seed_lab()
        self.seed_research()
        with sqlite3.connect(self.paths['writing']) as conn:
            conn.execute('CREATE TABLE writing_projects(id TEXT,title TEXT,updated_at REAL)')
            conn.execute("INSERT INTO writing_projects VALUES('wp-one','Saline surfaces draft',1)")
        results = self.client.get('/api/workspaces/search?q=saline').json()['items']
        self.assertEqual({item['space'] for item in results},{'lab','research','writing'})
        self.assertIn('/plan?open=task:overdue',{item['href'] for item in results})
        self.assertIn('/write/wp-one',{item['href'] for item in results})
        self.assertIn('/research/paper/one/view',{item['href'] for item in results})
        experiment = self.client.get('/api/workspaces/search?q=Nanobubble%20preparation').json()['items']
        self.assertEqual(experiment[0]['href'],'/plan?open=experiment:planned')
        self.assertEqual(self.client.get('/api/workspaces/search?q=x').status_code,422)
        self.assertEqual(len(self.client.get('/api/workspaces/search?q=saline&limit=1').json()['items']),1)

    def test_search_treats_wildcards_as_text_and_accepts_citation_key_prefix(self):
        self.seed_lab()
        self.seed_research()
        with sqlite3.connect(self.paths['papers']) as conn:
            conn.execute('CREATE TABLE citation_catalog(paper_id TEXT,citation_key TEXT)')
            conn.execute("INSERT INTO citation_catalog VALUES('one','cai2024')")
        self.assertEqual(self.client.get('/api/workspaces/search?q=cai2024').json()['items'][0]['href'],'/research/paper/one/view')
        self.assertEqual(self.client.get('/api/workspaces/search',params={'q':'%%'}).json()['items'],[])

    def test_unavailable_overview_keeps_workspace_navigation_visible(self):
        with patch.object(workspace_routes,'lab_overview',side_effect=sqlite3.OperationalError('locked')):
            response = self.client.get('/spaces/lab')
        self.assertEqual(response.status_code,503)
        self.assertIn('temporarily unavailable',response.text)
        self.assertIn('id="workspace-navigation"',response.text)

    def test_source_text_is_escaped_and_cross_space_links_remain_available(self):
        self.seed_research()
        with sqlite3.connect(self.paths['memory']) as conn:
            conn.execute("UPDATE sessions SET title='<script>alert(1)</script>'")
        html = self.client.get('/spaces/research').text
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',html)
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('/spaces/writing',html)
        self.assertIn('/spaces/lab',html)

    def test_deep_page_templates_share_correct_shell_including_scout_renderer(self):
        templates = make_templates()
        for path, template, values, expected in [
            ('/write/project','writing_workspace.html',{'project_id':'project'},'writing'),
            ('/research/chat','research_chat.html',{},'research'),
            ('/research/style','research_style.html',{},'writing'),
            ('/plan','planner.html',{'manuscripts':[],'experiment_statuses':[],'task_priorities':[]},'lab'),
        ]:
            response = templates.TemplateResponse(request(path),template,values)
            html = response.body.decode()
            self.assertIn(f'data-workspace="{expected}"',html)
            self.assertEqual({link['href'] for link in self.nav(html)}, {entry['href'] for entry in WORKSPACES[expected]['nav']})
        from jfr.web.scout_routes import templates as scout_templates
        response = scout_templates.TemplateResponse(request('/research/scout'),'research_search.html',{})
        self.assertIn('data-workspace="research"',response.body.decode())

    def test_already_running_template_renderer_remains_usable_until_routes_reload(self):
        from fastapi.templating import Jinja2Templates
        from jfr.web.themes import manifest
        legacy = Jinja2Templates(directory=str(Path(workspace_routes.__file__).parent / 'templates'))
        legacy.env.globals['appearance'] = manifest()
        for path, name, values, expected in [
            ('/write/one','writing_workspace.html',{'project_id':'one'},'writing'),
            ('/research/chat','research_chat.html',{},'research'),
            ('/','dashboard.html',{},'lab'),
        ]:
            response = legacy.TemplateResponse(request(path),name,values)
            self.assertIn(f'data-workspace="{expected}"',response.body.decode())


if __name__ == '__main__':
    unittest.main()
