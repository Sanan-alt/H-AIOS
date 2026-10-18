import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QCloseEvent


class ShutdownHandlerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_force_quit_allows_close_event_to_accept(self):
        import ui
        with patch.object(ui.MainWindow, "_setup_system_tray", lambda self: None):
            with patch.object(ui.MainWindow, "_load_saved_voice", lambda self: None):
                with patch.object(ui.MainWindow, "_load_saved_tts", lambda self: None):
                    with patch.object(ui.MainWindow, "_show_setup", lambda self: None):
                        win = ui.MainWindow("face.png")
                        win._force_quit = True

                        event = QCloseEvent()
                        win.closeEvent(event)
                        self.assertTrue(event.isAccepted())

    def test_request_quit_sets_force_quit_flag(self):
        import ui
        with patch.object(ui.MainWindow, "_setup_system_tray", lambda self: None):
            with patch.object(ui.MainWindow, "_load_saved_voice", lambda self: None):
                with patch.object(ui.MainWindow, "_load_saved_tts", lambda self: None):
                    with patch.object(ui.MainWindow, "_show_setup", lambda self: None):
                        win = ui.MainWindow("face.png")
                        self.assertFalse(win._force_quit)

                        quit_mock = MagicMock()
                        win.on_quit_requested = quit_mock
                        win._request_quit()

                        self.assertTrue(win._force_quit)
                        quit_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
