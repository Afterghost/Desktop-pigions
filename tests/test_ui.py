import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    import tkinter as tk
except ImportError:
    tk = None

from desktop import Treasure
from storage import Store


@unittest.skipUnless(tk is not None and (sys.platform == "win32" or os.environ.get("DISPLAY")),
                     "Tkinter and a graphical display are required")
class DesktopUITests(unittest.TestCase):
    def setUp(self):
        from app import DesktopPigeonApp

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(Path(self.temporary.name) / "DesktopPigeon")
        self.root = tk.Tk()
        self.app = DesktopPigeonApp(self.root, self.store)
        self.addCleanup(self.destroy)
        self.root.update()
        self.root.after_cancel(self.app.tick_id)
        self.app.tick_id = None

    def destroy(self):
        if not self.app.closed:
            self.app.close()

    def test_one_visible_pigeon_and_feeding_button(self):
        self.assertEqual(self.root.state(), "normal")
        self.assertTrue(self.app.bird.canvas.find_all())
        with patch.object(self.root, "deiconify") as deiconify:
            self.app.render()
            deiconify.assert_not_called()
        self.app.nest_window.show()
        self.app.pigeon.hunger = 80
        self.app.nest_window.food_buttons["seed_mix"].invoke()
        self.root.update_idletasks()
        self.assertEqual(self.app.pigeon.hunger, 65)
        self.assertEqual(float(self.app.nest_window.hunger["value"]), 65)
        self.assertTrue(any(self.app.bird.canvas.itemcget(item, "text") == "Coo! Thank you!"
                            for item in self.app.bird.canvas.find_all()
                            if self.app.bird.canvas.type(item) == "text"))
        self.assertEqual(self.store.load()[0], 65)

    def test_theft_overlay_inventory_pause_and_reload(self):
        self.app.rng = random.Random(2)
        self.app.nest_window.shiny_button.invoke()
        self.root.update()
        self.assertEqual(self.app.shiny_overlay.window.state(), "normal")
        target = self.app.pigeon.treasure
        self.app.toggle_pause()
        before = (self.app.pigeon.x, self.app.pigeon.y, self.app.pigeon.hunger)
        self.app.advance(10)
        self.assertEqual(before, (self.app.pigeon.x, self.app.pigeon.y, self.app.pigeon.hunger))
        self.app.toggle_pause()
        for _ in range(600):
            self.app.advance(0.05)
            if self.app.nest.items:
                break
        self.app.render()
        self.root.update()
        self.assertEqual(len(self.app.nest.items), 1)
        self.assertEqual(self.app.nest.items[0].name, target.name)
        self.assertEqual(self.app.shiny_overlay.window.state(), "withdrawn")
        self.assertEqual(len(self.app.nest_window.tree.get_children()), 1)
        self.assertEqual(self.store.load()[1], self.app.nest)
        self.app.close()
        self.assertTrue(self.app.closed)

    def test_corrupt_save_disables_writing_and_shows_warning(self):
        from app import DesktopPigeonApp

        self.app.close()
        self.store.path.write_text("damaged")
        self.root = tk.Tk()
        self.app = DesktopPigeonApp(self.root, self.store)
        self.root.update()
        self.assertFalse(self.app.saving_enabled)
        self.assertIn("Saving disabled", self.app.nest_window.notice["text"])
        self.app.feed("seed_mix")
        self.app.close()
        self.assertEqual(self.store.path.read_text(), "damaged")

    def test_save_failure_shows_warning_and_exit_can_be_cancelled(self):
        from storage import SaveError

        with patch.object(self.store, "save", side_effect=SaveError("Could not save locally.")):
            self.app.feed("seed_mix")
            self.assertIn("Could not save", self.app.nest_window.notice["text"])
            with patch("app.messagebox.askyesno", return_value=False):
                self.app.close()
            self.assertFalse(self.app.closed)
        self.app.nest.collect(Treasure("Blue marble", "Treasure", "#72c9ed", 0, 0))
        self.assertTrue(self.app.save())
        self.app.render()
        self.assertEqual(self.app.nest_window.notice["text"],
                         "Generated overlays only. No desktop files read.")
