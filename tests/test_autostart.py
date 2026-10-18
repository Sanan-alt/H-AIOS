import os
import unittest
from unittest.mock import patch, MagicMock

from core import autostart


class AutostartTests(unittest.TestCase):

    def test_startup_command_contains_background_or_wscript(self):
        cmd = autostart.get_windows_startup_command()
        self.assertTrue("wscript.exe" in cmd or "--background" in cmd)

    def test_enable_and_disable_autostart_with_mocked_registry(self):
        with patch.object(autostart, "is_windows", return_value=True):
            with patch("winreg.OpenKey", create=True) as mock_open:
                with patch("winreg.SetValueEx", create=True) as mock_set:
                    with patch("winreg.CloseKey", create=True):
                        ok, msg = autostart.enable_autostart()
                        self.assertTrue(ok)
                        mock_set.assert_called_once()

            with patch("winreg.OpenKey", create=True) as mock_open:
                with patch("winreg.DeleteValue", create=True) as mock_del:
                    with patch("winreg.CloseKey", create=True):
                        ok, msg = autostart.disable_autostart()
                        self.assertTrue(ok)
                        mock_del.assert_called_once()


if __name__ == "__main__":
    unittest.main()
