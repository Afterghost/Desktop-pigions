import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from config import MAX_STORED_ITEMS
from desktop import Bounds, Treasure, make_treasure
from feeding import advance_hunger, feed, hunger_state
from nest import Nest
from pigeon import Behavior, Pigeon
from storage import SaveError, Store


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.bounds = Bounds(-100, 20, 800, 600)
        self.pigeon = Pigeon(self.bounds, (550, 480), rng=random.Random(4))
        self.shiny = Treasure("Silver foil fragment", "Fragment", "#cbd4df", 200, 200)

    def test_roaming_stays_in_bounds_and_moves(self):
        start = (self.pigeon.x, self.pigeon.y)
        for _ in range(600):
            self.pigeon.step(0.1)
            self.assertEqual((self.pigeon.x, self.pigeon.y),
                             self.bounds.clamp(self.pigeon.x, self.pigeon.y))
        self.assertNotEqual(start, (self.pigeon.x, self.pigeon.y))

    def test_tiny_work_area_and_target_clamping(self):
        bounds = Bounds(0, 0, 30, 30)
        pigeon = Pigeon(bounds, (500, 500), rng=random.Random(1))
        for _ in range(200):
            pigeon.step(0.1)
        self.assertEqual((pigeon.x, pigeon.y), (0, 0))
        treasure = make_treasure(bounds, 20, 20, random.Random(1))
        self.assertEqual((treasure.x, treasure.y), (0, 0))

    def test_collection_runs_all_stages_once(self):
        self.assertTrue(self.pigeon.investigate(self.shiny))
        self.assertFalse(self.pigeon.investigate(self.shiny))
        states, collected = set(), []
        for _ in range(600):
            states.add(self.pigeon.behavior)
            item = self.pigeon.step(0.1)
            if item:
                collected.append(item)
        self.assertEqual(collected, [self.shiny])
        self.assertTrue({Behavior.INVESTIGATING, Behavior.APPROACHING, Behavior.THEFT,
                         Behavior.ESCAPING, Behavior.STORING}.issubset(states))
        self.assertIsNone(self.pigeon.treasure)
        self.assertFalse(self.pigeon.carrying)

    def test_elapsed_time_not_frame_count_controls_hunger_and_movement(self):
        a = Pigeon(self.bounds, (550, 480), rng=random.Random(1))
        b = Pigeon(self.bounds, (550, 480), rng=random.Random(1))
        for pigeon in (a, b):
            pigeon.behavior = Behavior.ROAMING
            pigeon.destination = (600, 400)
        a.step(0.5)
        for _ in range(5):
            b.step(0.1)
        self.assertAlmostEqual(a.x, b.x)
        self.assertAlmostEqual(a.hunger, b.hunger)
        for seconds in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                a.step(seconds)

    def test_feeding_hunger_bounds_and_labels(self):
        self.assertEqual(advance_hunger(99, 500), 100)
        self.assertEqual(advance_hunger(20, 5), 21)
        self.assertEqual(feed(5, "seed_mix"), 0)
        self.assertEqual(feed(80, "sunflower_seeds"), 60)
        for value, label in ((0, "Full"), (20, "Full"), (20.5, "Content"),
                             (40, "Content"), (41, "Hungry"),
                             (71, "Very Hungry"), (91, "Angry")):
            self.assertEqual(hunger_state(value), label)
        self.pigeon.hunger = 80
        self.pigeon.feed("sunflower_seeds")
        self.assertEqual(self.pigeon.hunger_label, "Hungry")
        self.assertGreater(self.pigeon.fed_for, 0)
        with self.assertRaises(KeyError):
            self.pigeon.feed("unknown")

    def test_nest_keeps_bounded_treasures_and_fragments(self):
        nest = Nest()
        for _ in range(MAX_STORED_ITEMS + 2):
            nest.collect(self.shiny)
        self.assertEqual(len(nest.items), MAX_STORED_ITEMS)
        self.assertEqual(nest.items[-1].kind, "Fragment")
        self.assertEqual(len({item.id for item in nest.items}), MAX_STORED_ITEMS)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(Path(self.temporary.name) / "DesktopPigeon")

    def test_default_and_roundtrip_without_touching_other_files(self):
        unrelated = Path(self.temporary.name) / "user.txt"
        unrelated.write_text("untouched")
        hunger, nest = self.store.load()
        self.assertEqual(hunger, 25)
        self.assertEqual(nest.items, [])
        nest.collect(Treasure("Shiny button", "Treasure", "#f6c453", 0, 0))
        self.store.save(65.5, nest)
        self.assertEqual(self.store.load(), (65.5, nest))
        self.assertEqual(unrelated.read_text(), "untouched")
        self.assertEqual(list(self.store.directory.iterdir()), [self.store.path])
        self.assertNotIn('"x"', self.store.path.read_text())

    def test_invalid_saves_are_preserved(self):
        self.store.directory.mkdir()
        for content in ('{broken', '[]', '{"version":2}', json.dumps({
                "version": 1, "hunger": -1, "items": []}),
                '{"version":1,"hunger":NaN,"items":[]}',
                '{"version":1,"hunger":true,"items":[]}'):
            self.store.path.write_text(content)
            with self.assertRaises(SaveError):
                self.store.load()
            self.assertEqual(self.store.path.read_text(), content)

    def test_failed_atomic_replace_keeps_previous_save_and_cleans_temp(self):
        self.store.save(20, Nest())
        original = self.store.path.read_text()
        with patch("storage.os.replace", side_effect=PermissionError):
            with self.assertRaises(SaveError):
                self.store.save(50, Nest())
        self.assertEqual(self.store.path.read_text(), original)
        self.assertEqual(list(self.store.directory.iterdir()), [self.store.path])

    def test_cleanup_permission_error_does_not_mask_save_error(self):
        self.store.save(20, Nest())
        with patch("storage.os.replace", side_effect=PermissionError):
            with patch("storage.Path.unlink", side_effect=PermissionError):
                with self.assertRaises(SaveError):
                    self.store.save(50, Nest())
        self.assertEqual(self.store.load()[0], 20)


if __name__ == "__main__":
    unittest.main()
