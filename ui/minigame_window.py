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
        self.overlay_open = False
        self.hit_regions = []
        self.panel_shift = 0
        self.window = app.root
        frame = ttk.Frame(app.root, padding=16)
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
        was_open = self.overlay_open
        self.overlay_open = False
        if was_open and not self.app.closed:
            self.app.render()

    def hide_memory(self):
        if not self.app.paused and isinstance(self.game, LocalGame):
            self.game.hide_memory()
            self.refresh()

    def show(self):
        if self.app.closed or not self.app.has_bird:
            return
        if (self.game is not None and not self.game.complete
                and self.participant != self.app.flock.selected_id):
            self.cancel()
        if self.game is None or self.game.complete:
            self.game = None
            self.game_name = None
            self.participant = self.app.flock.selected_id
            self.selection.set("Shiny Sorting")
        self.overlay_open = True
        self.refresh()
        self.app.render()

    def start(self):
        if self.app.closed or not self.app.has_bird or self.app.paused or (self.game is not None and not self.game.complete):
            return
        name = self.selection.get()
        profile = self.app.nest.companion
        if name == "Daily Foraging":
            if profile.progression.forage_cooldown > 0:
                self.feedback.configure(text="Daily Foraging rests for 300 active seconds between attempts.")
                self.app.render()
                return
            profile.progression.forage_cooldown = 300
            self.app.save()
        self.game = ShinySorting() if name == "Shiny Sorting" else LocalGame(name)
        self.participant = self.app.flock.selected_id
        self.app.flock.milestone(self.participant, "game")
        self.app.save()
        self.game_name = name
        self.overlay_open = True
        self._buttons(("Treasure", "Fragment") if name == "Shiny Sorting" else self.game.choices)
        self.feedback.configure(text="Tap an item or action in the pigeon overlay.")
        self.refresh()
        self.app.render()

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
        self.app.render()

    def refresh(self):
        active = self.game is not None and not self.game.complete
        revealing = active and getattr(self.game, "revealing", False)
        self.selector.configure(state="disabled" if active else "readonly")
        self.instructions.configure(text=INSTRUCTIONS[self.selection.get()] +
                                    "\nFive turns: 3+ correct earns a trinket, food, and friendship.")
        if self.app.paused:
            text = "Paused — resume from the nest."
        elif active:
            prompt = self.game.prompt if isinstance(self.game, LocalGame) else self.game.current[0]
            text = f"Round {self.game.index + 1}/5: {prompt}"
        elif self.game is not None:
            text = ("Cancelled — no reward." if self.game.cancelled
                    else f"Finished: {self.game.score}/5 correct")
        else:
            text = "Choose a game to play."
        self.prompt.configure(text=text)
        for button in self.buttons.values():
            button.configure(state="normal" if active and not self.app.paused and not revealing else "disabled")
        self.hide_button.configure(state="normal" if revealing and not self.app.paused else "disabled")
        self.start_button.configure(state="disabled" if active or self.app.paused else "normal")

    def overlay_layout(self, pigeon):
        width = min(500, max(240, self.app.bounds.width))
        height = min(340, max(220, self.app.bounds.height))
        offset_x, offset_y = 10, min(120, height - 100)
        right = self.app.bounds.x + self.app.bounds.width
        if right - pigeon.x < 390:
            x = pigeon.x + 96 - width + 10
            self.panel_shift = -104
        else:
            x = pigeon.x - offset_x
            self.panel_shift = 0
        x = min(max(x, self.app.bounds.x), right - width)
        y = min(max(pigeon.y - offset_y, self.app.bounds.y),
                self.app.bounds.y + self.app.bounds.height - height)
        return width, height, int(x), int(y), int(pigeon.x - x), int(pigeon.y - y)

    def handle_click(self, bird_id, x, y):
        if not self.overlay_open or bird_id != self.participant:
            return False
        x -= self.panel_shift
        if 450 <= x <= 492 and 8 <= y <= 48:
            self.cancel()
            return True
        for bounds, action, value in self.hit_regions:
            left, top, right, bottom = bounds
            if left <= x <= right and top <= y <= bottom:
                if action == "select":
                    names = list(GAME_NAMES)
                    index = names.index(self.selection.get())
                    self.selection.set(names[(index + value) % len(names)])
                    self.app.render()
                elif action == "start":
                    self.start()
                elif action == "hide":
                    self.hide_memory()
                    self.app.render()
                elif action == "answer":
                    self.answer(value)
                elif action == "close":
                    self.cancel()
                return True
        return True

    def _hit(self, canvas, bounds, action, value=None, label="", color="#dde7da"):
        left, top, right, bottom = bounds
        canvas.create_rectangle(left, top, right, bottom, fill=color, outline="#9caaa1",
                                width=1)
        canvas.create_text((left + right) / 2, (top + bottom) / 2, text=label,
                           fill="#253a3e", font=("TkDefaultFont", 9, "bold"),
                           width=max(40, right - left - 8))
        self.hit_regions.append((bounds, action, value))

    def draw_overlay(self, canvas):
        self.hit_regions = []
        if not self.overlay_open:
            return
        before = set(canvas.find_all())
        canvas.create_rectangle(112, 8, 492, 332, fill="#ecf1eb",
                                outline="#a6bbaf", width=2)
        canvas.create_text(126, 23, text="Pigeon games · tap a choice",
                           anchor="w", fill="#253a3e",
                           font=("TkDefaultFont", 10, "bold"))
        canvas.create_text(472, 22, text="×", fill="#753b35",
                           font=("TkDefaultFont", 16, "bold"))
        if self.app.paused:
            canvas.create_text(302, 150, text="Paused — resume from the nest",
                               fill="#253a3e", font=("TkDefaultFont", 12, "bold"),
                               width=300)
            return
        if self.game is None or self.game.complete:
            self._draw_picker(canvas)
        else:
            self._draw_round(canvas)
        created = set(canvas.find_all()) - before
        for item in created:
            canvas.addtag_withtag("game_panel", item)
        if self.panel_shift:
            canvas.move("game_panel", self.panel_shift, 0)

    def _draw_picker(self, canvas):
        canvas.create_text(302, 68, text=self.selection.get(), fill="#253a3e",
                           font=("TkDefaultFont", 14, "bold"))
        names = list(GAME_NAMES)
        index = names.index(self.selection.get())
        canvas.create_text(153, 68, text="‹", font=("TkDefaultFont", 22, "bold"),
                           fill="#253a3e")
        canvas.create_text(451, 68, text="›", font=("TkDefaultFont", 22, "bold"),
                           fill="#253a3e")
        self.hit_regions.extend([
            ((126, 48, 178, 90), "select", -1),
            ((425, 48, 477, 90), "select", 1),
        ])
        canvas.create_text(302, 116, text=INSTRUCTIONS[names[index]],
                           width=330, justify="center", fill="#344557")
        canvas.create_text(302, 177, text="Five turns · 3 correct earns a trinket and food",
                           width=330, justify="center", fill="#344557")
        canvas.create_text(302, 204, text=self.feedback.cget("text"),
                           width=330, fill="#344557", font=("TkDefaultFont", 8))
        self._hit(canvas, (218, 224, 386, 270), "start", label="Start game",
                  color="#d4e3cf")
        self._hit(canvas, (218, 280, 386, 316), "hide", label="Close",
                  color="#e4e8e2")
        self.hit_regions[-1] = ((218, 280, 386, 316), "close", None)

    def _draw_round(self, canvas):
        canvas.create_text(132, 52, text=f"{self.game_name} · {self.game.index + 1}/5",
                           anchor="w", fill="#253a3e",
                           font=("TkDefaultFont", 11, "bold"))
        instruction = INSTRUCTIONS[self.game_name]
        canvas.create_text(132, 78, text=instruction, anchor="nw", width=338,
                           fill="#344557", font=("TkDefaultFont", 8))
        if isinstance(self.game, LocalGame):
            self._draw_local_scene(canvas)
        else:
            self._draw_sorting_scene(canvas)
        canvas.create_text(302, 304, text=self.feedback.cget("text"),
                           width=345, fill="#344557",
                           font=("TkDefaultFont", 9, "bold"))

    def _draw_sorting_scene(self, canvas):
        name, kind, color = self.game.current
        canvas.create_polygon(302, 113, 323, 134, 302, 155, 281, 134,
                              fill=color, outline="#7c6537", width=2)
        canvas.create_text(302, 169, text=name, fill="#253a3e")
        self._hit(canvas, (130, 208, 294, 256), "answer", "Treasure",
                  "Treasure", "#ead9a9")
        self._hit(canvas, (310, 208, 474, 256), "answer", "Fragment",
                  "Fragment", "#d9dfe5")

    def _draw_local_scene(self, canvas):
        if self.game.name == "Peck Finder":
            for number in range(1, 10):
                row, col = divmod(number - 1, 3)
                x, y = 188 + col * 78, 145 + row * 48
                correct = number == self.game.current
                color = "#d5bd83" if correct else "#aab4b6"
                canvas.create_oval(x - 17, y - 17, x + 17, y + 17,
                                   fill=color, outline="#6e7779", width=2)
                canvas.create_text(x, y, text="●" if correct else "·",
                                   fill="#76552f" if correct else "#596577",
                                   font=("TkDefaultFont", 13, "bold"))
                self.hit_regions.append(((x - 25, y - 22, x + 25, y + 22),
                                         "answer", str(number)))
            return
        if self.game.name == "Follow Crumb Trail":
            canvas.create_text(302, 122, text="Follow the crumbs in order",
                               fill="#253a3e")
            for index in range(5):
                x, y = 154 + index * 74, 181 + (index % 2) * 20
                canvas.create_oval(x - 18, y - 18, x + 18, y + 18,
                                   fill="#c5a773" if index >= self.game.index else "#a8b8aa",
                                   outline="#76552f", width=2)
                canvas.create_text(x, y, text=str(index + 1), fill="#253a3e")
                self.hit_regions.append(((x - 24, y - 24, x + 24, y + 24),
                                         "answer", str(index + 1)))
            return
        if self.game.name == "Rooftop Dash":
            canvas.create_text(302, 122, text=f"Roof ahead: {self.game.current}",
                               fill="#253a3e", font=("TkDefaultFont", 11, "bold"))
        if self.game.name == "Human Inspection":
            canvas.create_text(302, 122, text=self.game.current,
                               fill="#253a3e", font=("TkDefaultFont", 10, "bold"))
        if self.game.name == "Pigeon Memory":
            if self.game.revealing:
                canvas.create_text(302, 125, text="Remember this order, then tap Hide",
                                   fill="#253a3e")
                palette = {"Red": "#d4685d", "Blue": "#6689b5", "Gold": "#d6ad4d"}
                for index, color in enumerate(self.game.rounds):
                    x = 168 + index * 66
                    canvas.create_oval(x - 17, 157, x + 17, 191,
                                       fill=palette[color], outline="#53616a")
                self._hit(canvas, (218, 214, 386, 256), "hide",
                          label="Hide sequence")
            else:
                self._draw_choice_cards(canvas, self.game.choices,
                                        {"Red": "#d4685d", "Blue": "#6689b5",
                                         "Gold": "#d6ad4d"})
            return
        icons = {
            "Rooftop Dash": {"Jump": "↗", "Duck": "⌒", "Run": "→"},
            "Human Inspection": {"Approach": "✦", "Wait": "…", "Retreat": "←"},
            "Daily Foraging": {"Search": "Seeds", "Rest": "Rest"},
        }[self.game.name]
        if self.game.name == "Daily Foraging":
            canvas.create_text(302, 116, text=f"Energy {self.game.energy}",
                               fill="#253a3e", font=("TkDefaultFont", 11, "bold"))
        self._draw_choice_cards(canvas, self.game.choices, icons)

    def _draw_choice_cards(self, canvas, choices, icons=None):
        icons = icons or {}
        columns = len(choices)
        card_width = min(104, 340 // columns)
        start = 302 - (card_width * columns + 8 * (columns - 1)) / 2
        for index, choice in enumerate(choices):
            left = int(start + index * (card_width + 8))
            top = 147 if self.game.name != "Daily Foraging" else 164
            bounds = (left, top, left + card_width, top + 88)
            self._hit(canvas, bounds, "answer", choice,
                      f"{icons.get(choice, choice)}\n{choice}", "#dde7da")
