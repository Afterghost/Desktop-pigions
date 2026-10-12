import random
import unittest

import config
from pigeon import Pigeon, MAX_ITEMS, MAX_TEARS, TEAR_LIFETIME, EAT_DURATION, PLAY_DURATION


class PigeonTests(unittest.TestCase):
    def make_bird(self):
        return Pigeon(800, 600, random.Random(42))

    def test_food_rewards_once_for_each_configured_food(self):
        for kind, values in config.FOOD_TYPES.items():
            with self.subTest(kind=kind):
                bird = self.make_bird()
                self.assertTrue(bird.place(kind, bird.x, bird.y))
                bird.update(0.01)
                self.assertEqual(bird.state, "eating")
                self.assertEqual(bird.hunger, 45)
                bird.update(EAT_DURATION)
                self.assertEqual(bird.hunger, 45 - values["hunger_reduction"])
                self.assertEqual(bird.friendship, values["friendship"])
                self.assertEqual(bird.items, [])
                bird.update(0.1)
                self.assertEqual(bird.friendship, values["friendship"])

    def test_hunger_bounds_and_elapsed_ticks(self):
        bird = self.make_bird()
        bird.hunger = 99
        bird.update(config.HUNGER_TICK_INTERVAL / 1000 * 3)
        self.assertEqual(bird.hunger, config.HUNGER_MAX)
        bird = self.make_bird()
        bird.hunger = 1
        bird.place("golden_corn", bird.x, bird.y)
        bird.update(0.01)
        bird.update(EAT_DURATION)
        self.assertEqual(bird.hunger, 0)

    def test_movement_is_independent_of_frame_rate(self):
        first, second = self.make_bird(), self.make_bird()
        for bird in (first, second):
            bird.place("seed_mix", 700, 300)
        first.update(1)
        for _ in range(100):
            second.update(0.01)
        self.assertAlmostEqual(first.x, second.x)
        self.assertAlmostEqual(first.y, second.y)
        self.assertAlmostEqual(first.x, 400 + first.speed)

    def test_feather_is_played_with_and_consumed_without_food_rewards(self):
        bird = self.make_bird()
        bird.place("feather", bird.x, bird.y)
        bird.update(0.01)
        self.assertEqual(bird.state, "playing")
        bird.update(PLAY_DURATION)
        self.assertEqual(bird.hunger, 45)
        self.assertEqual(bird.friendship, 0)
        self.assertEqual(bird.items, [])

    def test_food_has_priority_over_feather(self):
        bird = self.make_bird()
        bird.place("feather", bird.x, bird.y)
        bird.place("seed_mix", bird.x + 100, bird.y)
        bird.update(0.1)
        self.assertEqual(bird.target.kind, "seed_mix")

    def test_invalid_placements_and_item_limit(self):
        bird = self.make_bird()
        for kind, x, y in (("unknown", 50, 50), ("seed_mix", -1, 50),
                            ("seed_mix", 800, 50), ("feather", 50, 600)):
            self.assertFalse(bird.place(kind, x, y))
        for _ in range(MAX_ITEMS):
            self.assertTrue(bird.place("seed_mix", 50, 50))
        self.assertFalse(bird.place("feather", 50, 50))
        self.assertEqual(len(bird.items), MAX_ITEMS)

    def test_tears_bounded_expiring_and_reversible(self):
        bird = self.make_bird()
        for _ in range(MAX_TEARS * 4):
            bird.state = "idle"
            bird.destination = None
            bird.idle_time = 0
            bird.update(0.01)
            self.assertLessEqual(len(bird.tears), MAX_TEARS)
        self.assertTrue(bird.tears)
        bird.update(TEAR_LIFETIME)
        self.assertEqual(bird.tears, [])
        bird.idle_time = 100
        bird.state = "idle"
        for _ in range(30):
            bird.idle_time = 0
            bird.update(0.01)
            if bird.tears:
                break
            bird.destination = None
        self.assertTrue(bird.tears)
        bird.clear_effects()
        self.assertEqual(bird.tears, [])
        self.assertEqual(bird.state, "idle")

    def test_resize_clamps_pigeon_items_and_destination(self):
        bird = self.make_bird()
        bird.place("feather", 750, 550)
        bird.destination = (700, 500)
        bird.resize(100, 80)
        for x, y in ((bird.x, bird.y), (bird.items[0].x, bird.items[0].y), bird.destination):
            self.assertTrue(0 <= x < 100)
            self.assertTrue(0 <= y < 80)

    def test_nonpositive_update_is_noop(self):
        bird = self.make_bird()
        bird.update(0)
        bird.update(-1)
        self.assertEqual(bird.clock, 0)
        self.assertEqual(bird.hunger, 45)


if __name__ == "__main__":
    unittest.main()
