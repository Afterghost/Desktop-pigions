import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

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

    def test_slow_mouse_strokes_pet_at_the_birds_preferred_pace(self):
        bird = self.app.flock.selected
        bird.companion.traits = {"curiosity": 10, "calm": 80, "sociability": 20}
        bird.companion.pet_preference = "slow"
        self.app.render()
        self.app.nest_window.petting_speed.set("Slow")
        self.assertIn("likes slow petting", self.app.nest_window.personality["text"])
        times = (0, .3, .6, .9, 1.2, 1.5)
        with patch("app.time.monotonic", side_effect=times):
            for x in (10, 40, 70, 40, 10, 40):
                self.app._pet_motion(bird.id, SimpleNamespace(x=x))
        self.assertEqual(bird.companion.friendship, 4)
        self.assertIn("Perfect slow strokes", self.app.activity_status)

    def test_developer_settings_apply_and_keybinding_capture(self):
        settings = self.app.developer_settings
        settings.speed.set(2.0)
        settings.roam.set(350)
        settings.rest.set(0.5)
        settings.treasure_interval.set(12)
        settings._apply()
        pigeon = self.app.pigeon
        self.assertEqual((pigeon.movement_scale, pigeon.roam_radius, pigeon.rest_scale),
                         (2.0, 350, 0.5))
        self.assertEqual(self.app.treasure_interval, 12)

        settings._capture_key()
        self.app._handle_keypress(SimpleNamespace(keysym="F9"))
        self.assertEqual(self.app.pause_key, "F9")
        self.app._handle_keypress(SimpleNamespace(keysym="F9"))
        self.assertTrue(self.app.paused)
        self.app._handle_keypress(SimpleNamespace(keysym="F9"))
        self.assertFalse(self.app.paused)

        settings.gesture.set("Double-click")
        self.app.pet_gestures[self.app.flock.selected_id].reset()
        self.assertEqual(settings.gesture.get(), "Double-click")

    def test_pointer_prank_shake_restores_cursor_and_startles_thief(self):
        app = self.app
        pigeon = app.pigeon
        app.pointer_thief = app.flock.selected_id
        app.pointer_stolen_at = 10
        app.last_mouse_vector = (-50, 10)
        app.cursor_hide.show = lambda: setattr(app, "cursor_restored", True)
        app.cursor_restored = False
        app._restore_pointer(startled=True)

        self.assertTrue(app.cursor_restored)
        self.assertIsNone(app.pointer_thief)
        self.assertTrue(pigeon.startled)
        self.assertEqual(pigeon.destination[0], pigeon.x + 100)

    def test_pointer_prank_has_automatic_restore_timeout(self):
        app = self.app
        app.pointer_thief = app.flock.selected_id
        app.pointer_stolen_at = 10
        app.cursor_hide.show = lambda: setattr(app, "cursor_restored", True)
        app.cursor_restored = False
        with patch.object(app.root, "winfo_pointerxy", return_value=(0, 0)):
            app._check_pointer_prank(12.1)

        self.assertTrue(app.cursor_restored)
        self.assertIsNone(app.pointer_thief)
        self.assertFalse(app.pigeon.startled)
