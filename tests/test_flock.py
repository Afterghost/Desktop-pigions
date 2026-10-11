from dataclasses import asdict
import copy
import json
from pathlib import Path
import tempfile
import unittest

from companion import Companion
from flock import Flock, HISTORY_LIMIT
from nest import Nest
from progression import Progression
from storage import Store, SaveError


class FlockTests(unittest.TestCase):
    def test_grace_boundary_collect_does_not_reconcile_and_care_does(self):
        profile = Companion()
        progress = profile.progression
        progress.neglect = 239
        progress.advance(1, 100)
        self.assertEqual(progress.grace, 0)
        progress.advance(119, 100)
        profile.evolve("collect")
        self.assertEqual((progress.neglect, progress.grace), (240, 119))
        profile.evolve("govern")
        self.assertEqual(progress.grace, 119)
        profile.feed("seed_mix", 100)
        self.assertEqual((progress.neglect, progress.grace), (0, 0))
        progress.advance(360, 100)
        self.assertEqual((progress.neglect, progress.grace), (240, 120))

    def test_upgrades_hatch_inheritance_capacity_and_history_identity(self):
        flock = Flock.initial(Companion(traits={"curiosity": 80, "calm": 20, "sociability": 50}))
        parent = flock.selected
        self.assertFalse(flock.lay(parent.id))
        self.assertFalse(flock.upgrade())
        flock.treasury = 35
        for capacity in (2, 3, 5):
            self.assertTrue(flock.upgrade())
            self.assertEqual(flock.capacity, capacity)
        self.assertEqual(flock.treasury, 0)
        self.assertFalse(flock.upgrade())
        for _ in range(4):
            self.assertTrue(flock.lay(parent.id))
        self.assertFalse(flock.lay(parent.id))
        self.assertEqual(flock.advance(59), [])
        hatched = flock.advance(1)
        self.assertEqual(len(hatched), 4)
        child = hatched[0]
        self.assertEqual(child.companion.traits, {"curiosity": 65, "calm": 35, "sociability": 50})
        self.assertEqual((child.parent, child.generation), (parent.id, 2))
        parent.companion.traits["curiosity"] = 99
        self.assertEqual(child.companion.traits["curiosity"], 65)
        parent.companion.progression.advance(360, 100)
        parent.lifetime = 360
        self.assertTrue(flock.depart(parent))
        original = asdict(parent.legacy)
        self.assertEqual(len(flock.active), 4)
        self.assertTrue(flock.rejoin(parent.id))
        self.assertFalse(flock.rejoin(parent.id))
        self.assertEqual(asdict(parent.legacy), original)
        self.assertEqual(len({b.id for b in flock.active}), 5)
        self.assertEqual(Flock.from_data(asdict(flock)), flock)

    def test_mentoring_is_bounded_no_neglect_reconciliation(self):
        flock = Flock.initial(Companion())
        flock.level = 1
        flock.lay(flock.selected_id)
        flock.advance(60)
        elder, child = flock.active
        elder.lifetime = 100
        elder.companion.progression.neglect = 240
        calm = child.companion.traits["calm"]
        flock.advance(30)
        self.assertGreater(child.companion.traits["calm"], calm)
        self.assertEqual(elder.companion.progression.neglect, 240)
        self.assertGreater(flock.interactions, 0)
        child.companion.friendship = 100
        child.companion.traits["calm"] = 100
        flock.advance(30)
        self.assertEqual(child.companion.friendship, 100)
        self.assertEqual(child.companion.traits["calm"], 100)

    def test_history_limit_refuses_without_pruning(self):
        flock = Flock.initial(Companion())
        flock.level = 3
        for _ in range(HISTORY_LIMIT - 1):
            self.assertTrue(flock.lay())
            bird = flock.advance(60)[0]
            bird.companion.progression.advance(360, 100)
            flock.depart(bird)
        ids = [b.id for b in flock.records]
        self.assertFalse(flock.lay())
        self.assertEqual(ids, [b.id for b in flock.records])
        self.assertEqual(len(Flock.from_data(asdict(flock)).records), HISTORY_LIMIT)


class FlockStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent)
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name))

    def test_all_old_versions_preserve_profile_hunger_and_items(self):
        profile = asdict(Companion(friendship=47))
        for version in (1, 2, 3):
            data = {"version": version, "hunger": 97, "items": []}
            if version >= 2:
                legacy = copy.deepcopy(profile)
                if version == 2:
                    legacy.pop("progression")
                else:
                    legacy["progression"].pop("grace")
                data["companion"] = legacy
            raw = json.dumps(data)
            self.store.path.write_text(raw)
            hunger, nest = self.store.load()
            self.assertEqual(self.store.path.read_text(), raw)
            self.assertEqual(len(nest.flock.active), 1)
            self.assertEqual(nest.flock.selected.hunger, 97)
            self.assertIs(nest.companion, nest.flock.selected.companion)
            if version >= 2:
                self.assertEqual(nest.companion.friendship, 47)
                self.assertEqual(nest.companion.traits, profile["traits"])
            self.store.save(hunger, nest)
            self.assertEqual(json.loads(self.store.path.read_text())["version"], 4)
            self.assertEqual(self.store.load(), (hunger, nest))

    def test_corrupt_flock_fields_and_references_disable_saving(self):
        nest = Nest()
        self.store.save(25, nest)
        base = json.loads(self.store.path.read_text())
        bad_flocks = []
        for key, value in (("level", True), ("level", 4), ("treasury", -1),
                           ("treasury", True), ("selected_id", "missing"),
                           ("records", []), ("records", [None]), ("eggs", [None]),
                           ("social_timer", float("nan")), ("interactions", True)):
            flock = copy.deepcopy(base["flock"])
            flock[key] = value
            bad_flocks.append(flock)
        for key, value in (("id", False), ("id", "bad"), ("name", ""),
                           ("parent", "missing"), ("parent", []), ("generation", True),
                           ("generation", 2), ("status", "gone"), ("hunger", True),
                           ("lifetime", -1), ("forage_timer", True),
                           ("forage_timer", 61), ("legacy", {})):
            flock = copy.deepcopy(base["flock"])
            flock["records"][0][key] = value
            bad_flocks.append(flock)
        flock = copy.deepcopy(base["flock"])
        flock["records"].append(copy.deepcopy(flock["records"][0]))
        bad_flocks.append(flock)
        flock = copy.deepcopy(base["flock"])
        flock["records"][0]["parent"] = flock["records"][0]["id"]
        bad_flocks.append(flock)
        for bad in bad_flocks:
            data = copy.deepcopy(base)
            data["flock"] = bad
            raw = json.dumps(data)
            self.store.path.write_text(raw)
            store = Store(self.store.directory)
            with self.subTest(bad=bad), self.assertRaises(SaveError):
                store.load()
            with self.assertRaises(SaveError):
                store.save(25, Nest())
            self.assertEqual(self.store.path.read_text(), raw)

    def test_egg_cycle_capacity_timer_and_legacy_validation(self):
        flock = Flock.initial(Companion())
        flock.level = 1
        flock.lay(flock.selected_id)
        base = asdict(flock)
        for key, value in (("id", base["records"][0]["id"]), ("remaining", True),
                           ("remaining", 61), ("generation", 1), ("traits", {}),
                           ("parent", "missing")):
            data = copy.deepcopy(base)
            data["eggs"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                Flock.from_data(data)
        data = copy.deepcopy(base)
        data["level"] = 0
        with self.assertRaises(ValueError):
            Flock.from_data(data)
        bird = flock.selected
        bird.companion.progression.advance(360, 100)
        flock.depart(bird)
        base = asdict(flock)
        for key, value in (("lifetime", True), ("reputation", True), ("reason", "bad"),
                           ("personality", ""), ("name", "")):
            data = copy.deepcopy(base)
            data["records"][0]["legacy"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                Flock.from_data(data)
