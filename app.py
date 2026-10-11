"""Coordinates the simulation, local saves, and small desktop views."""

import random
import time
import tkinter as tk
from tkinter import messagebox

from config import (
    AUTO_FORAGE_INTERVAL, FOOD_TYPES, MOVEMENT_UPDATE_INTERVAL, PIGEON_SIZE, SAVE_INTERVAL,
)
from desktop import Treasure, make_treasure, work_area
from nest import Nest
from pigeon import Behavior, Pigeon
from storage import SaveError, Store
from flock import Flock, LIFETIME_LIMIT, HISTORY_LIMIT
from progression import number
from ui.nest_window import NestWindow
from ui.overlay import Overlay
from ui.pigeon_sprite import draw_pigeon
from ui.minigame_window import MinigameWindow


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
        self.effects = []
        self.rng = random.Random()
        self.paused = False
        self.closed = False
        self.elapsed = 0.0
        self.next_forage = 6.0
        self.next_save = SAVE_INTERVAL
        self.last_tick = time.monotonic()
        self.tick_id = None
        self.bird = Overlay(root, PIGEON_SIZE)
        self.nest_overlay = Overlay(tk.Toplevel(root), 64)
        self.nest_overlay.draw_nest()
        self.nest_overlay.place(*self.nest_position)
        self.shiny_overlay = Overlay(tk.Toplevel(root), 40)
        self.nest_window = NestWindow(self)
        self.game_window = MinigameWindow(self)
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

    @property
    def has_bird(self):
        return self.flock.selected_id in self.pigeons

    def _add_bird(self, record, overlay=None, target=None):
        pigeon = Pigeon(self.bounds, self.nest_position, record.hunger,
                        companion=record.companion)
        pigeon.x, pigeon.y = self.bounds.clamp(pigeon.x + len(self.pigeons) * 100, pigeon.y)
        self.pigeons[record.id] = pigeon
        overlay = overlay or Overlay(tk.Toplevel(self.root), PIGEON_SIZE)
        target = target or Overlay(tk.Toplevel(self.root), 40)
        self.birds[record.id] = overlay
        self.targets[record.id] = target
        overlay.canvas.bind("<Button-1>", lambda event, bird_id=record.id: self.select_bird(bird_id, True))
        overlay.canvas.bind("<Button-3>", lambda event, bird_id=record.id: (
            self.select_bird(bird_id), self._popup(event)))

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
            self.game_window.cancel()
            self.flock.selected_id = bird_id
            self._link_selection()
            self.save()
        self.render()
        if show:
            self.nest_window.show()
        return True

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
            self.game_window.cancel()
            self._add_bird(self.flock.selected)
            self._link_selection()
            self.activity_status = "Welcome home! Identity and legacy preserved."
            self.save()
        else:
            self.activity_status = "Select a departed bird; a free nest slot is required."
        self.render()

    def _depart(self, record):
        pigeon = self.pigeons.pop(record.id)
        pigeon.cancel_theft()
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
        self.activity_status = "Coo! Thank you for the food."
        self.save()
        self.render()

    def pet(self) -> None:
        if self.closed or not self.has_bird:
            return
        if self.paused:
            self.activity_status = "Resume to spend time with your pigeon."
        elif self.nest.companion.pet():
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
        self.activity_status = f"Game complete: +{score} friendship, +2 sunflower portions"
        if score == 5:
            self.activity_status += ", +1 golden corn!"
        self.save()
        self.render()
        return True

    def offer_shiny(self) -> None:
        if self.closed or self.paused or not self.has_bird:
            return
        pigeon = self.pigeon
        target = make_treasure(pigeon.bounds, pigeon.x, pigeon.y, self.rng)
        if pigeon.investigate(target):
            curiosity = self.nest.companion.traits["curiosity"] / 100
            self.next_forage = self.elapsed + AUTO_FORAGE_INTERVAL * (1.5 - curiosity)
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
        self.pigeon.cancel_theft()
        progress.intervention_cooldown = 10
        profile.evolve("govern")
        self.next_forage = self.elapsed + AUTO_FORAGE_INTERVAL
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
            if self.pigeon.treasure is not None and self.pigeon.treasure.kind == kind:
                self.pigeon.cancel_theft()
        self.next_forage = self.elapsed + AUTO_FORAGE_INTERVAL
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
            collected = pigeon.step(active_seconds)
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
                self.nest.collect(collected, record.companion)
                self.save()
            gift = record.companion.advance(active_seconds, self.rng)
            if gift is not None:
                self.nest.collect(Treasure(gift, "Gift", "#e6ad24", *self.nest_position),
                                  record.companion)
                self.activity_status = f"Your pigeon brought you a gift: {gift}!"
                self.save()
            if record.id != self.flock.selected_id and pigeon.treasure is None:
                record.forage_timer = max(0, record.forage_timer - active_seconds)
                if record.forage_timer == 0:
                    pigeon.investigate(make_treasure(pigeon.bounds, pigeon.x, pigeon.y, self.rng))
                    curiosity = record.companion.traits["curiosity"] / 100
                    record.forage_timer = AUTO_FORAGE_INTERVAL * (1.5 - curiosity)
        hatched = self.flock.advance(seconds)
        for record in hatched:
            self._add_bird(record)
        if hatched:
            self._link_selection()
            self.activity_status = f"{len(hatched)} pigeon(s) hatched — generation {hatched[-1].generation}."
            self.save()
        if self.flock.interactions and self.flock.social_timer == 0:
            self.activity_status = "Flock coo: +1 friendship together; elder shared calm with younger birds."
        for effect, expiry in list(self.effects):
            if self.elapsed >= expiry:
                effect.window.destroy()
                self.effects.remove((effect, expiry))
        if self.has_bird and self.elapsed >= self.next_forage and self.pigeon.treasure is None:
            self.next_forage = self.elapsed + AUTO_FORAGE_INTERVAL
            self.offer_shiny()
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
        self.render()
        self.tick_id = self.root.after(MOVEMENT_UPDATE_INTERVAL, self._tick)

    def render(self) -> None:
        if self.closed:
            return
        for bird_id, pigeon in self.pigeons.items():
            overlay = self.birds[bird_id]
            draw_pigeon(overlay.canvas, pigeon, self.elapsed, self.paused)
            overlay.place(pigeon.x, pigeon.y)
            shiny = self.targets[bird_id]
            if pigeon.treasure is not None and not pigeon.carrying:
                target = pigeon.treasure
                shiny.draw_treasure(target.color, self.elapsed, pigeon.behavior == Behavior.THEFT)
                shiny.place(*pigeon.bounds.clamp(target.x + 48, target.y + 48))
            else:
                shiny.hide()
        self.nest_window.refresh()
        self.game_window.refresh()

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

    def close(self) -> None:
        if self.closed:
            return
        if self.saving_enabled and not self.save():
            if not messagebox.askyesno("Local save failed",
                                      "Quit without saving the latest changes?",
                                      parent=self.nest_window.window):
                return
        self.closed = True
        self.game_window.cancel()
        for pigeon in self.pigeons.values():
            pigeon.cancel_theft()
        if self.tick_id is not None:
            self.root.after_cancel(self.tick_id)
        self.root.destroy()
