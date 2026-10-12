"""Interaction tests without constructing a Tk window."""

from types import SimpleNamespace
import ctypes
import unittest
from unittest.mock import Mock, patch

from app import App, WindowsOverlay
from pigeon import Pigeon, MAX_ITEMS


class InteractionTests(unittest.TestCase):
    def setUp(self):
        self.app = App.__new__(App)
        self.app.width, self.app.height = 800, 600
        self.app.bird = Pigeon(800, 600)
        self.app.drag = None
        self.app.tray_open = True
        self.app.preview = False
        self.app.notice = ""
        self.app.regions = [
            ("bird", (365, 265, 440, 326)),
            ("tab", (475, 100, 514, 182)),
            ("panel", (514, 0, 800, 600)),
            ("seed_mix", (528, 112, 786, 155)),
        ]

    def test_drag_from_tray_places_food_at_release_position(self):
        self.app.press(SimpleNamespace(x=600, y=130))
        self.assertEqual(self.app.drag, "seed_mix")
        self.app.motion(SimpleNamespace(x=200, y=200))
        self.app.release(SimpleNamespace(x=200, y=200))
        self.assertIsNone(self.app.drag)
        self.assertEqual(len(self.app.bird.items), 1)
        self.assertEqual(self.app.bird.items[0].x, 200)

    def test_releasing_in_tray_or_outside_cancels(self):
        for x, y in ((600, 130), (600, 450), (-1, 100), (800, 100), (100, 600)):
            with self.subTest(x=x, y=y):
                self.app.drag = "seed_mix"
                self.app.release(SimpleNamespace(x=x, y=y))
                self.assertIsNone(self.app.drag)
                self.assertEqual(self.app.bird.items, [])

    def test_escape_cancels_drag_before_closing_tray(self):
        self.app.drag = "feather"
        self.app.escape()
        self.assertIsNone(self.app.drag)
        self.assertTrue(self.app.tray_open)
        self.app.escape()
        self.assertFalse(self.app.tray_open)
        self.app.escape()  # Never exits an unfocused desktop overlay.

    def test_item_limit_feedback(self):
        for _ in range(MAX_ITEMS):
            self.app.bird.place("seed_mix", 100, 100)
        self.app.drag = "feather"
        self.app.release(SimpleNamespace(x=200, y=200))
        self.assertIn(str(MAX_ITEMS), self.app.notice)
        self.assertEqual(len(self.app.bird.items), MAX_ITEMS)

    def test_blank_desktop_is_not_an_interactive_region(self):
        self.assertIsNone(self.app.hit(100, 100))
        self.assertEqual(self.app.hit(600, 130), "seed_mix")
        self.assertEqual(self.app.hit(600, 500), "panel")


class WindowsBindingTests(unittest.TestCase):
    def setUp(self):
        self.user32 = Mock()
        self.kernel32 = Mock()
        # Deliberately exercise handles above the 32-bit range on 64-bit Python.
        self.handle = 0x123456789 if ctypes.sizeof(ctypes.c_void_p) == 8 else 123
        self.user32.GetAncestor.return_value = self.handle
        self.user32.GetWindowLongPtrW.return_value = 0x80000
        self.user32.GetWindowLongW.return_value = 0x80000
        self.user32.SetWindowLongPtrW.return_value = 0x80000
        self.user32.SetWindowLongW.return_value = 0x80000
        self.user32.SetLayeredWindowAttributes.return_value = 1
        self.user32.SetWindowPos.return_value = 1
        self.user32.SetWindowsHookExW.return_value = self.handle + 1
        self.user32.CallNextHookEx.return_value = 0
        self.kernel32.GetCurrentThreadId.return_value = 123
        self.root = SimpleNamespace(winfo_id=lambda: self.handle - 1)
        self.patches = [
            patch.object(ctypes, "WinDLL", side_effect=lambda name, **kw:
                         self.user32 if name == "user32" else self.kernel32, create=True),
            patch.object(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE, create=True),
            patch.object(ctypes, "set_last_error", create=True),
            patch.object(ctypes, "get_last_error", return_value=0, create=True),
            patch.object(ctypes, "WinError", side_effect=lambda code: OSError(code, "test failure"),
                         create=True),
        ]
        for mocked in self.patches:
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_pointer_sized_styles_click_through_and_focus_guard(self):
        overlay = WindowsOverlay(self.root)
        self.assertEqual(overlay.hwnd, self.handle)
        self.assertIs(overlay.get_style.restype, ctypes.c_ssize_t)
        self.assertIs(overlay.set_style.argtypes[-1], ctypes.c_ssize_t)
        self.assertTrue(overlay.click_through)
        self.assertEqual(overlay.activation_proc(5, 0, 0), 1)
        self.assertEqual(overlay.activation_proc(9, 0, 0), 1)
        self.assertEqual(overlay.activation_proc(-1, 0, 0), 0)
        overlay.set_interactive(True)
        self.assertFalse(overlay.click_through)
        self.assertEqual(overlay.set_style.call_args.args[-1] & 0x20, 0)
        self.assertTrue(overlay.set_style.call_args.args[-1] & 0x08000000)
        overlay.set_interactive(False)
        self.assertTrue(overlay.set_style.call_args.args[-1] & 0x20)
        overlay.restore()
        self.user32.UnhookWindowsHookEx.assert_called_once_with(self.handle + 1)

    def test_first_mapping_can_replace_wrapper(self):
        overlay = WindowsOverlay(self.root)
        self.user32.GetAncestor.return_value = self.handle + 2
        overlay.refresh_window(self.root)
        self.assertEqual(overlay.hwnd, self.handle + 2)
        self.assertEqual(self.user32.SetWindowPos.call_args.args[0], self.handle + 2)
        self.assertTrue(overlay.set_style.call_args.args[-1] & 0x20)
        overlay.restore()

    def test_failed_transparency_restores_style_and_unhooks(self):
        self.user32.SetLayeredWindowAttributes.return_value = 0
        with self.assertRaises(OSError):
            WindowsOverlay(self.root)
        self.user32.UnhookWindowsHookEx.assert_called_once_with(self.handle + 1)


if __name__ == "__main__":
    unittest.main()
