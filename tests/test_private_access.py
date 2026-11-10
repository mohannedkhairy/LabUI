"""Private-network access must not expose the library to other tailnet users."""
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from jfr.web.private_access import PrivateAccessMiddleware


class PrivateAccessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.policy = Path(temporary.name)/'access.json'
        self.policy.write_text(json.dumps({'owner_login': 'owner@example.com'}))
        app = FastAPI()
        app.add_middleware(PrivateAccessMiddleware, policy_path=self.policy)
        @app.get('/')
        def home():
            return {'private': True}
        @app.get('/stream')
        def stream():
            return StreamingResponse(iter(['data: first\n\n','data: second\n\n']), media_type='text/event-stream')
        self.app = app

    def client(self, address):
        client = TestClient(self.app, client=(address, 12345))
        self.addCleanup(client.close)
        return client

    def test_local_browser_and_health_probes_work_without_login(self):
        self.assertEqual(self.client('127.0.0.1').get('/').status_code, 200)

    def test_owner_identity_is_accepted_over_private_network(self):
        response = self.client('100.64.1.2').get('/', headers={
            'Tailscale-User-Login': 'OWNER@example.com', 'X-Forwarded-For': '100.64.1.2',
        })
        self.assertEqual(response.status_code, 200)

    def test_different_tailnet_member_is_rejected(self):
        response = self.client('100.64.1.2').get('/', headers={'Tailscale-User-Login': 'other@example.com'})
        self.assertEqual(response.status_code, 403)

    def test_remote_request_without_identity_is_rejected(self):
        self.assertEqual(self.client('100.64.1.2').get('/').status_code, 403)

    def test_forwarded_request_does_not_inherit_local_bypass(self):
        response = self.client('127.0.0.1').get('/', headers={'X-Forwarded-For': '100.64.1.2'})
        self.assertEqual(response.status_code, 403)

    def test_missing_or_invalid_policy_denies_remote_access(self):
        self.policy.unlink()
        client = self.client('100.64.1.2')
        self.assertEqual(client.get('/', headers={'Tailscale-User-Login': 'owner@example.com'}).status_code, 403)
        self.policy.write_text('invalid json')
        self.assertEqual(client.get('/', headers={'Tailscale-User-Login': 'owner@example.com'}).status_code, 403)

    def test_streaming_is_preserved_for_owner(self):
        response = self.client('100.64.1.2').get('/stream', headers={'Tailscale-User-Login': 'owner@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, 'data: first\n\ndata: second\n\n')


if __name__ == '__main__':
    unittest.main()
