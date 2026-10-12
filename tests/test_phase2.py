from dataclasses import asdict
import json
from pathlib import Path
import random
import tempfile
import unittest

from companion import Companion, GIFTS, PettingGesture
from desktop import Bounds, Treasure
from minigames import ShinySorting
from nest import Nest
from pigeon import Behavior, Pigeon
from storage import SaveError, Store


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.profile = Companion(traits={"curiosity": 80, "calm": 30, "sociability": 40})

    def test_feed_progression_and_inventory(self):
        self.assertTrue(self.profile.feed("seed_mix", 25))
        self.assertEqual(self.profile.friendship, 5)
        self.assertTrue(self.profile.feed("sunflower_seeds", 25))
        self.assertEqual(self.profile.food["sunflower_seeds"], 2)
        self.assertEqual(self.profile.friendship, 13)
        self.profile.food["sunflower_seeds"] = 0
        self.assertFalse(self.profile.feed("sunflower_seeds", 80))
        self.assertEqual(self.profile.friendship, 13)
        self.assertTrue(self.profile.feed("seed_mix", 0))
        self.assertEqual(self.profile.friendship, 13)
        self.profile.befriend(100)
        self.assertEqual(self.profile.friendship, 100)
        self.assertEqual(self.profile.relationship, "Best friend")

    def test_pet_cooldown_and_friendship_gifts(self):
        self.assertTrue(self.profile.pet())
        self.assertFalse(self.profile.pet())
        self.assertEqual(self.profile.friendship, 3)
        self.assertIsNone(self.profile.advance(15, random.Random(1)))
        self.assertTrue(self.profile.pet())
        self.profile.befriend(20)
        self.assertIsNone(self.profile.advance(119, random.Random(1)))
        self.assertIn(self.profile.advance(1, random.Random(1)), GIFTS)
        self.assertEqual(self.profile.gift_timer, 0)
        self.assertIsNone(self.profile.advance(1, random.Random(1)))

    def test_pet_speed_preference_and_matching_bonus(self):
        self.assertEqual(self.profile.pet_speed_preference, "quick")
        self.assertTrue(self.profile.pet("quick"))
        self.assertEqual(self.profile.friendship, 5)
        self.assertFalse(self.profile.pet("slow"))
        calm = Companion(traits={"curiosity": 10, "calm": 80, "sociability": 20})
        social = Companion(traits={"curiosity": 10, "calm": 20, "sociability": 80})
        self.assertEqual(calm.pet_speed_preference, "slow")
        self.assertEqual(social.pet_speed_preference, "steady")
        calm.evolve("play")
        calm.evolve("play")
        self.assertEqual(calm.pet_speed_preference, "slow")
        with self.assertRaises(ValueError):
            social.pet("too fast")

    def test_mouse_gesture_recognizes_two_strokes_at_their_pace(self):
        gesture = PettingGesture()
        samples = ((10, 0), (40, .2), (70, .4), (40, .6), (10, .8), (40, 1))
        result = None
        for x, now in samples:
            result = gesture.move(x, now)
        self.assertEqual(result, "steady")
        self.assertIsNone(gesture.move(10, 1.2))

    def test_personality_influences_roaming_pause(self):
        self.assertEqual(self.profile.personality, "Shiny explorer")
        waits = []
        for calm in (0, 100):
            profile = Companion(traits={"curiosity": 80, "calm": calm, "sociability": 40})
            pigeon = Pigeon(Bounds(0, 0, 800, 600), (600, 400),
                            rng=random.Random(2), companion=profile)
            pigeon.behavior = Behavior.ROAMING
            pigeon.destination = (pigeon.x, pigeon.y)
            pigeon.step(0.1)
            waits.append(pigeon.wait)
        self.assertGreater(waits[1], waits[0])

    def test_developer_movement_scale_changes_flight_speed(self):
        normal, fast = (
            Pigeon(Bounds(0, 0, 800, 600), (600, 400)),
            Pigeon(Bounds(0, 0, 800, 600), (600, 400)),
        )
        for bird in (normal, fast):
            bird.behavior = Behavior.ROAMING
            bird.destination = (700, 300)
        fast.movement_scale = 2
        normal.step(0.033)
        fast.step(0.033)
        self.assertAlmostEqual(fast.x - 400, (normal.x - 400) * 2)

    def test_game_reward_is_once_and_requires_winning_score(self):
        for correct_count in range(6):
            game = ShinySorting(random.Random(2))
            self.assertIsNone(game.claim_reward())
            for index in range(5):
                kind = game.current[1]
                if index >= correct_count:
                    kind = "Fragment" if kind == "Treasure" else "Treasure"
                game.answer(kind)
            self.assertEqual(game.score, correct_count)
            score = game.claim_reward()
            self.assertEqual(score, correct_count if correct_count >= 3 else None)
            self.assertIsNone(game.claim_reward())
            self.assertFalse(game.answer("Treasure"))
        self.profile.reward_game(5)
        self.assertEqual(self.profile.games_won, 1)
        self.assertEqual(self.profile.friendship, 5)
        self.assertEqual(self.profile.food["sunflower_seeds"], 5)
        self.assertEqual(self.profile.food["golden_corn"], 4)
        with self.assertRaises(ValueError):
            self.profile.reward_game(2)


class Phase2StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))

    def test_version1_migrates_hunger_and_items_on_next_save(self):
        old = {"version": 1, "hunger": 62, "items": [
            {"id": "original", "name": "Shiny button", "kind": "Treasure",
             "collected_at": "2026-10-11T18:00:00+00:00"}]}
        self.store.path.write_text(json.dumps(old))
        original = self.store.path.read_text()
        hunger, nest = self.store.load()
        self.assertEqual(self.store.path.read_text(), original)
        self.assertEqual(hunger, 62)
        self.assertEqual(nest.items[0].id, "original")
        self.assertEqual(nest.companion.friendship, 0)
        nest.companion.befriend(25)
        nest.collect(Treasure(GIFTS[0], "Gift", "#e6ad24", 0, 0))
        self.store.save(hunger, nest)
        self.assertEqual(json.loads(self.store.path.read_text())["version"], 6)
        self.assertEqual(self.store.load(), (hunger, nest))

    def test_invalid_phase2_data_is_preserved(self):
        self.store.save(25, Nest())
        data = json.loads(self.store.path.read_text())
        for field, value in (("friendship", True), ("friendship", 101),
                             ("traits", {}), ("food", {"seed_mix": 4}),
                             ("gift_timer", float("nan")), ("pet_cooldown", -1),
                             ("games_won", "one")):
            modified = json.loads(json.dumps(data))
            modified["companion"][field] = value
            raw = json.dumps(modified)
            self.store.path.write_text(raw)
            with self.assertRaises(SaveError):
                self.store.load()
            self.assertEqual(self.store.path.read_text(), raw)
        profile = asdict(Companion())
        del profile["traits"]
        with self.assertRaises(ValueError):
            Companion.from_data(profile)
