"""Compact actions shown above a pigeon after a right-click."""

import tkinter as tk

from config import FOOD_TYPES, PIGEON_SIZE


class BirdMenu:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#72553c")
        frame = tk.Frame(self.window, bg="#fff7e8", bd=2, relief="ridge", padx=4, pady=3)
        frame.pack()

        self.food_menu = tk.Menu(self.window, tearoff=False)
        for food in FOOD_TYPES:
            self.food_menu.add_command(
                label=food.replace("_", " ").title(),
                command=lambda food=food: self._act(lambda: app.feed(food)),
            )
        self.feed_button = tk.Button(frame, text="Feed", command=self.show_food,
                                     relief="flat", bg="#f4d9a8", activebackground="#e8c586")
        self.feed_button.pack(side="left", padx=2)
        self.play_button = tk.Button(frame, text="Play", command=lambda: self._act(app.game_window.show),
                                     relief="flat", bg="#d8e5cf", activebackground="#bed3ae")
        self.play_button.pack(side="left", padx=2)
        self.shoo_button = tk.Button(
            frame, text="Shoo", command=lambda: self._act(lambda: app.intervene("Shoo / catch")),
            relief="flat", bg="#e8d4d0", activebackground="#d8b9b1",
        )
        self.shoo_button.pack(side="left", padx=2)
        self.window.bind("<Escape>", lambda event: self.hide())

    def _act(self, action):
        self.hide()
        action()

    def show_food(self):
        self.window.update_idletasks()
        self.food_menu.tk_popup(self.feed_button.winfo_rootx(),
                                self.feed_button.winfo_rooty() + self.feed_button.winfo_height())
        self.food_menu.grab_release()

    def show(self, pigeon_x: int, pigeon_y: int, bounds) -> None:
        self.window.deiconify()
        self.window.update_idletasks()
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        x = pigeon_x + PIGEON_SIZE // 2 - width // 2
        x = max(bounds.x, min(x, bounds.x + bounds.width - width))
        y = max(bounds.y, pigeon_y - height - 8)
        self.window.geometry(f"+{x}+{y}")
        self.window.lift()

    def hide(self) -> None:
        self.window.withdraw()
