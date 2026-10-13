from dataclasses import asdict
import json
from pathlib import Path
import random
import tempfile
import unittest

from companion import Companion, GIFTS
from desktop import Bounds, Treasure
from minigames import LocalGame, ShinySorting
from nest import Nest
from pigeon import Pigeon
from progression import GAME_NAMES, Progression
from storage import Store, SaveError


def winning_choice(game):
    if isinstance(game, ShinySorting) and not isinstance(game, LocalGame):
        return game.current[1]
    if game.name in ("Peck Finder", "Follow Crumb Trail"):
        return str(game.current)
    if game.name == "Pigeon Memory":
        return game.current
    if game.name == "Rooftop Dash":
        return {"Gap": "Jump", "Wire": "Duck", "Clear": "Run"}[game.current]
    if game.name == "Human Inspection":
        return {"Open palm with seeds": "Approach", "Typing at a desk": "Wait",
                "Waving a broom": "Retreat"}[game.current]
    return "Rest" if game.energy < 2 else "Search"


class GameTests(unittest.TestCase):
    def make_game(self, name):
        return ShinySorting(random.Random(1)) if name == GAME_NAMES[0] else LocalGame(name, random.Random(1))

    def test_every_game_wins_once_fails_and_cancels_without_reward(self):
        for name in GAME_NAMES:
            for outcome in ("win", "fail", "cancel"):
                with self.subTest(name=name, outcome=outcome):
                    game = self.make_game(name)
                    self.assertIsNone(game.claim_reward())
                    if isinstance(game, LocalGame):
                        game.hide_memory()
                    if outcome == "cancel":
                        game.answer(winning_choice(game))
                        game.cancel()
                    else:
                        while not game.complete:
                            correct = winning_choice(game)
                            options = game.choices if isinstance(game, LocalGame) else ("Treasure", "Fragment")
                            game.answer(correct if outcome == "win" else next(v for v in options if v != correct))
                    self.assertEqual(game.claim_reward(), 5 if outcome == "win" else None)
                    self.assertIsNone(game.claim_reward())
                    self.assertFalse(game.answer("Treasure" if name == GAME_NAMES[0] else game.choices[0]))

    def test_memory_requires_hiding_and_foraging_manages_energy(self):
        memory = LocalGame("Pigeon Memory", random.Random(4))
        self.assertIn("Remember:", memory.prompt)
        self.assertFalse(memory.answer(memory.current))
        self.assertEqual(memory.index, 0)
        memory.hide_memory()
        self.assertNotIn("Remember:", memory.prompt)
        self.assertTrue(memory.answer(memory.current))
        forage = LocalGame("Daily Foraging")
        forage.answer("Search")
        forage.answer("Search")
        self.assertEqual(forage.energy, 0)
        self.assertFalse(forage.answer("Search"))
        self.assertEqual(forage.energy, 0)
        self.assertTrue(forage.answer("Rest"))
        self.assertEqual(forage.energy, 3)


