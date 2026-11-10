"""Private publishing must wait for sign-in and establish ownership first."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import publish_private_access as publisher


class PrivatePublisherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)/'access.json'
        mock = patch.dict('os.environ', {'LABUI_ACCESS_POLICY':str(self.path),'LABUI_PORT':'8770'})
        mock.start()
        self.addCleanup(mock.stop)
        self.status = {'BackendState':'Running','Self':{'UserID':42,'DNSName':'labui.example.ts.net.'},
                       'User':{'42':{'LoginName':'owner@example.com'}}}

    def result(self, value, code=0):
        return SimpleNamespace(stdout=json.dumps(value),stderr='',returncode=code)

    def test_no_service_is_published_before_account_sign_in(self):
        with patch.object(publisher,'command',return_value=self.result({'BackendState':'NeedsLogin'})) as command:
            self.assertEqual(publisher.main(),0)
        command.assert_called_once_with('status','--json')
        self.assertFalse(self.path.exists())

    def test_owner_policy_exists_before_enabling_serve(self):
        def command(*arguments):
            if arguments==('status','--json'):return self.result(self.status)
            if arguments==('serve','status','--json'):return self.result({})
            self.assertEqual(arguments,('serve','--bg','--yes','http://127.0.0.1:8770'))
            self.assertEqual(json.loads(self.path.read_text())['owner_login'],'owner@example.com')
            return SimpleNamespace(stdout='Private HTTPS enabled',stderr='',returncode=0)
        with patch.object(publisher,'command',side_effect=command):
            self.assertEqual(publisher.main(),0)
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

    def test_existing_serve_configuration_is_left_running(self):
        configuration={'Web':{'labui.example.ts.net:443':{'Handlers':{'/':{'Proxy':'http://127.0.0.1:8770'}}}}}
        with patch.object(publisher,'command',side_effect=[self.result(self.status),self.result(configuration)]) as command:
            self.assertEqual(publisher.main(),0)
        self.assertEqual(command.call_count,2)

    def test_unknown_host_owner_does_not_publish_service(self):
        self.status['User']={}
        with patch.object(publisher,'command',return_value=self.result(self.status)) as command:
            with self.assertRaisesRegex(RuntimeError,'host owner'):
                publisher.main()
        command.assert_called_once_with('status','--json')


if __name__=='__main__':
    unittest.main()
