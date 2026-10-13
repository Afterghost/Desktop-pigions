from dataclasses import asdict
import copy
from itertools import combinations
import json
from pathlib import Path
import tempfile
import unittest

from chronicle import RECENT_LIMIT
from companion import Companion
from desktop import Bounds, Treasure
from flock import Flock
from nest import Nest
from pigeon import Pigeon, Behavior
from social import BOND_LIMIT, SocialMotion
from storage import Store, SaveError


def family():
    flock = Flock.initial(Companion(traits=dict.fromkeys(("curiosity", "calm", "sociability"), 70)))
    flock.level = 1
    flock.lay(flock.selected_id)
    flock.advance(60)
    return flock


class SocialTests(unittest.TestCase):
    def test_mutual_bonds_no_human_reward_inactive_and_return_persist(self):
        flock = family()
        a, b = flock.active
        human = a.companion.friendship
        for _ in range(4):
            flock.advance(30)
        bond = flock.bond(a.id, b.id)
        self.assertIs(bond, flock.bond(b.id, a.id))
        self.assertEqual(bond.status, "Friendship")
        self.assertEqual(a.companion.friendship, human)
        b.companion.progression.advance(360, 100)
        flock.depart(b)
        before = asdict(bond)
        flock.advance(300)
        self.assertEqual(asdict(bond), before)
        legacy = asdict(b.legacy)
        flock.rejoin(b.id)
        flock.advance(30)
        self.assertEqual(len(flock.bonds), 1)
        self.assertGreater(bond.meetings, before["meetings"])
        self.assertEqual(asdict(b.legacy), legacy)
        self.assertEqual(Flock.from_data(asdict(flock)), flock)

    def test_personality_rivalry_and_reconciliation_are_observed(self):
        flock = family()
        a, b = flock.active
        a.companion.traits = dict.fromkeys(a.companion.traits, 0)
        b.companion.traits = dict.fromkeys(b.companion.traits, 100)
        for _ in range(5):
            flock.advance(30)
        bond = flock.bond(a.id, b.id)
        self.assertEqual(bond.status, "Rivalry")
        a.companion.traits = dict(b.companion.traits)
        for _ in range(15):
            flock.advance(30)
        self.assertEqual(bond.status, "Friendship")
        self.assertTrue({"rivalry", "reconciliation", "friendship"} <=
                        {e.kind for e in flock.chronicle.core})
        for _ in range(50):
            flock.advance(30)
        self.assertLessEqual(bond.affinity, 100)

    def test_explicit_bond_cap_preserves_old_pairs(self):
        flock = family()
        original = flock.bonds[0]
        child = flock.active[1]
        child.companion.progression.advance(360, 100)
        flock.depart(child)
        for _ in range(24):
            flock.lay()
            child = flock.advance(60)[0]
            child.companion.progression.advance(360, 100)
            flock.depart(child)
        for a, b in combinations(flock.records, 2):
            flock.bond(a.id, b.id, create=True)
        self.assertEqual(len(flock.bonds), BOND_LIMIT)
        self.assertIs(flock.bond(*original.actors), original)
        self.assertEqual(len(Flock.from_data(asdict(flock)).bonds), BOND_LIMIT)

    def test_deterministic_hatch_snapshot_filters_and_permanent_history(self):
        flock = family()
        a, b = flock.active
        hatch = next(e for e in flock.chronicle.core if e.kind == "hatch")
        text = flock.chronicle.prose(hatch, flock)
        self.assertIn(a.name, text)
        self.assertIn("generation 2", text)
        self.assertIn("curiosity 60", text)
        b.companion.traits["curiosity"] = 99
        self.assertEqual(flock.chronicle.prose(hatch, flock), text)
        self.assertEqual(flock.chronicle.family_ids(flock, b.id, "Ancestors"), {a.id, b.id})
        self.assertEqual(flock.chronicle.family_ids(flock, b.id, "Descendants"), {b.id})
        self.assertEqual(flock.chronicle.family_ids(flock, b.id, "Lineage"), {a.id, b.id})
        core = copy.deepcopy(flock.chronicle.core)
        for _ in range(100):
            flock.chronicle.record("foraging", sorted([a.id, b.id]), permanent=False)
        self.assertEqual(flock.chronicle.core, core)
        self.assertEqual(len(flock.chronicle.recent), RECENT_LIMIT)
        for bird in flock.active:
            bird.companion.progression.advance(360, 100)
            flock.depart(bird)
        loaded = Flock.from_data(asdict(flock))
        self.assertEqual(loaded.active, [])
        self.assertIn(text, [loaded.chronicle.prose(e, loaded) for e in loaded.chronicle.core])

    def test_collaboration_movement_protection_and_timeout_cancel(self):
        flock = family()
        a, b = flock.active
        flock.bond(a.id, b.id).affinity = 40
        bounds = Bounds(-100, -50, 800, 600)
        pigeons = {bird.id: Pigeon(bounds, (500, 400), companion=bird.companion)
                   for bird in flock.active}
        motion = SocialMotion()
        target = Treasure("Blue marble", "Treasure", "#abc", 200, 200)
        b.companion.progression.protected = ["Treasure"]
        motion.start(flock, pigeons, lambda pigeon: target)
        self.assertIsNone(motion.collaboration)
        b.companion.progression.protected = []
        motion.start(flock, pigeons, lambda pigeon: target)
        self.assertIsNotNone(motion.collaboration)
        follower = pigeons[motion.collaboration.partner]
        follower.x, follower.y = bounds.x, bounds.y
        before = follower.x, follower.y
        motion.advance(.2, flock, pigeons)
        self.assertNotEqual((follower.x, follower.y), before)
        self.assertEqual((follower.x, follower.y), bounds.clamp(follower.x, follower.y))
        leader = pigeons[motion.collaboration.leader]
        leader.cancel_theft()
        motion.advance(.1, flock, pigeons)
        self.assertIsNone(motion.collaboration)
        motion.start(flock, pigeons, lambda pigeon: target)
        motion.advance(31, flock, pigeons)
        motion.advance(.1, flock, pigeons)
        self.assertIsNone(motion.collaboration)
        self.assertIsNone(leader.treasure)

    def test_automatic_shared_find_can_start_only_from_tear_search(self):
        flock = family()
        a, b = flock.active
        flock.bond(a.id, b.id).affinity = 40
        bounds = Bounds(-100, -50, 800, 600)
        pigeons = {bird.id: Pigeon(bounds, (500, 400), companion=bird.companion)
                   for bird in flock.active}
        motion = SocialMotion()
        target = Treasure("Blue marble", "Treasure", "#abc", 200, 200)
        motion.start(flock, pigeons, lambda pigeon: target, allow_foraging=False)
        self.assertIsNone(motion.collaboration)
        self.assertTrue(motion.start_foraging(
            a.id, flock, pigeons, lambda pigeon: target))
        self.assertEqual(motion.collaboration.leader, a.id)
        self.assertIs(pigeons[a.id].treasure, target)

    def test_rival_yielding_has_no_inventory_or_hunger_reward(self):
        flock = family()
        flock.bonds[0].affinity = -40
        bounds = Bounds(0, 0, 800, 600)
        pigeons = {b.id: Pigeon(bounds, (500, 400), companion=b.companion) for b in flock.active}
        motion = SocialMotion()
        motion.start(flock, pigeons, lambda p: None)
        yielding = pigeons[motion.avoidance[0]]
        before = yielding.x, yielding.y
        motion.advance(.2, flock, pigeons)
        self.assertNotEqual((yielding.x, yielding.y), before)
        self.assertEqual(yielding.hunger, 25)
        self.assertIsNone(yielding.treasure)
        motion.advance(5, flock, pigeons)
        motion.advance(.1, flock, pigeons)
        self.assertIsNone(motion.avoidance)
        motion.start(flock, pigeons, lambda p: None)
        departed = flock.active[0]
        departed.companion.progression.advance(360, 100)
        flock.depart(departed)
        before = [(p.x, p.y) for p in pigeons.values()]
        motion.advance(.1, flock, pigeons)
        self.assertIsNone(motion.avoidance)
        self.assertEqual([(p.x, p.y) for p in pigeons.values()], before)


class StoryStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent)
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name))

    def test_v4_preserves_profiles_eggs_legacy_without_invented_milestones(self):
        flock = family()
        a, b = flock.active
        a.companion.reward_game(5)
        b.companion.progression.advance(360, 100)
        flock.depart(b)
        flock.lay(a.id)
        nest = Nest(companion=a.companion, flock=flock)
        self.store.save(a.hunger, nest)
        data = json.loads(self.store.path.read_text())
        data["version"] = 4
        data["flock"].pop("bonds")
        data["flock"].pop("chronicle")
        data["companion"].pop("pet_preference")
        data["companion"].pop("outfit")
        data["companion"].pop("appeal_preference")
        for bird in data["flock"]["records"]:
            bird["companion"].pop("pet_preference")
            bird["companion"].pop("outfit")
            bird["companion"].pop("appeal_preference")
        raw = json.dumps(data)
        self.store.path.write_text(raw)
        hunger, migrated = self.store.load()
        self.assertEqual(self.store.path.read_text(), raw)
        for restored, original in zip(migrated.flock.records, flock.records):
            original.companion.pet_preference = restored.companion.pet_preference
            original.companion.outfit = restored.companion.outfit
            original.companion.appeal_preference = restored.companion.appeal_preference
        self.assertEqual(migrated.flock.records, flock.records)
        self.assertEqual(migrated.flock.eggs, flock.eggs)
        self.assertEqual({e.kind for e in migrated.flock.chronicle.core}, {"origins", "egg_origins"})
        self.store.save(hunger, migrated)
        self.assertEqual(self.store.load(), (hunger, migrated))
        migrated.flock.advance(60)
        self.assertEqual(Flock.from_data(asdict(migrated.flock)), migrated.flock)

    def test_strict_bonds_events_and_read_only_original(self):
        flock = family()
        nest = Nest(companion=flock.selected.companion, flock=flock)
        self.store.save(25, nest)
        base = json.loads(self.store.path.read_text())
        mutations = []
        for field, value in (("actors", [flock.selected_id] * 2), ("actors", ["missing", "missing2"]),
                             ("affinity", True), ("affinity", -101), ("meetings", -1)):
            data = copy.deepcopy(base)
            data["flock"]["bonds"][0][field] = value
            mutations.append(data)
        data = copy.deepcopy(base)
        data["flock"]["bonds"] *= 2
        mutations.append(data)
        for field, value in (("actors", ["missing"]), ("kind", "fiction"), ("id", "bad"),
                             ("traits", {"curiosity": float("nan")}), ("actors", [True])):
            data = copy.deepcopy(base)
            data["flock"]["chronicle"]["core"][0][field] = value
            mutations.append(data)
        data = copy.deepcopy(base)
        data["flock"]["chronicle"]["core"].append(data["flock"]["chronicle"]["core"][0])
        mutations.append(data)
        data = copy.deepcopy(base)
        data["flock"]["chronicle"]["core"] = []
        mutations.append(data)
        data = copy.deepcopy(base)
        data["flock"]["chronicle"]["recent"].append(data["flock"]["chronicle"]["recent"][0])
        mutations.append(data)
        for data in mutations:
            raw = json.dumps(data)
            self.store.path.write_text(raw)
            store = Store(self.store.directory)
            with self.assertRaises(SaveError):
                store.load()
            with self.assertRaises(SaveError):
                store.save(25, nest)
            self.assertEqual(self.store.path.read_text(), raw)
