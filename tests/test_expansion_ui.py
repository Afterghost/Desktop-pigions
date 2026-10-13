import os
from pathlib import Path
import sys
import tempfile
import unittest

try:
    import tkinter as tk
except ImportError:
    tk = None

from desktop import Treasure
from progression import GAME_NAMES
from storage import Store
from test_expansion import winning_choice


@unittest.skipUnless(tk is not None and (sys.platform == "win32" or os.environ.get("DISPLAY")),
                     "Tkinter and a graphical display required")
class ExpansionUITests(unittest.TestCase):
    def setUp(self):
        from app import DesktopPigeonApp
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = tk.Tk()
        self.app = DesktopPigeonApp(self.root, Store(Path(self.directory.name)))
        self.addCleanup(self.app.close)
        self.root.update()
        self.root.after_cancel(self.app.tick_id)
        self.app.tick_id = None

    def test_all_game_controls_reward_once_and_pause_freezes_memory(self):
        ui = self.app.game_window
        profile = self.app.nest.companion
        ui.show()
        for name in GAME_NAMES:
            ui.selection.set(name)
            ui.start_button.invoke()
            self.assertIsNotNone(ui.game)
            self.app.toggle_pause()
            before = ui.game.index
            ui.answer(winning_choice(ui.game))
            ui.hide_button.invoke()
            self.app.advance(100)
            self.assertEqual(ui.game.index, before)
            self.app.toggle_pause()
            if name == "Pigeon Memory":
                self.assertTrue(ui.game.revealing)
                ui.hide_button.invoke()
            for _ in range(5):
                ui.buttons[winning_choice(ui.game)].invoke()
            self.assertIn(name, profile.progression.achievements)
            self.assertEqual(profile.games_won, GAME_NAMES.index(name) + 1)
            self.assertEqual(len(self.app.nest.items), GAME_NAMES.index(name) + 1)
            self.assertIn(self.app.nest.items[-1].kind, ("Treasure", "Fragment"))
            self.assertIsNone(ui.game.claim_reward())
        self.assertEqual(profile, self.app.store.load()[1].companion)
        self.assertEqual(self.app.store.load()[1].companion.progression.forage_cooldown, 300)
        ui.start()
        self.assertIn("300 active seconds", ui.feedback["text"])

    def test_game_close_cancels_round(self):
        ui = self.app.game_window
        ui.show()
        self.root.update()
        ui.start()
        ui.buttons[winning_choice(ui.game)].invoke()
        self.assertTrue(ui.overlay_open)
        ui.cancel()
        self.assertFalse(ui.overlay_open)
        self.assertTrue(ui.game.cancelled)
        self.assertIsNone(ui.game.claim_reward())
        self.assertEqual(self.app.nest.companion.games_won, 0)
        ui.show()
        ui.start_button.invoke()
        self.assertEqual(ui.game.index, 0)

    def test_game_picker_and_choices_run_on_pigeon_overlay(self):
        ui = self.app.game_window
        ui.show()
        self.root.update()
        bird = self.app.birds[self.app.flock.selected_id]
        self.assertEqual(ui.window.state(), "withdrawn")
        self.assertEqual(int(bird.canvas["width"]), 500)
        self.assertTrue(any("game_panel" in bird.canvas.gettags(item)
                            for item in bird.canvas.find_all()))
        self.assertTrue(ui.handle_click(ui.participant, 302, 247))
        self.assertIsNotNone(ui.game)
        answer = next(bounds for bounds, action, _ in ui.hit_regions
                      if action == "answer")
        x, y = (answer[0] + answer[2]) // 2, (answer[1] + answer[3]) // 2
        self.assertTrue(ui.handle_click(ui.participant, x, y))
        self.assertEqual(ui.game.index, 1)
        ui.cancel()

    def test_overlay_layout_keeps_board_onscreen_at_right_edge(self):
        ui = self.app.game_window
        pigeon = self.app.pigeon
        pigeon.x = self.app.bounds.x + self.app.bounds.width - 96
        width, height, x, y, offset_x, offset_y = ui.overlay_layout(pigeon)
        self.assertLessEqual(x, self.app.bounds.x + self.app.bounds.width - width)
        self.assertEqual(ui.panel_shift, -104)
        self.assertGreaterEqual(offset_x, width - 120)
        self.assertGreaterEqual(offset_y, 0)

    def test_governing_cancel_protection_trade_cooldown_and_pause(self):
        app = self.app
        target = Treasure("Blue marble", "Treasure", "#abc", app.pigeon.x, app.pigeon.y)
        app.pigeon.investigate(target)
        app.toggle_pause()
        self.assertFalse(app.intervene("Shoo / catch"))
        app.protect("Treasure")
        self.assertNotIn("Treasure", app.nest.companion.progression.protected)
        app.toggle_pause()
        self.assertTrue(app.intervene("Shoo / catch"))
        reputation = app.nest.companion.progression.reputation
        app.pigeon.investigate(target)
        self.assertFalse(app.intervene("Laser distraction"))
        self.assertEqual(reputation, app.nest.companion.progression.reputation)
        app.protect("Treasure")
        self.assertIsNone(app.pigeon.treasure)
        self.assertFalse(app.pigeon.investigate(target))
        app.advance(10)
        self.assertEqual(app.nest.items, [])
        self.assertIn("Treasure", app.store.load()[1].companion.progression.protected)
        app.protect("Treasure")
        app.pigeon.investigate(target)
        app.nest.companion.food["sunflower_seeds"] = 0
        self.assertFalse(app.intervene("Seed bribe / trade"))
        self.assertIsNotNone(app.pigeon.treasure)
        app.nest.companion.food["sunflower_seeds"] = 1
        self.assertTrue(app.intervene("Seed bribe / trade"))
        self.assertEqual(app.nest.companion.food["sunflower_seeds"], 0)
        app.advance(10)
        app.pigeon.investigate(target)
        self.assertTrue(app.intervene("Laser distraction"))
        self.assertIsNone(app.pigeon.treasure)

    def test_last_chance_pause_and_persistent_reconciliation_by_selected_item(self):
        app = self.app
        app.pigeon.hunger = 100
        progress = app.nest.companion.progression
        progress.neglect = 239
        app.toggle_pause()
        app.advance(100)
        self.assertEqual(progress.neglect, 239)
        app.toggle_pause()
        app.advance(1)
        app.render()
        self.root.update()
        self.assertIn("Last Chance Coo", app.nest_window.progress["text"])
        self.assertEqual(app.nest_window.window.state(), "normal")
        self.assertEqual(app.store.load()[1].companion.progression.neglect, 240)
        item = app.nest.collect(Treasure("Friendship twig", "Gift", "#abc", 0, 0))
        app.render()
        app.nest_window.tree.selection_set(item.id)
        app.nest_window.return_button.invoke()
        self.assertEqual(progress.neglect, 0)
        self.assertIn("Forgiven", app.nest_window.personality["text"])
        self.assertIn("The Day We Made Up", app.nest_window.journal["text"])
        self.assertTrue(app.store.load()[1].companion.progression.forgiven)
        self.assertEqual(app.nest.items, [])
