"""Nest inventory and companion controls."""

import tkinter as tk
from tkinter import ttk

from config import FOOD_TYPES, MAX_STORED_ITEMS, NEST_HEIGHT, NEST_WIDTH


class NestWindow:
    def __init__(self, app):
        self.app = app
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
        self.progress = ttk.Label(frame, wraplength=620)
        self.progress.pack(anchor="w")
        self.journal = ttk.Label(frame, wraplength=620)
        self.journal.pack(anchor="w")
        social = ttk.Frame(frame)
        social.pack(fill="x", pady=5)
        self.pet_button = ttk.Button(social, text="Pet pigeon", command=app.pet)
        self.pet_button.pack(side="left")
        ttk.Button(social, text="Play minigames",
                   command=lambda: app.game_window.show()).pack(side="left", padx=5)
        self.activity = ttk.Label(frame, wraplength=540)
        self.activity.pack(anchor="w", pady=3)
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

    def refresh(self) -> None:
        app = self.app
        pigeon = app.pigeon
        profile = app.nest.companion
        self.relationship.configure(text=f"Friendship: {profile.friendship}/100 — {profile.relationship}")
        self.friendship["value"] = profile.friendship
        self.personality.configure(text=f"Personality: {profile.personality}")
        progress = profile.progression
        self.progress.configure(text=f"Reputation: {progress.reputation} — {progress.title}\n"
                                f"Trust: {progress.neglect_stage}")
        self.journal.configure(text="Journal: " + (", ".join(progress.achievements[-6:]) or "No milestones yet."))
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
