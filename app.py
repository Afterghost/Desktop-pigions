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

    def feed(self, food: str) -> None:
        if not self.nest.companion.feed(food, self.pigeon.hunger):
            self.activity_status = "No portions left. Play Shiny Sorting to earn food."
            self.render()
            return
        self.pigeon.feed(food)
        self.activity_status = "Coo! Thank you for the food."
        self.save()
        self.render()

    def pet(self) -> None:
        if self.paused:
            self.activity_status = "Resume to spend time with your pigeon."
        elif self.nest.companion.pet():
            self.activity_status = "A gentle head scratch! Friendship increased."
            self.save()
        else:
            self.activity_status = "Give your pigeon a moment before another head scratch."
        self.render()

    def reward_game(self, score: int) -> None:
        self.nest.companion.reward_game(score)
        self.activity_status = f"Game complete: +{score} friendship, +2 sunflower portions"
        if score == 5:
            self.activity_status += ", +1 golden corn!"
        self.save()
        self.render()

    def offer_shiny(self) -> None:
        if self.paused:
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
        if self.paused or progress.intervention_cooldown > 0 or self.pigeon.treasure is None:
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
        if self.paused:
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
        if self.paused:
            return
        selected = self.nest_window.tree.selection()
        if selected and self.nest.return_item(selected[0]):
            self.activity_status = "Returned a generated nest item. Coo! Friendship and trust restored."
            self.save()
            self.render()

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.menu.entryconfigure(self.pause_index, label="Resume" if self.paused else "Pause")
        self.render()

    def advance(self, seconds: float) -> None:
        if self.paused:
            return
        self.elapsed += seconds
        collected = self.pigeon.step(seconds)
        progress = self.nest.companion.progression
        previous_stage = progress.neglect_stage
        progress.advance(seconds, self.pigeon.hunger)
        if progress.neglect_stage != previous_stage and progress.neglect >= 240:
            self.activity_status = progress.neglect_stage
            self.nest_window.show()
            self.save()
        if collected is not None:
            self.nest.collect(collected)
            self.save()
        gift = self.nest.companion.advance(seconds, self.rng)
        if gift is not None:
            self.nest.collect(Treasure(gift, "Gift", "#e6ad24", *self.nest_position))
            self.activity_status = f"Your pigeon brought you a gift: {gift}!"
            self.save()
        if self.elapsed >= self.next_forage and self.pigeon.treasure is None:
            self.next_forage = self.elapsed + AUTO_FORAGE_INTERVAL
            self.offer_shiny()
        if self.elapsed >= self.next_save:
            self.save()
            self.next_save = self.elapsed + SAVE_INTERVAL

    def _tick(self) -> None:
        now = time.monotonic()
        # Sleep/suspension does not cause starvation or teleportation on resume.
        self.advance(min(0.25, max(0, now - self.last_tick)))
        self.last_tick = now
        self.render()
        self.tick_id = self.root.after(MOVEMENT_UPDATE_INTERVAL, self._tick)

    def render(self) -> None:
        pigeon = self.pigeon
        draw_pigeon(self.bird.canvas, pigeon, self.elapsed, self.paused)
        self.bird.place(pigeon.x, pigeon.y)
        if pigeon.treasure is not None and not pigeon.carrying:
            target = pigeon.treasure
            self.shiny_overlay.draw_treasure(target.color, self.elapsed,
                                             pigeon.behavior == Behavior.THEFT)
            self.shiny_overlay.place(target.x + 48, target.y + 48)
        else:
            self.shiny_overlay.hide()
        self.nest_window.refresh()
        self.game_window.refresh()

    def save(self) -> bool:
        if not self.saving_enabled:
            return False
        try:
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
        if self.tick_id is not None:
            self.root.after_cancel(self.tick_id)
        self.root.destroy()
