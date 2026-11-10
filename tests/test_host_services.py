"""Keep app and adapter restart policy independent of GPU availability."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.install_user_services import unit_text


class HostServiceTests(unittest.TestCase):
    def test_app_wants_adapter_without_stopping_when_it_restarts(self):
        unit = unit_text(Path('/home/test/LabUI'), Path('/home/test/labui.env'), False)
        self.assertIn('Wants=labui-model.service', unit)
        self.assertNotIn('Requires=labui-model.service', unit)
        self.assertIn('Restart=always', unit)
        self.assertIn('--app-only', unit)
        self.assertIn('--what=sleep', unit)
        self.assertIn('${LABUI_PORT}', unit)

    def test_adapter_restarts_and_uses_configured_port(self):
        unit = unit_text(Path('/home/test/LabUI'), Path('/home/test/labui.env'), True)
        self.assertIn('Restart=always', unit)
        self.assertIn('${LABUI_LM_PROXY_PORT}', unit)
        self.assertIn('WantedBy=default.target', unit)


if __name__ == '__main__':
    unittest.main()
