"""Coordinates the simulation, local saves, and small desktop views."""

import random
import time
import tkinter as tk
from tkinter import messagebox

from config import (
    AUTO_FORAGE_INTERVAL, FOOD_TYPES, MOVEMENT_UPDATE_INTERVAL, PIGEON_SIZE, SAVE_INTERVAL,
)
from companion import ATTIRE, PettingGesture
from desktop import Treasure, make_treasure, work_area
from nest import Nest
from pigeon import Behavior, Pigeon
from storage import SaveError, Store
from flock import Flock, LIFETIME_LIMIT, HISTORY_LIMIT
from progression import number
from social import SocialMotion
from pointer_prank import MouseShake, TemporaryCursorHide
from ui.nest_window import NestWindow
from ui.overlay import Overlay
from ui.bird_menu import BirdMenu
from ui.developer_settings import DeveloperSettings
from ui.pigeon_sprite import draw_pigeon
from ui.minigame_window import MinigameWindow
from ui.dressing_room import DressingRoom


TEAR_SEARCH_DELAY = 0.5
TEAR_FORAGE_CHANCE = 0.35


class DesktopPigeonApp:
    def __init__(self, root: tk.Tk, store: Store | None = None):
        self.root = root
        root.title("Desktop Pigeon")
        root.withdraw()
        self.store = store if store is not None else Store()
        self.save_status = ""
        self.saving_enabled = True
        try:
            hunger, self.nest = self.store.load()
        except SaveError as exc:
            hunger, self.nest = 25.0, Nest()
            self.save_status = str(exc)
            self.saving_enabled = False
        bounds = work_area(root.winfo_screenwidth(), root.winfo_screenheight())
        self.nest_position = bounds.clamp(bounds.x + bounds.width - 112,
                                         bounds.y + bounds.height - 100)
        self.pigeon = Pigeon(bounds, self.nest_position, hunger, companion=self.nest.companion)
        self.bounds = bounds
        if self.nest.flock is None:
            self.nest.flock = Flock.initial(self.nest.companion, hunger)
        self.flock = self.nest.flock
        self.pigeons = {}
        self.birds = {}
        self.targets = {}
        self.paper_tears = {}
        self.tear_searches = {}
        self.play_effects = {}
        self.drag_item = None
        self.drag_widget = None
        self.pet_gestures = {}
        self.effects = []
        self.social = SocialMotion()
        self.rng = random.Random()
        self.cursor_hide = TemporaryCursorHide()
        self.mouse_shake = MouseShake()
        self.pointer_prank_enabled = False
        self.pointer_thief = None
        self.pointer_stolen_at = None
        self.pointer_hover = None
        self.pointer_hover_since = None
        self.last_mouse_vector = (1, 0)
        self.pointer_theft_cooldown = 0.0
        self.movement_scale = 1.0
        self.roam_radius = 200
        self.rest_scale = 1.0
        self.treasure_interval = AUTO_FORAGE_INTERVAL
        self.pause_key = "F8"
        self._key_capture_callback = None
        self.paused = False
        self.closed = False
        self.elapsed = 0.0
        self.next_save = SAVE_INTERVAL
        self.last_tick = time.monotonic()
        self.tick_id = None
        self.bird = Overlay(root, PIGEON_SIZE)
        self.nest_overlay = Overlay(tk.Toplevel(root), 64)
        self.nest_overlay.draw_nest()
        self.nest_overlay.place(*self.nest_position)
        self.shiny_overlay = Overlay(tk.Toplevel(root), 40)
        self.developer_settings = DeveloperSettings(self)
        self.nest_window = NestWindow(self)
        self.game_window = MinigameWindow(self)
        self.dressing_room = DressingRoom(self)
        self.bird_menu = BirdMenu(self)
        self.activity_status = ""
        self.menu = tk.Menu(root, tearoff=False)
        self.menu.add_command(label="Open nest", command=self.nest_window.show)
        foods = tk.Menu(self.menu, tearoff=False)
        for food in FOOD_TYPES:
            foods.add_command(label=food.replace("_", " ").title(),
                              command=lambda food=food: self.feed(food))
        self.menu.add_cascade(label="Feed", menu=foods)
        self.menu.add_command(label="Offer a shiny", command=self.offer_shiny)
        self.menu.add_command(label="Pet pigeon", command=self.pet)
        self.menu.add_command(label="Play minigames", command=self.game_window.show)
        for action in ("Shoo / catch", "Seed bribe / trade", "Laser distraction"):
            self.menu.add_command(label=action, command=lambda action=action: self.intervene(action))
        self.pause_index = self.menu.index("end") + 1
        self.menu.add_command(label="Pause", command=self.toggle_pause)
        self.menu.add_separator()
        self.menu.add_command(label="Quit", command=self.close)
        for overlay in (self.bird, self.nest_overlay):
            overlay.canvas.bind("<Button-1>", lambda event: self.nest_window.show())
            overlay.canvas.bind("<Button-3>", self._popup)
        for index, record in enumerate(self.flock.active):
            self._add_bird(record, self.bird if index == 0 else None,
                           self.shiny_overlay if index == 0 else None)
        self._link_selection()
        root.bind_all("<KeyPress>", self._handle_keypress, add="+")
        root.bind_all("<ButtonRelease-1>", self._finish_drag, add="+")
        root.bind("<Escape>", lambda event: self.close()
                  if event.widget.winfo_toplevel() == root else None)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.render()
        if not self.saving_enabled:
            self.nest_window.show()
        self.tick_id = root.after(MOVEMENT_UPDATE_INTERVAL, self._tick)

    def _popup(self, event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def capture_next_key(self, callback):
        self._key_capture_callback = callback

    def set_pointer_prank(self):
        self.pointer_prank_enabled = (
            self.cursor_hide.supported and self.developer_settings.pointer_prank.get())
        if not self.pointer_prank_enabled:
            self._restore_pointer()

    def _restore_pointer(self, startled=False):
        if self.pointer_thief is None:
            return
        bird_id = self.pointer_thief
        self.cursor_hide.show()
        self.pointer_thief = None
        self.pointer_stolen_at = None
        self.mouse_shake.reset()
        pigeon = self.pigeons.get(bird_id)
        if startled and pigeon is not None:
            pigeon.startle(*self.last_mouse_vector)

    def _check_pointer_prank(self, now):
        if self.pointer_thief is not None:
            try:
                x, y = self.root.winfo_pointerxy()
            except tk.TclError:
                self._restore_pointer()
                return
            motion = self.mouse_shake.move(x, y, now)
            if motion is not None:
                self.last_mouse_vector = motion
                self._restore_pointer(startled=True)
            elif now - self.pointer_stolen_at >= 2:
                self._restore_pointer()
            return

        if not self.pointer_prank_enabled or self.paused or now < self.pointer_theft_cooldown:
            self.pointer_hover = None
            self.pointer_hover_since = None
            return
        try:
            x, y = self.root.winfo_pointerxy()
        except tk.TclError:
            return
        bird_id = next((identity for identity, pigeon in self.pigeons.items()
                        if pigeon.x <= x < pigeon.x + PIGEON_SIZE
                        and pigeon.y <= y < pigeon.y + PIGEON_SIZE), None)
        if bird_id != self.pointer_hover:
            self.pointer_hover = bird_id
            self.pointer_hover_since = now if bird_id is not None else None
        if (bird_id is not None and self.pointer_hover_since is not None
                and now - self.pointer_hover_since >= 2):
            if self.cursor_hide.hide():
                self.pointer_thief = bird_id
                self.pointer_stolen_at = now
                self.mouse_shake.reset()
                self.mouse_shake.move(x, y, now)
                self.pointer_hover = None
                self.pointer_hover_since = None
                self.pointer_theft_cooldown = now + 30

    def _handle_keypress(self, event):
        if event.keysym == "Escape" and self.pointer_thief is not None:
            self._restore_pointer()
            return "break"
        if event.keysym == "Escape" and self.game_window.overlay_open:
            self.game_window.cancel()
            return "break"
        if event.keysym == "Escape" and self.drag_item is not None:
            self._cancel_drag()
            return "break"
        if self._key_capture_callback is not None:
            callback, self._key_capture_callback = self._key_capture_callback, None
            callback(event.keysym)
            return "break"
        if event.keysym.casefold() == self.pause_key.casefold():
            self.toggle_pause()
            return "break"

    def apply_developer_settings(self, speed, roam, rest, treasure_interval):
        self.movement_scale = max(0.5, min(3.0, float(speed)))
        self.roam_radius = max(50, min(600, int(float(roam))))
        self.rest_scale = max(0.25, min(2.0, float(rest)))
        self.treasure_interval = max(5, min(120, int(float(treasure_interval))))
        for pigeon in self.pigeons.values():
            pigeon.movement_scale = self.movement_scale
            pigeon.roam_radius = self.roam_radius
            pigeon.rest_scale = self.rest_scale
        for record in self.flock.active:
            pigeon = self.pigeons.get(record.id)
            if pigeon is None:
                continue
            record.forage_timer = min(
                record.forage_timer,
                self._forage_delay(record))

    @property
    def has_bird(self):
        return self.flock.selected_id in self.pigeons

    def _add_bird(self, record, overlay=None, target=None):
        pigeon = Pigeon(self.bounds, self.nest_position, record.hunger,
                        companion=record.companion)
        pigeon.movement_scale = self.movement_scale
        pigeon.roam_radius = self.roam_radius
        pigeon.rest_scale = self.rest_scale
        pigeon.x, pigeon.y = self.bounds.clamp(pigeon.x + len(self.pigeons) * 100, pigeon.y)
        self.pigeons[record.id] = pigeon
        self.paper_tears[record.id] = []
        self.tear_searches[record.id] = None
        self.play_effects[record.id] = 0.0
        overlay = overlay or Overlay(tk.Toplevel(self.root), PIGEON_SIZE)
        target = target or Overlay(tk.Toplevel(self.root), 40)
        self.birds[record.id] = overlay
        self.targets[record.id] = target
        overlay.canvas.bind("<Button-1>",
                            lambda event, bird_id=record.id: self._bird_click(bird_id, event))
        overlay.canvas.bind("<Double-Button-1>", lambda event, bird_id=record.id: self._pet_bird(bird_id))
        overlay.canvas.bind("<Motion>", lambda event, bird_id=record.id: self._pet_motion(bird_id, event))
        overlay.canvas.bind("<Leave>", lambda event, bird_id=record.id: self.pet_gestures[bird_id].reset())
        overlay.canvas.bind("<Button-3>", lambda event, bird_id=record.id:
                            self._bird_popup(bird_id))
        self.pet_gestures[record.id] = PettingGesture()

    def _bird_popup(self, bird_id):
        if not self.select_bird(bird_id):
            return
        overlay = self.birds[bird_id]
        self.bird_menu.show(overlay.window.winfo_rootx(), overlay.window.winfo_rooty(), self.bounds)

    def _bird_click(self, bird_id, event):
        if self.game_window.handle_click(bird_id, event.x, event.y):
            return "break"
        self.select_bird(bird_id, True)

    def _pet_bird(self, bird_id):
        if (self.developer_settings.gesture.get() != "Mouse strokes"
                and self.select_bird(bird_id, True)):
            self.pet()

    def _pet_motion(self, bird_id, event):
        if self.closed or self.paused or bird_id not in self.pet_gestures:
            return
        if self.developer_settings.gesture.get() == "Double-click":
            return
        speed = self.pet_gestures[bird_id].move(event.x, time.monotonic())
        if speed is None:
            return
        selected_speed = self.nest_window.petting_speed.get().lower()
        if selected_speed not in ("any speed", speed):
            self.activity_status = f"Choose {speed.title()} or Any speed in Settings to use that stroke."
            self.render()
            return
        if self.select_bird(bird_id, True):
            self.pet(speed)

    def _link_selection(self):
        record = self.flock.selected or self.flock.records[0]
        self.nest.companion = record.companion
        if self.has_bird:
            self.pigeon = self.pigeons[record.id]
            self.bird = self.birds[record.id]
            self.shiny_overlay = self.targets[record.id]
        else:
            self.pigeon = Pigeon(self.bounds, self.nest_position, record.hunger,
                                 companion=record.companion)

    def select_bird(self, bird_id, show=False):
        if self.closed or bird_id not in self.pigeons:
            return False
        if bird_id != self.flock.selected_id:
            self.social.cancel(self.pigeons)
            self.game_window.cancel()
            self.flock.selected_id = bird_id
            self._link_selection()
            self.save()
        self.render()
        if show:
            self.nest_window.show()
        return True

    def set_outfit(self, outfit):
        if self.closed or self.paused or not self.has_bird or outfit not in ATTIRE:
            return False
        self.nest.companion.outfit = outfit
        preference = self.nest.companion.appeal_preference
        self.activity_status = (
            f"{self.flock.selected.name} loves the {outfit.lower()} look!"
            if outfit == preference else
            f"{self.flock.selected.name} is unsure about the {outfit.lower()} look.")
        self.save()
        self.render()
        return True

    def begin_drag(self, item: str, widget) -> bool:
        if (self.closed or self.paused or item not in (*FOOD_TYPES, "feather")
                or self.drag_item is not None):
            return False
        self.drag_item = item
        self.drag_widget = widget
        try:
            widget.grab_set_global()
        except tk.TclError:
            self.drag_item = None
            self.drag_widget = None
            return False
        self.activity_status = (
            f"Dragging {item.replace('_', ' ')} — drop it on a pigeon; Escape cancels.")
        self.render()
        return True

    def _cancel_drag(self) -> None:
        widget, self.drag_widget = self.drag_widget, None
        self.drag_item = None
        if widget is not None:
            try:
                widget.grab_release()
            except tk.TclError:
                pass
        self.activity_status = "Tray drag cancelled."
        self.render()

    def _finish_drag(self, event=None):
        if self.drag_item is None:
            return
        item, self.drag_item = self.drag_item, None
        widget, self.drag_widget = self.drag_widget, None
        if widget is not None:
            try:
                widget.grab_release()
            except tk.TclError:
                pass
        try:
            x, y = self.root.winfo_pointerxy()
        except tk.TclError:
            return "break"
        self.drop_from_tray(item, x, y)
        return "break"

    def drop_from_tray(self, item: str, x: int, y: int) -> bool:
        if self.closed or self.paused or item not in (*FOOD_TYPES, "feather"):
            return False
        bird_id = next((identity for identity, pigeon in self.pigeons.items()
                        if pigeon.x <= x < pigeon.x + PIGEON_SIZE
                        and pigeon.y <= y < pigeon.y + PIGEON_SIZE), None)
        if bird_id is None:
            self.activity_status = "Drop the food or feather onto a pigeon."
            self.render()
            return False
        if bird_id != self.flock.selected_id:
            self.select_bird(bird_id)
        if item == "feather":
            self.play_effects[bird_id] = 2.0
            self.activity_status = f"{self.flock.selected.name} played with a feather."
            self.render()
            return True
        self.feed(item)
        return True

    def smooth_tears(self) -> None:
        for tears in self.paper_tears.values():
            tears.clear()
        self.activity_status = "Smoothed out the temporary paper tears."
        self.render()

    def upgrade_nest(self):
        if self.closed or self.paused:
            return
        if self.flock.upgrade():
            self.activity_status = f"Nest expanded: capacity {self.flock.capacity}."
        else:
            self.activity_status = "Collect more generated items to earn nest treasury, or nest is already Grand."
        self.save()
        self.render()

    def lay_egg(self, adopt=False):
        if self.closed or self.paused:
            return
        if self.flock.lay(None if adopt else self.flock.selected_id):
            self.activity_status = "Egg waiting: 60 active seconds to hatch."
        else:
            self.activity_status = f"No room: upgrade/rejoin later. Permanent identity limit: {HISTORY_LIMIT}."
        self.save()
        self.render()

    def rejoin_history(self):
        if self.closed or self.paused:
            return
        selected = self.nest_window.family.selection()
        if selected and self.flock.rejoin(selected[0]):
            self.social.cancel(self.pigeons)
            self.game_window.cancel()
            self._add_bird(self.flock.selected)
            self._link_selection()
            self.activity_status = "Welcome home! Identity and legacy preserved."
            self.save()
        else:
            self.activity_status = "Select a departed bird; a free nest slot is required."
        self.render()

    def _depart(self, record):
        if self.pointer_thief == record.id:
            self._restore_pointer()
        task = self.social.collaboration
        if task and record.id in (task.leader, task.partner):
            self.social.cancel(self.pigeons)
        if ((self.social.avoidance and record.id in self.social.avoidance[:2])
                or (self.social.greeting and record.id in self.social.greeting[:2])):
            self.social.cancel(self.pigeons)
        pigeon = self.pigeons.pop(record.id)
        pigeon.cancel_theft()
        self.paper_tears.pop(record.id, None)
        self.tear_searches.pop(record.id, None)
        self.play_effects.pop(record.id, None)
        overlay = self.birds.pop(record.id)
        target = self.targets.pop(record.id)
        overlay.hide()
        target.hide()
        if overlay.window != self.root:
            overlay.window.destroy()
        target.window.destroy()
        if record.id == self.flock.selected_id:
            self.game_window.cancel()
        self.flock.depart(record)
        effect = Overlay(tk.Toplevel(self.root), PIGEON_SIZE)
        effect.canvas.create_line(25, 20, 45, 38, fill="#c4ced6", width=4)
        effect.canvas.create_line(28, 18, 33, 30, fill="#c4ced6", width=3)
        effect.canvas.create_line(20, 55, 60, 65, fill="#99714d", width=3)
        effect.canvas.create_oval(55, 25, 72, 32, fill="#c4ced6", outline="")
        effect.place(pigeon.x, pigeon.y)
        self.effects.append((effect, self.elapsed + 3))
        self._link_selection()
        self.activity_status = f"{record.name} departed. Legacy kept; invite back from Family/history."
        self.nest_window.show()
        self.save()

    def feed(self, food: str) -> None:
        if self.closed or not self.has_bird:
            return
        if not self.nest.companion.feed(food, self.pigeon.hunger):
            self.activity_status = "No portions left. Play Shiny Sorting to earn food."
            self.render()
            return
        self.pigeon.feed(food)
        if self.nest.companion.progression.actions["care"]:
            self.flock.milestone(self.flock.selected_id, "care")
        self.activity_status = "Coo! Thank you for the food."
        self.save()
        self.render()

    def pet(self, speed=None) -> None:
        if self.closed or not self.has_bird:
            return
        if self.paused:
            self.activity_status = "Resume to spend time with your pigeon."
        elif self.nest.companion.pet(speed):
            self.flock.milestone(self.flock.selected_id, "care")
            if speed and speed == self.nest.companion.pet_speed_preference:
                self.activity_status = f"Perfect {speed} strokes! Your pigeon loves that pace."
            elif speed:
                self.activity_status = f"A {speed} head scratch! Friendship increased."
            else:
                self.activity_status = "A gentle head scratch! Friendship increased."
            self.save()
        else:
            self.activity_status = "Give your pigeon a moment before another head scratch."
        self.render()

    def reward_game(self, score: int, participant=None) -> bool:
        if (self.closed or self.paused or not self.has_bird
                or (participant is not None and participant != self.flock.selected_id)):
            return False
        self.nest.companion.reward_game(score)
        self.flock.milestone(self.flock.selected_id, "win")
        trinket = make_treasure(self.pigeon.bounds, self.pigeon.x, self.pigeon.y, self.rng)
        self.nest.collect(trinket, self.nest.companion)
        self.flock.milestone(self.flock.selected_id, "treasure")
        self.activity_status = (
            f"Game complete: +{score} friendship, +2 sunflower portions, "
            f"and a {trinket.name} trinket!")
        if score == 5:
            self.activity_status += ", +1 golden corn!"
        self.save()
        self.render()
        return True

    def offer_shiny(self) -> None:
        if self.closed or self.paused or not self.has_bird:
            return
        pigeon = self.pigeon
        task = self.social.collaboration
        if task and self.flock.selected_id in (task.leader, task.partner):
            return
        if self.social.greeting and self.flock.selected_id in self.social.greeting[:2]:
            return
        target = make_treasure(pigeon.bounds, pigeon.x, pigeon.y, self.rng)
        if pigeon.investigate(target):
            self.flock.selected.forage_timer = self._forage_delay(self.flock.selected)
            self.tear_searches[self.flock.selected_id] = None
        self.render()

    def intervene(self, action: str) -> bool:
        if action not in ("Shoo / catch", "Seed bribe / trade", "Laser distraction"):
            raise ValueError("Unknown intervention")
        profile = self.nest.companion
        progress = profile.progression
        if self.closed or not self.has_bird or self.paused or progress.intervention_cooldown > 0 or self.pigeon.treasure is None:
            self.activity_status = "No active target, paused, or intervention resting (10 active seconds)."
            self.render()
            return False
        if action == "Seed bribe / trade":
            if profile.food["sunflower_seeds"] <= 0:
                self.activity_status = "Trade needs one earned sunflower portion."
                self.render()
                return False
            profile.food["sunflower_seeds"] -= 1
            self.pigeon.feed("sunflower_seeds")
            progress.reconcile()
        self.social.cancel(self.pigeons)
        self.pigeon.cancel_theft()
        progress.intervention_cooldown = 10
        profile.evolve("govern")
        self.flock.selected.forage_timer = self._forage_delay(self.flock.selected)
        self.tear_searches[self.flock.selected_id] = None
        self.activity_status = f"{action}: cancelled the synthetic target. Nothing collected."
        self.save()
        self.render()
        return True

    def protect(self, kind):
        if kind not in ("Treasure", "Fragment"):
            raise ValueError("Unknown protected type")
        if self.closed or not self.has_bird or self.paused:
            return
        protected = self.nest.companion.progression.protected
        if kind in protected:
            protected.remove(kind)
        else:
            protected.append(kind)
            task = self.social.collaboration
            if (task and self.flock.selected_id in (task.leader, task.partner)
                    and task.target.kind == kind):
                self.social.cancel(self.pigeons)
            if self.pigeon.treasure is not None and self.pigeon.treasure.kind == kind:
                self.pigeon.cancel_theft()
        self.flock.selected.forage_timer = self._forage_delay(self.flock.selected)
        self.tear_searches[self.flock.selected_id] = None
        self.save()
        self.render()

    def return_selected(self):
        if self.closed or not self.has_bird or self.paused:
            return
        selected = self.nest_window.tree.selection()
        if selected and self.nest.return_item(selected[0]):
            self.activity_status = "Returned a generated nest item. Coo! Friendship and trust restored."
            self.save()
            self.render()

    def toggle_pause(self) -> None:
        if self.closed:
            return
        self._restore_pointer()
        self.last_tick = time.monotonic()
        self.paused = not self.paused
        self.menu.entryconfigure(self.pause_index, label="Resume" if self.paused else "Pause")
        self.render()

    def advance(self, seconds: float) -> None:
        if not number(seconds, 1_000_000):
            raise ValueError("Invalid active time")
        if self.closed or self.paused:
            return
        self.elapsed += seconds
        self.social.advance(seconds, self.flock, self.pigeons)
        deliveries = []
        gifts = []
        for record in list(self.flock.active):
            pigeon = self.pigeons[record.id]
            progress = record.companion.progression
            previous_stage = progress.neglect_stage
            # Limit a single large deterministic step to the remaining departure time.
            active_seconds = seconds
            if pigeon.hunger >= 90:
                active_seconds = min(seconds, 240 - progress.neglect + 120 - progress.grace)
            elif progress.neglect >= 240:
                active_seconds = min(seconds, 120 - progress.grace)
            task = self.social.collaboration
            controlled = (task and record.id == task.partner) or (
                self.social.avoidance and record.id == self.social.avoidance[0]) or (
                self.social.greeting and record.id in self.social.greeting[:2])
            collected = pigeon.step(active_seconds, social_movement=bool(controlled))
            self._advance_cosmetics(record.id, pigeon, active_seconds)
            self._advance_forage(record, pigeon, active_seconds, bool(controlled))
            record.hunger = pigeon.hunger
            record.lifetime = min(LIFETIME_LIMIT, record.lifetime + active_seconds)
            progress.advance(active_seconds, pigeon.hunger)
            if progress.grace >= 120:
                self._depart(record)
                continue
            if progress.neglect_stage != previous_stage and progress.neglect >= 240:
                self.activity_status = f"{record.name}: {progress.neglect_stage}"
                self.nest_window.show()
                self.save()
            if collected is not None:
                deliveries.append((record, collected,
                                   task if task and task.leader == record.id else None))
            gift = record.companion.advance(active_seconds, self.rng)
            if gift is not None:
                gifts.append((record, gift))
        for record, collected, task in deliveries:
            if record.status != "active":
                continue
            if task:
                if task is not self.social.collaboration:
                    continue
                if not self.social.finish(record.id, collected, self.flock, self.pigeons):
                    continue
                self.activity_status = f"{record.name} and a friend stored one shared treasure."
            self.nest.collect(collected, record.companion)
            self.flock.milestone(record.id, "treasure")
            self.save()
        for record, gift in gifts:
            self.nest.collect(Treasure(gift, "Gift", "#e6ad24", *self.nest_position),
                              record.companion)
            self.flock.milestone(record.id, "gift")
            partner = self.social.share_gift(record.id, self.flock, self.pigeons)
            self.activity_status = (f"{record.name} and a flock friend delivered one shared gift: {gift}!"
                                    if partner else f"{record.name} brought a gift: {gift}!")
            self.save()
        interactions = self.flock.interactions
        hatched = self.flock.advance(seconds)
        for record in hatched:
            self._add_bird(record)
        if hatched:
            self._link_selection()
            self.activity_status = f"{len(hatched)} pigeon(s) hatched — generation {hatched[-1].generation}."
            self.save()
        if self.flock.interactions != interactions:
            self.social.start(self.flock, self.pigeons,
                              lambda bird: make_treasure(bird.bounds, bird.x, bird.y, self.rng),
                              allow_foraging=False)
            self.activity_status = "Flock met: mutual bonds changed; elders shared calm."
        for effect, expiry in list(self.effects):
            if self.elapsed >= expiry:
                effect.window.destroy()
                self.effects.remove((effect, expiry))
        if self.elapsed >= self.next_save:
            self.save()
            self.next_save = self.elapsed + SAVE_INTERVAL

    def _tick(self) -> None:
        if self.closed:
            return
        now = time.monotonic()
        # Sleep/suspension does not cause starvation or teleportation on resume.
        self.advance(min(0.25, max(0, now - self.last_tick)))
        self.last_tick = now
        self._check_pointer_prank(now)
        self.render()
        self.tick_id = self.root.after(MOVEMENT_UPDATE_INTERVAL, self._tick)

    def render(self) -> None:
        if self.closed:
            return
        for bird_id, pigeon in self.pigeons.items():
            overlay = self.birds[bird_id]
            playing = (self.game_window.overlay_open
                       and self.game_window.participant == bird_id)
            if playing:
                width, height, x, y, offset_x, offset_y = (
                    self.game_window.overlay_layout(pigeon))
                overlay.canvas.configure(width=width, height=height)
                overlay.window.geometry(f"{width}x{height}{x:+d}{y:+d}")
                if overlay.window.state() == "withdrawn":
                    overlay.window.deiconify()
            else:
                overlay.canvas.configure(width=PIGEON_SIZE, height=PIGEON_SIZE)
            draw_pigeon(overlay.canvas, pigeon, self.elapsed, self.paused,
                        holding_pointer=bird_id == self.pointer_thief,
                        paper_tears=self.paper_tears[bird_id],
                        feather_playing=self.play_effects[bird_id] > 0)
            if playing:
                overlay.canvas.move("all", offset_x, offset_y)
            label = self.social.labels.get(bird_id)
            if label:
                overlay.canvas.create_text((offset_x if playing else 0) + PIGEON_SIZE // 2,
                                           (offset_y if playing else 0) + 12, text=label,
                                           fill="#825019", font=("TkDefaultFont", 8))
            if not playing:
                overlay.place(pigeon.x, pigeon.y)
            shiny = self.targets[bird_id]
            if pigeon.treasure is not None and not pigeon.carrying:
                target = pigeon.treasure
                shiny.draw_treasure(target.color, self.elapsed, pigeon.behavior == Behavior.THEFT)
                shiny.place(*pigeon.bounds.clamp(target.x + 48, target.y + 48))
            else:
                shiny.hide()
        if self.game_window.overlay_open:
            self.game_window.draw_overlay(self.birds[self.game_window.participant].canvas)
        self.nest_window.refresh()
        self.game_window.refresh()
        self.dressing_room.refresh()

    def save(self) -> bool:
        if self.closed or not self.saving_enabled:
            return False
        try:
            for record in self.flock.active:
                record.hunger = self.pigeons[record.id].hunger
            self.store.save(self.pigeon.hunger, self.nest)
            self.save_status = ""
            return True
        except SaveError as exc:
            self.save_status = str(exc)
            self.nest_window.show()
            return False

    def _advance_cosmetics(self, bird_id, pigeon, seconds):
        tears = self.paper_tears[bird_id]
        for tear in tears:
            tear["age"] += seconds
        tears[:] = [tear for tear in tears if tear["age"] < 9]
        self.play_effects[bird_id] = max(0, self.play_effects[bird_id] - seconds)

    def _forage_delay(self, record):
        curiosity = record.companion.traits["curiosity"] / 100
        return min(60, self.treasure_interval * (1.5 - curiosity))

    def _advance_forage(self, record, pigeon, seconds, controlled):
        bird_id = record.id
        if pigeon.treasure is not None or controlled:
            self.tear_searches[bird_id] = None
            return
        pending = self.tear_searches[bird_id]
        if pending is not None:
            pending -= seconds
            self.tear_searches[bird_id] = pending
            if pending <= 0:
                self.tear_searches[bird_id] = None
                record.forage_timer = self._forage_delay(record)
                if self.rng.random() < TEAR_FORAGE_CHANCE:
                    if self.social.start_foraging(
                            record.id, self.flock, self.pigeons,
                            lambda bird: make_treasure(
                                bird.bounds, bird.x, bird.y, self.rng)):
                        self.activity_status = (
                            f"{record.name} found a shiny after tearing the screen!")
                        return
                    target = make_treasure(pigeon.bounds, pigeon.x, pigeon.y, self.rng)
                    if pigeon.investigate(target):
                        self.activity_status = (
                            f"{record.name} found a shiny after tearing the screen!")
                else:
                    self.activity_status = (
                        f"No item this time; {record.name} will search again after another tear.")
            return
        if pigeon.behavior != Behavior.IDLE:
            return
        record.forage_timer = max(0, record.forage_timer - seconds)
        if record.forage_timer == 0:
            tears = self.paper_tears[bird_id]
            if len(tears) >= 8:
                tears.pop(0)
            tears.append({
                "x": self.rng.uniform(15, PIGEON_SIZE - 15),
                "y": self.rng.uniform(38, PIGEON_SIZE - 12),
                "age": 0.0,
                "angle": self.rng.uniform(-0.5, 0.5),
            })
            self.tear_searches[bird_id] = TEAR_SEARCH_DELAY
            self.activity_status = f"{record.name} tore a paper scrap and is searching."

    def close(self) -> None:
        if self.closed:
            return
        if self.drag_item is not None:
            self._cancel_drag()
        self._restore_pointer()
        if self.saving_enabled and not self.save():
            if not messagebox.askyesno("Local save failed",
                                      "Quit without saving the latest changes?",
                                      parent=self.nest_window.window):
                return
        self.closed = True
        self.game_window.cancel()
        self.social.cancel(self.pigeons)
        for pigeon in self.pigeons.values():
            pigeon.cancel_theft()
        if self.tick_id is not None:
            self.root.after_cancel(self.tick_id)
        self.root.destroy()
