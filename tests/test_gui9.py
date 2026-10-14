import os
import unittest
from unittest.mock import MagicMock, patch
from mcp_server import gui9


@unittest.skipUnless(os.name=='nt','Windows process identity test')
class WindowIdentityTests(unittest.TestCase):
    def test_browser_title_cannot_impersonate_simapro(self):
        try:
            import win32api, win32process
        except ImportError:
            self.skipTest('Optional GUI dependencies not installed')
        window=MagicMock()
        window.class_name.return_value='Chrome_WidgetWin_1'
        with patch.object(win32api,'OpenProcess',return_value=MagicMock()), \
             patch.object(win32process,'GetModuleFileNameEx',return_value=r'C:\Browser\msedge.exe'):
            self.assertFalse(gui9._is_simapro_window(window))
        with patch.object(win32api,'OpenProcess',return_value=MagicMock()), \
             patch.object(win32process,'GetModuleFileNameEx',return_value=r'D:\Program Files\SimaPro\SimaPro.exe'):
            self.assertTrue(gui9._is_simapro_window(window))
        window.class_name.return_value='TApplication'
        self.assertFalse(gui9._is_simapro_window(window))

    def test_gui_input_requires_exact_title(self):
        window=MagicMock()
        window.window_text.return_value='SimaPro 9.0.0.48'
        with patch.dict(os.environ,{'SIMAPRO_GUI_ENABLED':'1'}), patch.object(gui9,'_app',return_value=window):
            with self.assertRaises(ValueError):
                gui9.gui_step('type_keys',key_sequence='abc',approval_token='I_APPROVE_GUI_STEP')
            with self.assertRaises(RuntimeError):
                gui9.gui_step('type_keys',key_sequence='abc',expected_window='SimaPro',approval_token='I_APPROVE_GUI_STEP')
        window.type_keys.assert_not_called()
