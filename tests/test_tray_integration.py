"""Persistent pantry interactions and cosmetic effects without a Tk window."""

import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

try:
    import tkinter as tk
except ImportError:
    tk = None

from pigeon import Behavior


@unittest.skipIf(tk is None, "Tkinter is required")
class TrayIntegrationTests(unittest.TestCase):
    def setUp(self):
        from app import DesktopPigeonApp

        self.app = DesktopPigeonApp.__new__(DesktopPigeonApp)
        self.app.closed = False
        self.app.paused = False
        self.app.drag_item = None
        self.app.drag_widget = None
        self.app.pigeons = {
            "one": SimpleNamespace(x=10, y=20),
            "two": SimpleNamespace(x=100, y=200),
        }
        self.app.flock = SimpleNamespace(
            selected_id="one", selected=SimpleNamespace(name="First"))
        self.app.play_effects = {"one": 0.0, "two": 0.0}
        self.app.paper_tears = {"one": [], "two": []}
        self.app.tear_searches = {"one": None, "two": None}
        self.app.treasure_interval = 30
        self.app.rng = random.Random(4)
        self.app.activity_status = ""
        self.app.social = SimpleNamespace(start_foraging=Mock(return_value=False))
        self.app.render = Mock()
        self.app.feed = Mock()
        self.app.select_bird = Mock(side_effect=self.select_bird)

    def select_bird(self, bird_id, show=False):
        self.app.flock.selected_id = bird_id
        self.app.flock.selected = SimpleNamespace(name="Second")
        return True

    def test_food_drop_selects_target_and_uses_existing_feed(self):
        self.assertTrue(self.app.drop_from_tray("sunflower_seeds", 110, 210))
        self.app.select_bird.assert_called_once_with("two")
        self.app.feed.assert_called_once_with("sunflower_seeds")

    def test_drop_outside_bird_and_while_paused_does_nothing(self):
        self.assertFalse(self.app.drop_from_tray("seed_mix", 500, 500))
        self.app.paused = True
        self.assertFalse(self.app.drop_from_tray("seed_mix", 20, 30))
        self.app.feed.assert_not_called()

    def test_feather_drop_is_cosmetic_and_play_effect_expires(self):
        self.assertTrue(self.app.drop_from_tray("feather", 110, 210))
        self.assertEqual(self.app.play_effects["two"], 2.0)
        self.app._advance_cosmetics("two", SimpleNamespace(behavior=Behavior.ROAMING), 2.0)
        self.assertEqual(self.app.play_effects["two"], 0.0)
        self.app.feed.assert_not_called()

    def test_item_search_waits_for_tear_then_rolls_once(self):
        from unittest.mock import patch

        record = SimpleNamespace(
            id="one", name="First", forage_timer=0,
            companion=SimpleNamespace(traits={"curiosity": 50}))
        pigeon = SimpleNamespace(
            treasure=None, behavior=Behavior.IDLE, bounds=object(), x=10, y=20,
            investigate=Mock(return_value=True))
        self.app.rng.random = Mock(return_value=0.1)
        target = object()
        with patch("app.make_treasure", return_value=target) as make_treasure:
            self.app._advance_forage(record, pigeon, 0.25, False)
            self.assertEqual(len(self.app.paper_tears["one"]), 1)
            self.assertEqual(self.app.tear_searches["one"], 0.5)
            make_treasure.assert_not_called()
            pigeon.investigate.assert_not_called()

            self.app._advance_forage(record, pigeon, 0.25, False)
            self.assertEqual(self.app.tear_searches["one"], 0.25)
            pigeon.investigate.assert_not_called()
            self.app._advance_forage(record, pigeon, 0.25, False)
            make_treasure.assert_called_once()
            pigeon.investigate.assert_called_once_with(target)
        self.assertIn("after tearing", self.app.activity_status)
        self.assertIsNone(self.app.tear_searches["one"])
        self.assertGreater(record.forage_timer, 0)

    def test_failed_search_still_requires_next_tear(self):
        record = SimpleNamespace(
            id="one", name="First", forage_timer=0,
            companion=SimpleNamespace(traits={"curiosity": 50}))
        pigeon = SimpleNamespace(treasure=None, behavior=Behavior.IDLE)
        self.app.rng.random = Mock(return_value=0.9)
        self.app._advance_forage(record, pigeon, 0.25, False)
        self.app._advance_forage(record, pigeon, 0.5, False)
        self.assertEqual(len(self.app.paper_tears["one"]), 1)
        self.assertIsNone(self.app.tear_searches["one"])
        self.assertGreater(record.forage_timer, 0)
        self.app.rng.random.assert_called_once_with()

    def test_no_search_while_not_idle_and_smoothing_clears_all(self):
        record = SimpleNamespace(
            id="one", name="First", forage_timer=0,
            companion=SimpleNamespace(traits={"curiosity": 50}))
        pigeon = SimpleNamespace(treasure=None, behavior=Behavior.ROAMING)
        self.app._advance_forage(record, pigeon, 1, False)
        self.assertEqual(self.app.paper_tears["one"], [])
        self.assertIsNone(self.app.tear_searches["one"])
        self.app.smooth_tears()
        self.assertEqual(self.app.paper_tears, {"one": [], "two": []})

    def test_sprite_draws_paper_tears_and_feather_play(self):
        from desktop import Bounds
        from pigeon import Pigeon
        from ui.pigeon_sprite import draw_pigeon

        canvas = Mock()
        pigeon = Pigeon(Bounds(0, 0, 800, 600), (20, 20))
        draw_pigeon(canvas, pigeon, 0, False,
                    paper_tears=[{"x": 20, "y": 50, "age": 1, "angle": 0.2}],
                    feather_playing=True)
        self.assertGreaterEqual(canvas.create_polygon.call_count, 4)
        canvas.create_line.assert_any_call(
            80, 52, 73, 70, fill="#785785", width=2)


if __name__ == "__main__":
    unittest.main()
