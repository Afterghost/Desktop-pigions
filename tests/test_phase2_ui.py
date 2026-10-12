import os
from pathlib import Path
import sys
import tempfile
import unittest

try:
    import tkinter as tk
except ImportError:
    tk = None

from storage import Store


@unittest.skipUnless(tk is not None and (sys.platform == "win32" or os.environ.get("DISPLAY")),
                     "Tkinter and a graphical display are required")
class Phase2UITests(unittest.TestCase):
    def setUp(self):
        from app import DesktopPigeonApp
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = tk.Tk()
        self.app = DesktopPigeonApp(self.root, Store(Path(self.temp.name)))
        self.addCleanup(self.close)
        self.root.update()
        self.root.after_cancel(self.app.tick_id)
        self.app.tick_id = None

    def close(self):
        if not self.app.closed:
            self.app.close()

    def test_pet_feed_game_rewards_and_save_reload(self):
        profile = self.app.nest.companion
        self.app.nest_window.show()
        self.app.nest_window.pet_button.invoke()
        self.assertGreater(profile.friendship, 0)
        self.assertEqual(str(self.app.nest_window.pet_button["state"]), "disabled")
        self.app.nest_window.food_buttons["seed_mix"].invoke()
        game_ui = self.app.game_window
        game_ui.show()
        game_ui.start_button.invoke()
        for _ in range(5):
            game_ui.buttons[game_ui.game.current[1]].invoke()
        self.assertEqual(profile.games_won, 1)
        self.assertEqual(profile.food["sunflower_seeds"], 5)
        game_ui.buttons["Treasure"].invoke()
        self.assertEqual(profile.games_won, 1)
        self.assertIn("5/5", game_ui.prompt["text"])
        self.assertEqual(self.app.store.load()[1].companion, profile)
        self.assertEqual(float(self.app.nest_window.friendship["value"]), profile.friendship)

    def test_pause_freezes_game_and_gift_progress(self):
        profile = self.app.nest.companion
        profile.befriend(20)
        profile.gift_timer = 119
        self.app.game_window.start()
        self.app.toggle_pause()
        self.app.game_window.answer("Treasure")
        self.app.advance(10)
        self.assertEqual(self.app.game_window.game.index, 0)
        self.assertEqual(profile.gift_timer, 119)
        self.assertEqual(len(self.app.nest.items), 0)
        self.app.toggle_pause()
        self.app.advance(1)
        self.app.render()
        self.assertEqual(len(self.app.nest.items), 1)
        self.assertEqual(self.app.nest.items[0].kind, "Gift")
        self.assertIn("gift:", self.app.nest_window.activity["text"])

    def test_empty_food_does_not_feed_or_increase_friendship(self):
        self.app.nest.companion.food["golden_corn"] = 0
        hunger = self.app.pigeon.hunger
        self.app.feed("golden_corn")
        self.assertEqual(self.app.pigeon.hunger, hunger)
        self.assertEqual(self.app.nest.companion.friendship, 0)
        self.assertIn("No portions", self.app.nest_window.activity["text"])
