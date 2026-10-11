"""Shiny Sorting: a local, untimed five-round classification minigame."""

import tkinter as tk
from tkinter import ttk

from minigames import ShinySorting, LocalGame, INSTRUCTIONS
from progression import GAME_NAMES


class MinigameWindow:
    def __init__(self, app):
        self.app = app
        self.game = None
        self.participant = None
        self.game_name = None
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title("Desktop Pigeon — Shiny Sorting")
        self.window.geometry("620x460")
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.bind("<Escape>", lambda event: self.cancel() or "break")
        frame = ttk.Frame(self.window, padding=16)
        frame.pack(fill="both", expand=True)
        self.selection = tk.StringVar(value="Shiny Sorting")
        self.selector = ttk.Combobox(frame, textvariable=self.selection, values=GAME_NAMES, state="readonly")
        self.selector.pack()
        self.instructions = ttk.Label(frame, wraplength=560)
        self.instructions.pack()
        self.selector.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        self.prompt = ttk.Label(frame, font=("TkDefaultFont", 13, "bold"))
        self.prompt.pack(pady=14)
        self.feedback = ttk.Label(frame, wraplength=400)
        self.feedback.pack(pady=5)
        self.choices = ttk.Frame(frame)
        self.choices.pack()
        self.buttons = {}
        self._buttons(("Treasure", "Fragment"))
        self.hide_button = ttk.Button(frame, text="Hide / recall", command=self.hide_memory)
        self.hide_button.pack()
        self.start_button = ttk.Button(frame, text="Start / play again", command=self.start)
        self.start_button.pack(pady=12)
        ttk.Button(frame, text="Cancel round / close (no reward)", command=self.cancel).pack()

    def _buttons(self, options):
        for button in self.buttons.values():
            button.destroy()
        self.buttons = {}
        for index, kind in enumerate(options):
            button = ttk.Button(self.choices, text=kind, command=lambda kind=kind: self.answer(kind))
            button.grid(row=index // 3, column=index % 3, padx=4, pady=3)
            self.buttons[kind] = button

    def cancel(self):
        if self.game is not None and not self.game.complete:
            self.game.cancel()
        self.window.withdraw()

    def hide_memory(self):
        if not self.app.paused and isinstance(self.game, LocalGame):
            self.game.hide_memory()
            self.refresh()

    def show(self):
        self.refresh()
        self.window.deiconify()
        self.window.lift()

    def start(self):
        if self.app.closed or not self.app.has_bird or self.app.paused or (self.game is not None and not self.game.complete):
            return
        name = self.selection.get()
        profile = self.app.nest.companion
        if name == "Daily Foraging":
            if profile.progression.forage_cooldown > 0:
                self.feedback.configure(text="Daily Foraging rests for 300 active seconds between attempts.")
                return
            profile.progression.forage_cooldown = 300
            self.app.save()
        self.game = ShinySorting() if name == "Shiny Sorting" else LocalGame(name)
        self.participant = self.app.flock.selected_id
        self.game_name = name
        self._buttons(("Treasure", "Fragment") if name == "Shiny Sorting" else self.game.choices)
        self.feedback.configure(text="Buttons and marbles are treasures; foil and paper are fragments.")
        self.refresh()

    def answer(self, kind):
        if (self.app.closed or self.app.paused or self.game is None or self.game.complete
                or self.participant != self.app.flock.selected_id or not self.app.has_bird):
            return
        correct = self.game.answer(kind)
        self.feedback.configure(text="Correct!" if correct else "Not quite — try the next shiny.")
        if self.game.complete:
            score = self.game.claim_reward()
            if score is not None:
                if self.app.reward_game(score, self.participant):
                    self.app.nest.companion.progression.unlock(self.game_name)
                    self.app.save()
                    self.feedback.configure(text=self.app.activity_status)
            else:
                self.feedback.configure(text="No reward this time. Try again for at least 3 correct.")
        self.refresh()

    def refresh(self):
        active = self.game is not None and not self.game.complete
        revealing = active and getattr(self.game, "revealing", False)
        self.selector.configure(state="disabled" if active else "readonly")
        self.instructions.configure(text=INSTRUCTIONS[self.selection.get()] +
                                    "\nFive turns: 3+ correct earns food and friendship; perfect earns corn.")
        if self.app.paused:
            text = "Paused — resume from the nest."
        elif active:
            prompt = self.game.prompt if isinstance(self.game, LocalGame) else self.game.current[0]
            text = f"Round {self.game.index + 1}/5: {prompt}"
        elif self.game is not None:
            text = ("Cancelled — no reward." if self.game.cancelled
                    else f"Finished: {self.game.score}/5 correct")
        else:
            text = "Ready to sort?"
        self.prompt.configure(text=text)
        for button in self.buttons.values():
            button.configure(state="normal" if active and not self.app.paused and not revealing else "disabled")
        self.hide_button.configure(state="normal" if revealing and not self.app.paused else "disabled")
        self.start_button.configure(state="disabled" if active or self.app.paused else "normal")
