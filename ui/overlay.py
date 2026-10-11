"""Small, topmost overlay windows instead of a desktop-sized input blocker."""

import sys
import tkinter as tk


class Overlay:
    def __init__(self, window: tk.Tk | tk.Toplevel, size: int):
        self.window = window
        self.size = size
        self.background = "#faf0df"
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        if sys.platform == "win32":
            self.background = "#ff00ff"
            window.attributes("-transparentcolor", self.background)
            window.attributes("-toolwindow", True)
        self.canvas = tk.Canvas(window, width=size, height=size, highlightthickness=0,
                                bg=self.background)
        self.canvas.pack()

    def place(self, x: float, y: float) -> None:
        self.window.geometry(f"{self.size}x{self.size}{int(x):+d}{int(y):+d}")
        if self.window.state() == "withdrawn":
            self.window.deiconify()

    def hide(self) -> None:
        self.window.withdraw()

    def draw_nest(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        canvas.create_oval(5, 25, 58, 51, fill="#ae8051", outline="#70482c", width=3)
        canvas.create_oval(10, 26, 53, 40, fill="#614931", outline="#d8b17b", width=2)
        for x in range(8, 52, 9):
            canvas.create_line(x, 40, x + 10, 49, fill="#ebc590", width=2)
        canvas.create_text(32, 12, text="Nest", fill="#473523", font=("TkDefaultFont", 10))

    def draw_treasure(self, color: str, phase: float, stealing: bool) -> None:
        canvas = self.canvas
        canvas.delete("all")
        radius = 10 + (int(phase * 5) % 3)
        canvas.create_polygon(20, 20 - radius, 20 + radius, 20, 20, 20 + radius,
                              20 - radius, 20, fill=color, outline="#7c6537", width=2)
        canvas.create_line(3, 3, 10, 10, fill="#e6ad24", width=2)
        canvas.create_line(30, 10, 37, 3, fill="#e6ad24", width=2)
        if stealing:
            canvas.create_oval(1, 1, 39, 39, outline="#e6ad24", width=2)
