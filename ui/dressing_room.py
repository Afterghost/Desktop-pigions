"""Pigeon outfit selection and live expression preview."""

import math
import tkinter as tk
from tkinter import ttk

from companion import ATTIRE
from ui.pigeon_sprite import draw_pigeon


class DressingRoom:
    def __init__(self, app):
        self.app = app
        self.look_phase = 0.0
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title("Desktop Pigeon — Dressing Room")
        self.window.geometry("340x390")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.window.withdraw)
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill="both", expand=True)
        self.name = ttk.Label(frame, font=("TkDefaultFont", 11, "bold"))
        self.name.pack()
        self.canvas = tk.Canvas(frame, width=220, height=150, bg="#f4f0e7",
                                highlightthickness=0)
        self.canvas.pack(pady=8)
        self.expression = ttk.Label(frame, wraplength=300, justify="center")
        self.expression.pack(pady=4)
        self.preference = ttk.Label(frame, wraplength=300, justify="center")
        self.preference.pack(pady=4)
        self.buttons = {}
        options = ttk.Frame(frame)
        options.pack(fill="x", pady=6)
        for index, outfit in enumerate(ATTIRE):
            button = ttk.Button(options, text=outfit,
                                command=lambda outfit=outfit: app.set_outfit(outfit))
            button.grid(row=index // 3, column=index % 3, padx=2, pady=2, sticky="ew")
            self.buttons[outfit] = button
        for column in range(3):
            options.columnconfigure(column, weight=1)
        ttk.Button(frame, text="Done", command=self.window.withdraw).pack(pady=5)

    def show(self):
        if self.app.closed or not self.app.has_bird:
            return
        self.refresh()
        self.window.deiconify()
        self.window.lift()

    def refresh(self):
        if self.app.closed or self.window.state() == "withdrawn" or not self.app.has_bird:
            return
        record = self.app.flock.selected
        pigeon = self.app.pigeon
        profile = record.companion
        approved = profile.outfit == profile.appeal_preference
        expression = "happy" if approved else "displeased"
        self.look_phase += 0.16
        self.canvas.delete("all")
        draw_pigeon(self.canvas, pigeon, self.look_phase, self.app.paused,
                    outfit=profile.outfit, expression=expression,
                    look_phase=math.sin(self.look_phase))
        self.canvas.move("all", 62, 32)
        self.name.configure(text=f"{record.name}'s dressing room")
        self.expression.configure(
            text=("♥  Loves this look!" if approved else "Hmm… not quite their style.")
                 + ("  ☺" if approved else "  ☹"))
        self.preference.configure(
            text=f"{record.name} loves {profile.appeal_preference.lower()} looks. "
                 f"Current outfit: {profile.outfit.lower()}.")
        for outfit, button in self.buttons.items():
            button.configure(state="disabled" if self.app.paused else "normal",
                             text=f"✓ {outfit}" if outfit == profile.outfit else outfit)
