"""Live developer controls for tuning pigeon behavior and input."""

import tkinter as tk
from tkinter import ttk


class DeveloperSettings:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title("Desktop Pigeon — Developer Settings")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.window.withdraw)
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill="both", expand=True)

        self.speed = tk.DoubleVar(value=1.0)
        self.roam = tk.IntVar(value=200)
        self.rest = tk.DoubleVar(value=1.0)
        self.treasure_interval = tk.IntVar(value=30)
        for row, (label, variable, start, end, resolution) in enumerate((
            ("Movement speed", self.speed, 0.5, 3.0, 0.1),
            ("Roaming distance (pixels)", self.roam, 50, 600, 25),
            ("Rest duration", self.rest, 0.25, 2.0, 0.05),
            ("Treasure interval (seconds)", self.treasure_interval, 5, 120, 1),
        )):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            scale = tk.Scale(frame, variable=variable, from_=start, to=end,
                             resolution=resolution, orient="horizontal", length=230,
                             showvalue=True, command=self._apply)
            scale.grid(row=row, column=1, sticky="ew", padx=(10, 0))

        ttk.Separator(frame).grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(frame, text="Pet gesture").grid(row=5, column=0, sticky="w")
        self.gesture = tk.StringVar(value="Both")
        ttk.Combobox(frame, textvariable=self.gesture,
                     values=("Both", "Double-click", "Mouse strokes"),
                     state="readonly", width=18).grid(row=5, column=1, sticky="w")
        self.gesture.trace_add("write", self._apply)

        ttk.Label(frame, text="Pause/resume key").grid(row=6, column=0, sticky="w", pady=5)
        self.key_button = ttk.Button(frame, text="F8", command=self._capture_key)
        self.key_button.grid(row=6, column=1, sticky="w")
        ttk.Label(frame, text="Click the key button, then press the key to bind.",
                  wraplength=340).grid(row=7, column=0, columnspan=2, sticky="w")
        frame.columnconfigure(1, weight=1)

    def _apply(self, *_):
        self.app.apply_developer_settings(
            self.speed.get(), self.roam.get(), self.rest.get(),
            self.treasure_interval.get())

    def _capture_key(self):
        self.key_button.configure(text="Press a key…")
        self.app.capture_next_key(self._set_key)

    def _set_key(self, key):
        if key and key not in {
                "Alt_L", "Alt_R", "Control_L", "Control_R", "Escape", "Shift_L", "Shift_R",
                "Super_L", "Super_R"}:
            self.app.pause_key = key
            self.key_button.configure(text=key)
        else:
            self.key_button.configure(text=self.app.pause_key)

    def show(self):
        self.window.deiconify()
        self.window.lift()