class ProgressionTests(unittest.TestCase):
    def test_evolution_hybrid_and_bounded_nonrepeatable_reputation(self):
        profile = Companion(traits=dict.fromkeys(("curiosity", "calm", "sociability"), 40))
        for _ in range(5):
            profile.evolve("care")
        self.assertEqual(profile.personality, "Gentle Soul")
        self.assertEqual(profile.traits["calm"], 45)
        for _ in range(5):
            profile.reward_game(5)
        self.assertIn("Hybrid:", profile.personality)
        self.assertIn("Playful Acrobat", profile.personality)
        for _ in range(100):
            profile.evolve("care")
        reputation = profile.progression.reputation
        profile.evolve("care")
        self.assertEqual(profile.progression.reputation, reputation)
        self.assertEqual(len(profile.progression.achievements),
                         len(set(profile.progression.achievements)))

    def test_active_neglect_stages_pending_and_reconciliation(self):
        progress = Progression()
        progress.advance(100, 89)
        self.assertEqual(progress.neglect, 0)
        for seconds, stage in ((1, "Grumpy"), (59, "Bitter"), (60, "Resentful"),
                               (60, "Preparing to Leave"), (60, "Last Chance Coo")):
            progress.advance(seconds, 90)
            self.assertIn(stage, progress.neglect_stage)
        progress.advance(10_000, 100)
        self.assertEqual(progress.neglect, 240)
        self.assertTrue(progress.reconcile())
        self.assertTrue(progress.forgiven)
        self.assertFalse(progress.reconcile())
        self.assertEqual(progress.achievements, ["The Day We Made Up"])

    def test_protection_and_cancelled_target_never_collected(self):
        profile = Companion()
        pigeon = Pigeon(Bounds(0, 0, 800, 600), (500, 400), companion=profile)
        target = Treasure("Shiny button", "Treasure", "#abc", 200, 200)
        profile.progression.protected = ["Treasure"]
        self.assertFalse(pigeon.investigate(target))
        profile.progression.protected.clear()
        self.assertTrue(pigeon.investigate(target))
        for _ in range(10):
            pigeon.step(.1)
        self.assertTrue(pigeon.cancel_theft())
        self.assertFalse(pigeon.cancel_theft())
        for _ in range(200):
            self.assertIsNone(pigeon.step(.1))

    def test_selected_gift_return_is_consumed_once_and_reconciles(self):
        nest = Nest()
        item = nest.collect(Treasure(GIFTS[-1], "Gift", "#abc", 0, 0))
        nest.companion.progression.neglect = 240
        self.assertFalse(nest.return_item("missing"))
        self.assertTrue(nest.return_item(item.id))
        self.assertFalse(nest.return_item(item.id))
        self.assertEqual(nest.companion.friendship, 4)
        self.assertTrue(nest.companion.progression.forgiven)
        self.assertEqual(nest.items, [])


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name))

    def test_v1_v2_migration_preserves_items_and_traits_and_roundtrips_v3(self):
        item = {"id": "original", "name": "Blue marble", "kind": "Treasure",
                "collected_at": "2026-10-11T19:00:00+00:00"}
        old_profile = asdict(Companion(friendship=42, games_won=8,
                                      traits={"curiosity": 28, "calm": 79, "sociability": 52}))
        old_profile.pop("progression")
        old_profile.pop("pet_preference")
        old_profile.pop("outfit")
        old_profile.pop("appeal_preference")
        old_profile.pop("wardrobe")
        for version in (1, 2):
            data = {"version": version, "hunger": 93.5, "items": [item]}
            if version == 2:
                data["companion"] = old_profile
            raw = json.dumps(data)
            self.store.path.write_text(raw)
            hunger, nest = self.store.load()
            self.assertEqual(raw, self.store.path.read_text())
            self.assertEqual(self.store.load()[1].companion.traits, nest.companion.traits)
            self.assertEqual(nest.items[0].id, "original")
            if version == 2:
                self.assertEqual(nest.companion.traits, old_profile["traits"])
                self.assertEqual(nest.companion.games_won, 8)
                self.assertEqual(nest.companion.friendship, 42)
            nest.companion.progression.neglect = 240
            nest.companion.progression.protected = ["Fragment"]
            nest.companion.progression.intervention_cooldown = 7.5
            nest.companion.progression.forage_cooldown = 210
            self.store.save(hunger, nest)
            self.assertEqual(json.loads(self.store.path.read_text())["version"], 8)
            self.assertEqual((hunger, nest), self.store.load())
            nest.companion.evolve("care")
            self.store.save(hunger, nest)
            self.assertTrue(self.store.load()[1].companion.progression.forgiven)
            self.assertIn("The Day We Made Up", self.store.load()[1].companion.progression.achievements)

    def test_new_fields_corrupt_rejection_keeps_original(self):
        self.store.save(25, Nest())
        base = json.loads(self.store.path.read_text())
        mutations = (("actions", {}), ("actions", {"care": True}),
                     ("achievements", ["unknown"]), ("achievements", [["care:1"]]),
                     ("protected", ["Gift"]), ("protected", ["Treasure", "Treasure"]),
                     ("forgiven", 1), ("forgiven", True), ("neglect", -1),
                     ("neglect", float("nan")), ("neglect", 241),
                     ("intervention_cooldown", 11), ("forage_cooldown", 301))
        for key, value in mutations:
            data = json.loads(json.dumps(base))
            data["companion"]["progression"][key] = value
            raw = json.dumps(data)
            self.store.path.write_text(raw)
            with self.subTest(key=key, value=value), self.assertRaises(SaveError):
                self.store.load()
            self.assertEqual(raw, self.store.path.read_text())
        for version in (False, 8, "3"):
            base["version"] = version
            raw = json.dumps(base)
            self.store.path.write_text(raw)
            with self.assertRaises(SaveError):
                self.store.load()
            self.assertEqual(raw, self.store.path.read_text())

    def test_save_validation_does_not_replace_last_good_save(self):
        nest = Nest()
        self.store.save(25, nest)
        raw = self.store.path.read_text()
        nest.companion.progression.forage_cooldown = float("inf")
        with self.assertRaises(SaveError):
            self.store.save(25, nest)
        self.assertEqual(raw, self.store.path.read_text())
