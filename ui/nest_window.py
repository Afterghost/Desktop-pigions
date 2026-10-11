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
        self.window.geometry(f"{NEST_WIDTH}x{NEST_HEIGHT}")
        self.window.minsize(540, 400)
        self.window.protocol("WM_DELETE_WINDOW", self.window.withdraw)
        self.window.bind("<Escape>", lambda event: self.window.withdraw())
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill="both", expand=True)
        self.summary = ttk.Label(frame, font=("TkDefaultFont", 11, "bold"))
        self.summary.pack(anchor="w")
        self.hunger = ttk.Progressbar(frame, maximum=100)
        self.hunger.pack(fill="x", pady=(5, 8))
        food_frame = ttk.LabelFrame(frame, text="Feed your pigeon (free in Phase 1)", padding=5)
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
        self.summary.configure(text=f"Hunger: {pigeon.hunger_label} ({pigeon.hunger:.0f}/100)"
                               f" — {'Paused' if app.paused else pigeon.behavior.value}")
        self.hunger["value"] = pigeon.hunger
        self.pause_button.configure(text="Resume" if app.paused else "Pause")
        self.shiny_button.configure(state="disabled" if pigeon.treasure else "normal")
        self.inventory_label.configure(
            text=f"Nest: {len(app.nest.items)} treasures / fragments (keeps latest {MAX_STORED_ITEMS})")
        ids = tuple(item.id for item in reversed(app.nest.items))
        if self.tree.get_children() != ids:
            self.tree.delete(*self.tree.get_children())
            for item in reversed(app.nest.items):
                self.tree.insert("", "end", iid=item.id,
                                 values=(item.name, item.kind,
                                         item.collected_at[:19].replace("T", " ")))
        self.notice.configure(text=app.save_status or "Generated overlays only. No desktop files read.")
