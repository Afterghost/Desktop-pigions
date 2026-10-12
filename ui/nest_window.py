"""Nest inventory and companion controls."""

import tkinter as tk
from tkinter import ttk

from config import FOOD_TYPES, MAX_STORED_ITEMS, NEST_HEIGHT, NEST_WIDTH
from flock import UPGRADE_COSTS
from ui.story_window import StoryWindow


class NestWindow:
    def __init__(self, app):
        self.app = app
        self.stories = StoryWindow(app)
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title("Desktop Pigeon — Nest")
        self.window.geometry(f"{NEST_WIDTH + 80}x{NEST_HEIGHT + 380}")
        self.window.minsize(620, 720)
        self.window.protocol("WM_DELETE_WINDOW", self.window.withdraw)
        self.window.bind("<Escape>", lambda event: self.window.withdraw() or "break")
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill="both", expand=True)
        self.summary = ttk.Label(frame, font=("TkDefaultFont", 11, "bold"))
        self.summary.pack(anchor="w")
        self.hunger = ttk.Progressbar(frame, maximum=100)
        self.hunger.pack(fill="x", pady=(5, 8))
        self.relationship = ttk.Label(frame)
        self.relationship.pack(anchor="w")
        self.friendship = ttk.Progressbar(frame, maximum=100)
        self.friendship.pack(fill="x", pady=3)
        self.personality = ttk.Label(frame)
        self.personality.pack(anchor="w")
        family_frame = ttk.LabelFrame(frame, text="Family / permanent history (click active bird to select)", padding=3)
        family_frame.pack(fill="x")
        self.flock_summary = ttk.Label(family_frame)
        self.flock_summary.pack(anchor="w")
        self.family = ttk.Treeview(family_frame, columns=("name", "gen", "parent", "rep", "status"),
                                  show="headings", height=3)
        for column, title in (("name", "Name"), ("gen", "Gen"), ("parent", "Parent"),
                              ("rep", "Reputation"), ("status", "Status")):
            self.family.heading(column, text=title)
            self.family.column(column, width=95, minwidth=30)
        self.family.pack(fill="x")
        self.family.bind("<<TreeviewSelect>>", lambda event: self._select_family())
        family_scroll = ttk.Scrollbar(family_frame, orient="vertical", command=self.family.yview)
        family_scroll.pack(side="right", fill="y")
        self.family.configure(yscrollcommand=family_scroll.set)
        self.legacy_info = ttk.Label(family_frame, wraplength=610)
        self.legacy_info.pack(anchor="w")
        growth = ttk.Frame(family_frame)
        growth.pack(fill="x")
        self.upgrade_button = ttk.Button(growth, command=app.upgrade_nest)
        self.upgrade_button.pack(side="left")
        self.egg_button = ttk.Button(growth, text="Lay egg", command=app.lay_egg)
        self.egg_button.pack(side="left")
        self.adopt_button = ttk.Button(growth, text="Adopt egg", command=lambda: app.lay_egg(True))
        self.adopt_button.pack(side="left")
        self.rejoin_button = ttk.Button(growth, text="Invite departed bird back", command=app.rejoin_history)
        self.rejoin_button.pack(side="left")
        self.progress = ttk.Label(frame, wraplength=620)
        self.progress.pack(anchor="w")
        self.journal = ttk.Label(frame, wraplength=620)
        self.journal.pack(anchor="w")
        social = ttk.Frame(frame)
        social.pack(fill="x", pady=5)
        self.pet_button = ttk.Button(social, text="Pet pigeon", command=app.pet)
        self.pet_button.pack(side="left")
        ttk.Button(social, text="Developer settings",
                   command=app.developer_settings.show).pack(side="left", padx=5)
        ttk.Button(social, text="Play minigames",
                   command=lambda: app.game_window.show()).pack(side="left", padx=5)
        ttk.Button(social, text="Family stories / activity",
                   command=self.stories.show).pack(side="left")
        self.bonds = ttk.Label(frame, wraplength=540)
        self.bonds.pack(anchor="w")
        self.activity = ttk.Label(frame, wraplength=540)
        self.activity.pack(anchor="w", pady=3)
        settings = ttk.LabelFrame(frame, text="Settings — mouse petting", padding=4)
        settings.pack(fill="x")
        ttk.Label(settings, text="Recognize stroke pace:").grid(row=0, column=0, sticky="w")
        self.petting_speed = tk.StringVar(value="Any speed")
        ttk.Combobox(settings, textvariable=self.petting_speed,
                     values=("Any speed", "Slow", "Steady", "Quick"),
                     state="readonly", width=12).grid(row=0, column=1, padx=5, sticky="w")
        ttk.Label(settings, text="Move back and forth over the pigeon twice; match their favorite pace for bonus friendship.",
                  wraplength=560).grid(row=1, column=0, columnspan=2, sticky="w")
        governance = ttk.LabelFrame(frame, text="Visible synthetic targets only", padding=4)
        governance.pack(fill="x")
        self.intervention_buttons = {}
        for action in ("Shoo / catch", "Seed bribe / trade", "Laser distraction"):
            button = ttk.Button(governance, text=action, command=lambda action=action: app.intervene(action))
            button.pack(side="left", padx=2)
            self.intervention_buttons[action] = button
        protection = ttk.Frame(frame)
        protection.pack(fill="x")
        self.protection_buttons = {}
        for kind in ("Treasure", "Fragment"):
            button = ttk.Button(protection, command=lambda kind=kind: app.protect(kind))
            button.pack(side="left", padx=2)
            self.protection_buttons[kind] = button
        food_frame = ttk.LabelFrame(frame, text="Feed (seed mix is always free)", padding=5)
        food_frame.pack(fill="x")
        self.food_buttons = {}
        for index, food in enumerate(FOOD_TYPES):
            button = ttk.Button(food_frame, text=food.replace("_", " ").title(),
                                command=lambda food=food: app.feed(food))
            button.grid(row=index // 3, column=index % 3, padx=3, pady=2, sticky="ew")
            self.food_buttons[food] = button
        for column in range(3):
            food_frame.columnconfigure(column, weight=1)
        self.inventory_label = ttk.Label(frame)
        self.inventory_label.pack(anchor="w", pady=(10, 3))
        inventory = ttk.Frame(frame)
        inventory.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(inventory, columns=("name", "kind", "time"),
                                 show="headings", height=5)
        for column, title, width in (("name", "Collected item", 215),
                                     ("kind", "Type", 80), ("time", "Collected (UTC)", 165)):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, minwidth=60)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(inventory, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.return_button = ttk.Button(frame, text="Return selected gift / treasure to pigeon",
                                       command=app.return_selected)
        self.return_button.pack(anchor="w")
        self.notice = ttk.Label(frame, wraplength=540, foreground="#8d382a")
        self.notice.pack(anchor="w", pady=5)
        controls = ttk.Frame(frame)
        controls.pack(fill="x")
        self.shiny_button = ttk.Button(controls, text="Offer a shiny", command=app.offer_shiny)
        self.shiny_button.pack(side="left")
        self.pause_button = ttk.Button(controls, command=app.toggle_pause)
        self.pause_button.pack(side="left", padx=5)
        ttk.Button(controls, text="Quit", command=app.close).pack(side="right")

    def show(self) -> None:
        self.refresh()
        self.window.deiconify()
        self.window.lift()

    def _select_family(self):
        selected = self.family.selection()
        if not selected:
            return
        bird = next((b for b in self.app.flock.records if b.id == selected[0]), None)
        if bird is None:
            return
        if bird.legacy:
            legacy = bird.legacy
            self.legacy_info.configure(text=f"Legacy {bird.id}: {legacy.name} · {legacy.personality} · "
                                       f"rep {legacy.reputation} · {legacy.lifetime:.0f}s · {legacy.reason}")
        else:
            self.legacy_info.configure(text=f"Identity {bird.id} · active lifetime {bird.lifetime:.0f}s")
        self.app.select_bird(bird.id)

    def refresh(self) -> None:
        app = self.app
        pigeon = app.pigeon
        profile = app.nest.companion
        self.relationship.configure(text=f"Friendship: {profile.friendship}/100 — {profile.relationship}")
        self.friendship["value"] = profile.friendship
        self.personality.configure(text=f"Personality: {profile.personality} · "
                                        f"likes {profile.pet_speed_preference} petting")
        progress = profile.progression
        self.progress.configure(text=f"Reputation: {progress.reputation} — {progress.title}\n"
                                f"Trust: {progress.neglect_stage}"
                                + (f" — leaves in {120 - progress.grace:.0f} active seconds"
                                   if progress.neglect >= 240 and app.has_bird else ""))
        flock = app.flock
        cost = UPGRADE_COSTS[flock.level] if flock.level < 3 else None
        self.flock_summary.configure(text=f"{('Small', 'Expanded', 'Large', 'Grand')[flock.level]} nest: "
                                     f"{len(flock.active)}/{flock.capacity} · treasury {flock.treasury} · "
                                     f"social meetings {flock.interactions} · eggs: "
                                     + (", ".join(f"{e.remaining:.0f}s" for e in flock.eggs) or "none"))
        self.upgrade_button.configure(text=f"Upgrade ({cost} treasury)" if cost else "Grand nest",
                                      state="normal" if cost and not app.paused else "disabled")
        for button in (self.egg_button, self.adopt_button, self.rejoin_button):
            button.configure(state="disabled" if app.paused else "normal")
        ids = tuple(b.id for b in flock.records)
        if self.family.get_children() != ids:
            self.family.delete(*self.family.get_children())
            for bird in flock.records:
                self.family.insert("", "end", iid=bird.id)
        by_id = {b.id: b for b in flock.records}
        for bird in flock.records:
            self.family.item(bird.id, values=(bird.name, bird.generation,
                              by_id[bird.parent].name if bird.parent else "—",
                              bird.companion.progression.reputation,
                              bird.status + (" *" if bird.id == flock.selected_id else "")))
        self.journal.configure(text="Journal: " + (", ".join(progress.achievements[-6:]) or "No milestones yet."))
        bonds = sorted((b for b in flock.bonds if flock.selected_id in b.actors),
                       key=lambda b: all(by_id[i].status == "active" for i in b.actors), reverse=True)
        self.bonds.configure(text="Flock bonds (not human friendship): " + (
            "; ".join(f"{by_id[next(i for i in bond.actors if i != flock.selected_id)].name}: "
                      f"{bond.status} {bond.affinity:+d}"
                      for bond in bonds[:2]) or "none yet")
            + (f" · {len(bonds) - 2} more in stories" if len(bonds) > 2 else ""))
        if self.stories.window.state() != "withdrawn":
            self.stories.refresh()
        for button in self.intervention_buttons.values():
            button.configure(state="normal" if not app.paused and pigeon.treasure is not None
                             and progress.intervention_cooldown == 0 else "disabled")
        for kind, button in self.protection_buttons.items():
            button.configure(text=f"{'Unprotect' if kind in progress.protected else 'Protect'} {kind}",
                             state="disabled" if app.paused else "normal")
        self.return_button.configure(state="disabled" if app.paused else "normal")
        self.activity.configure(text=app.activity_status)
        self.pet_button.configure(state="disabled" if app.paused or profile.pet_cooldown > 0 else "normal")
        for food, button in self.food_buttons.items():
            portions = "free" if food == "seed_mix" else str(profile.food[food])
            button.configure(text=f"{food.replace('_', ' ').title()} ({portions})",
                             state="normal" if food == "seed_mix" or profile.food[food] else "disabled")
        self.summary.configure(text=f"Hunger: {pigeon.hunger_label} ({pigeon.hunger:.0f}/100)"
                               f" — {'Paused' if app.paused else pigeon.behavior.value}")
        self.hunger["value"] = pigeon.hunger
        self.pause_button.configure(text="Resume" if app.paused else "Pause")
        self.shiny_button.configure(state="disabled" if pigeon.treasure or app.paused else "normal")
        self.inventory_label.configure(
            text=f"Nest: {len(app.nest.items)} treasures / fragments / gifts (latest {MAX_STORED_ITEMS})")
        ids = tuple(item.id for item in reversed(app.nest.items))
        if self.tree.get_children() != ids:
            self.tree.delete(*self.tree.get_children())
            for item in reversed(app.nest.items):
                self.tree.insert("", "end", iid=item.id,
                                 values=(item.name, item.kind,
                                         item.collected_at[:19].replace("T", " ")))
        self.notice.configure(text=app.save_status or "Generated overlays only. No desktop files read.")
        if not app.has_bird:
            self.summary.configure(text="No active pigeon — invite a departed bird or adopt an egg.")
            for button in (self.pet_button, self.shiny_button, self.return_button,
                           *self.food_buttons.values(), *self.intervention_buttons.values(),
                           *self.protection_buttons.values()):
                button.configure(state="disabled")
