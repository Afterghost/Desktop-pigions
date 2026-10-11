"""Shiny Sorting: a local, untimed five-round classification minigame."""

import tkinter as tk
from tkinter import ttk

from minigames import ShinySorting


class MinigameWindow:
    def __init__(self, app):
        self.app = app
        self.game = None
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title("Desktop Pigeon — Shiny Sorting")
        self.window.geometry("440x280")
        self.window.protocol("WM_DELETE_WINDOW", self.window.withdraw)
        self.window.bind("<Escape>", lambda event: self.window.withdraw())
        frame = ttk.Frame(self.window, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Sort five shinies into Treasure or Fragment.\n"
                  "3+ correct earns food; 5 correct earns bonus corn.",
                  wraplength=400).pack()
        self.prompt = ttk.Label(frame, font=("TkDefaultFont", 13, "bold"))
        self.prompt.pack(pady=14)
        self.feedback = ttk.Label(frame, wraplength=400)
        self.feedback.pack(pady=5)
        choices = ttk.Frame(frame)
        choices.pack()
        self.buttons = {}
        for kind in ("Treasure", "Fragment"):
            button = ttk.Button(choices, text=kind, command=lambda kind=kind: self.answer(kind))
            button.pack(side="left", padx=5)
            self.buttons[kind] = button
        self.start_button = ttk.Button(frame, text="Start / play again", command=self.start)
        self.start_button.pack(pady=12)

    def show(self):
        self.refresh()
        self.window.deiconify()
        self.window.lift()

    def start(self):
        if self.app.paused or (self.game is not None and not self.game.complete):
            return
        self.game = ShinySorting()
        self.feedback.configure(text="Buttons and marbles are treasures; foil and paper are fragments.")
        self.refresh()

    def answer(self, kind):
        if self.app.paused or self.game is None or self.game.complete:
            return
        correct = self.game.answer(kind)
        self.feedback.configure(text="Correct!" if correct else "Not quite — try the next shiny.")
        if self.game.complete:
            score = self.game.claim_reward()
            if score is not None:
                self.app.reward_game(score)
                self.feedback.configure(text=self.app.activity_status)
            else:
                self.feedback.configure(text="No reward this time. Try again for at least 3 correct.")
        self.refresh()

    def refresh(self):
        active = self.game is not None and not self.game.complete
        if self.app.paused:
            text = "Paused — resume from the nest."
        elif active:
            text = f"Round {self.game.index + 1}/5: {self.game.current[0]}"
        elif self.game is not None:
            text = f"Finished: {self.game.score}/5 correct"
        else:
            text = "Ready to sort?"
        self.prompt.configure(text=text)
        for button in self.buttons.values():
            button.configure(state="normal" if active and not self.app.paused else "disabled")
        self.start_button.configure(state="disabled" if active or self.app.paused else "normal")
