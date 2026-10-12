import os
from pathlib import Path
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


@unittest.skipUnless(tk and (sys.platform == "win32" or os.environ.get("DISPLAY")), "Tk display required")
class FlockUITests(unittest.TestCase):
    def setUp(self):
        from app import DesktopPigeonApp
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent)
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name))
        self.root = tk.Tk()
        self.app = DesktopPigeonApp(self.root, self.store)
        self.addCleanup(self.cleanup)
        self.root.update()
        self.root.after_cancel(self.app.tick_id)
        self.app.tick_id = None

    def cleanup(self):
        if not self.app.closed:
            self.app.close()

    def grow(self):
        app = self.app
        app.flock.treasury = 5
        app.nest_window.upgrade_button.invoke()
        app.nest_window.egg_button.invoke()
        app.advance(59)
        self.assertEqual(len(app.pigeons), 1)
        app.advance(1)
        app.render()
        self.root.update()
        self.assertEqual(len(app.pigeons), 2)
        return app.flock.active

    def test_multiple_windows_selected_feed_collector_and_reload(self):
        app = self.app
        parent, child = self.grow()
        for overlay in app.birds.values():
            self.assertEqual(overlay.window.state(), "normal")
            self.assertTrue(overlay.canvas.find_all())
        app.pigeons[parent.id].hunger = 80
        app.pigeons[child.id].hunger = 60
        app.birds[child.id].canvas.event_generate("<Button-1>", x=20, y=20)
        self.root.update()
        self.assertEqual(app.flock.selected_id, child.id)
        app.nest_window.food_buttons["seed_mix"].invoke()
        self.assertEqual(app.pigeons[parent.id].hunger, 80)
        self.assertEqual(app.pigeons[child.id].hunger, 45)
        app.next_forage = app.elapsed + 10000
        for record in app.flock.active:
            app.pigeons[record.id].cancel_theft()
            record.forage_timer = 60
        target = Treasure("Blue marble", "Treasure", "#abc", 0, 0)
        bird = app.pigeons[parent.id]
        bird.investigate(target)
        from pigeon import Behavior
        bird.behavior = Behavior.STORING
        bird.wait = .1
        count = parent.companion.progression.actions["collect"]
        app.advance(.1)
        self.assertEqual(parent.companion.progression.actions["collect"], count + 1)
        self.assertEqual(child.companion.progression.actions["collect"], 0)
        app.save()
        hunger, nest = self.store.load()
        self.assertEqual(hunger, app.pigeons[child.id].hunger)
        self.assertEqual(nest.flock.selected_id, child.id)
        self.assertEqual(nest, app.nest)
        app.close()
        self.assertTrue(app.closed)
        before = nest.flock.records[0].lifetime
        self.assertEqual(self.store.load()[1].flock.records[0].lifetime, before)

    def test_departure_grace_pause_return_history_and_stale_callbacks(self):
        app = self.app
        record = app.flock.selected
        profile = record.companion
        app.pigeon.hunger = 100
        profile.progression.neglect = 239
        app.game_window.start()
        old_game = app.game_window.game
        app.advance(1)
        app.render()
        self.assertIn("120 active seconds", app.nest_window.progress["text"])
        app.advance(119)
        self.assertEqual(profile.progression.grace, 119)
        app.toggle_pause()
        before = record.lifetime
        app.advance(1000)
        self.assertEqual(record.lifetime, before)
        app.toggle_pause()
        app.advance(1)
        self.assertFalse(app.has_bird)
        self.assertEqual(len(app.pigeons), 0)
        self.assertTrue(old_game.cancelled)
        self.assertIsNone(old_game.claim_reward())
        self.assertFalse(app.reward_game(5, record.id))
        self.assertIsNone(app.pigeon.treasure)
        app.feed("seed_mix")
        self.assertEqual(profile.games_won, 0)
        legacy = record.legacy
        self.assertIsNotNone(legacy)
        self.assertEqual(record.lifetime, 121)
        app.render()
        self.root.update()
        self.assertEqual(len(app.effects), 1)
        app.advance(3)
        self.assertEqual(app.effects, [])
        app.nest_window.family.selection_set(record.id)
        app.nest_window.rejoin_button.invoke()
        self.root.update()
        self.assertTrue(app.has_bird)
        self.assertEqual(record.id, app.flock.selected_id)
        self.assertEqual(profile.progression.grace, 0)
        app.nest_window.rejoin_button.invoke()
        self.assertEqual(len(app.pigeons), 1)
        self.assertIs(record.legacy, legacy)
        self.assertEqual(self.store.load()[1].flock.selected.legacy, legacy)

    def test_reconcile_grace_and_freeze_eggs_suspend_clock(self):
        app = self.app
        app.flock.treasury = 5
        app.upgrade_nest()
        app.lay_egg()
        app.pigeon.hunger = 100
        progress = app.nest.companion.progression
        progress.neglect = 240
        progress.grace = 119
        app.feed("seed_mix")
        self.assertEqual(progress.grace, 0)
        app.toggle_pause()
        app.advance(100)
        self.assertEqual(app.flock.eggs[0].remaining, 60)
        app.toggle_pause()
        with patch("app.time.monotonic", return_value=app.last_tick + 10000):
            app._tick()
        self.assertEqual(app.flock.eggs[0].remaining, 59.75)
        self.root.after_cancel(app.tick_id)
        app.tick_id = None
        app.save()
        self.assertEqual(self.store.load()[1].flock.eggs[0].remaining, 59.75)
        app.close()
        app.advance(100)
        self.assertEqual(app.flock.eggs[0].remaining, 59.75)

    def test_game_switch_cancels_and_exit_reload_never_rewards_old_participant(self):
        app = self.app
        parent, child = self.grow()
        ui = app.game_window
        ui.start()
        old = ui.game
        ui.answer(old.current[1])
        app.select_bird(child.id)
        self.assertTrue(old.cancelled)
        ui.answer("Treasure")
        self.assertEqual(child.companion.games_won, 0)
        self.assertEqual(parent.companion.games_won, 0)
        self.assertFalse(app.reward_game(5, parent.id))
        ui.start()
        for _ in range(5):
            ui.answer(ui.game.current[1])
        self.assertEqual(child.companion.games_won, 1)
        ui.start()
        running = ui.game
        app.close()
        self.assertTrue(running.cancelled)
        self.assertFalse(app.reward_game(5, child.id))
        nest = self.store.load()[1]
        self.assertEqual(nest.flock.selected.companion.games_won, 1)

    def test_five_birds_capacity_selected_departure_reloads_no_orphan_windows(self):
        from app import DesktopPigeonApp
        app = self.app
        app.flock.treasury = 35
        for _ in range(3):
            app.upgrade_nest()
        for _ in range(4):
            app.lay_egg()
        app.advance(60)
        app.render()
        self.root.update()
        self.assertEqual(len(app.pigeons), 5)
        departed = app.flock.active[2]
        app.select_bird(departed.id)
        pigeon = app.pigeon
        pigeon.hunger = 100
        departed.companion.progression.neglect = 240
        departed.companion.progression.grace = 119
        app.game_window.start()
        pigeon.investigate(Treasure("Blue marble", "Treasure", "#abc", pigeon.x, pigeon.y))
        app.advance(1)
        self.assertEqual(len(app.pigeons), 4)
        self.assertIsNone(pigeon.treasure)
        self.assertNotEqual(app.flock.selected_id, departed.id)
        app.lay_egg()
        self.assertFalse(app.flock.rejoin(departed.id))
        app.advance(60)
        self.assertEqual(len(app.pigeons), 5)
        app.close()
        self.root = tk.Tk()
        self.app = DesktopPigeonApp(self.root, self.store)
        self.root.update()
        self.root.after_cancel(self.app.tick_id)
        self.app.tick_id = None
        self.assertEqual(len(self.app.pigeons), 5)
        self.assertEqual(len(self.app.flock.records), 6)
        self.assertEqual(len(self.app.flock.eggs), 0)
        self.assertIs(self.app.nest.companion, self.app.flock.selected.companion)
        for bird_id, overlay in self.app.birds.items():
            self.assertEqual(overlay.window.state(), "normal")
            pigeon = self.app.pigeons[bird_id]
            self.assertEqual((pigeon.x, pigeon.y), pigeon.bounds.clamp(pigeon.x, pigeon.y))
