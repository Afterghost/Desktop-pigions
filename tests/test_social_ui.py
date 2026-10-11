from dataclasses import asdict
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
from pigeon import Behavior
from storage import Store


@unittest.skipUnless(tk and (sys.platform == "win32" or os.environ.get("DISPLAY")), "Tk display required")
class SocialUITests(unittest.TestCase):
    def setUp(self):
        from app import DesktopPigeonApp
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent)
        self.addCleanup(self.directory.cleanup)
        self.root = tk.Tk()
        self.app = DesktopPigeonApp(self.root, Store(Path(self.directory.name)))
        self.addCleanup(self.cleanup)
        self.root.update()
        self.root.after_cancel(self.app.tick_id)
        self.app.tick_id = None
        self.app.flock.treasury = 5
        self.app.upgrade_nest()
        self.app.lay_egg()
        self.app.advance(60)
        for bird in self.app.flock.active:
            self.app.pigeons[bird.id].cancel_theft()
            bird.forage_timer = 60
        self.app.next_forage = self.app.elapsed + 10000
        self.app.flock.bonds[0].affinity = 40

    def cleanup(self):
        if not self.app.closed:
            self.app.close()

    def collaborate(self):
        self.app.social.start(self.app.flock, self.app.pigeons,
                              lambda p: Treasure("Blue marble", "Treasure", "#abc", p.x, p.y))
        self.assertIsNotNone(self.app.social.collaboration)
        return self.app.social.collaboration

    def test_one_shared_collection_no_duplicate_treasury_or_profile_reward(self):
        app = self.app
        task = self.collaborate()
        leader = app.pigeons[task.leader]
        partner = app.pigeons[task.partner]
        leader.behavior = Behavior.STORING
        leader.wait = .1
        count = len(app.nest.items)
        treasury = app.flock.treasury
        partner_count = partner.companion.progression.actions["collect"]
        app.advance(.1)
        self.assertEqual(len(app.nest.items), count + 1)
        self.assertEqual(app.flock.treasury, treasury + 1)
        self.assertEqual(partner.companion.progression.actions["collect"], partner_count)
        app.advance(.1)
        self.assertEqual(len(app.nest.items), count + 1)
        self.assertIsNone(app.social.collaboration)
        self.assertIn("foraging", {e.kind for e in app.flock.chronicle.recent})

    def test_pause_protection_selection_and_partner_departure_abort(self):
        app = self.app
        task = self.collaborate()
        app.toggle_pause()
        before = asdict(app.flock)
        app.advance(1000)
        self.assertEqual(asdict(app.flock), before)
        self.assertEqual(task.remaining, 30)
        app.toggle_pause()
        app.select_bird(next(i for i in (task.leader, task.partner) if i != app.flock.selected_id))
        self.assertIsNone(app.social.collaboration)
        self.assertIsNone(app.pigeons[task.leader].treasure)
        task = self.collaborate()
        app.protect("Treasure")
        self.assertIsNone(app.social.collaboration)
        count = len(app.nest.items)
        app.advance(.1)
        self.assertEqual(len(app.nest.items), count)
        app.protect("Treasure")
        task = self.collaborate()
        app.pigeons[task.leader].behavior = Behavior.STORING
        app.pigeons[task.leader].wait = .1
        partner = next(b for b in app.flock.active if b.id == task.partner)
        partner.companion.progression.neglect = 240
        partner.companion.progression.grace = 119.9
        app.pigeons[partner.id].hunger = 100
        app.advance(.1)
        self.assertEqual(partner.status, "departed")
        self.assertEqual(len(app.nest.items), count)
        self.assertIsNone(app.social.collaboration)

    def test_story_widgets_selected_lineage_empty_flock_and_saved_milestones(self):
        app = self.app
        app.feed("seed_mix")
        app.game_window.start()
        for _ in range(5):
            app.game_window.answer(app.game_window.game.current[1])
        app.nest_window.refresh()
        self.assertIn("Friendship", app.nest_window.bonds["text"])
        stories = app.nest_window.stories
        child = app.flock.active[1]
        app.nest_window.family.selection_set(child.id)
        stories.show()
        stories.mode.set("Ancestors")
        stories.refresh()
        self.root.update()
        text = stories.text.get("1.0", "end")
        self.assertIn("generation 2", text)
        self.assertIn("inherited", text)
        self.assertIn("first recorded game", text)
        self.assertEqual(len(stories.family.get_children()), 2)
        for bird in list(app.flock.active):
            bird.companion.progression.advance(360, 100)
            app._depart(bird)
        stories.refresh()
        self.root.update()
        self.assertIn("departed", stories.text.get("1.0", "end"))
        self.assertFalse(app.has_bird)
        app.save()
        self.assertEqual(app.store.load()[1].flock.chronicle, app.flock.chronicle)

    def test_shared_gift_one_item_escort_pause_and_no_extra_currency(self):
        app = self.app
        source = app.flock.active[0]
        source.companion.friendship = 20
        source.companion.gift_timer = 119.9
        treasury = app.flock.treasury
        app.advance(.1)
        self.assertEqual(len(app.nest.items), 1)
        self.assertEqual(app.nest.items[0].kind, "Gift")
        self.assertEqual(app.flock.treasury, treasury)
        self.assertIsNotNone(app.social.greeting)
        helper = app.pigeons[app.social.greeting[1]]
        helper.x, helper.y = app.bounds.x, app.bounds.y
        before = helper.x, helper.y
        app.advance(.1)
        self.assertNotEqual((helper.x, helper.y), before)
        app.toggle_pause()
        frozen = list(app.social.greeting)
        app.advance(100)
        self.assertEqual(app.social.greeting, frozen)
        self.assertEqual(len(app.nest.items), 1)
