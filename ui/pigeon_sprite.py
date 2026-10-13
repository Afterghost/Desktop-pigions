"""Procedural pigeon art, with walking, pecking, carrying, and feeding feedback."""

import math
import tkinter as tk

from pigeon import Behavior, Pigeon


def _trait_color(pigeon: Pigeon, palette: dict[str, str], fallback: str) -> str:
    traits = pigeon.companion.traits if pigeon.companion else {}
    total = sum(traits.values())
    if not total:
        return fallback
    channels = [
        round(sum(int(palette[name][index:index + 2], 16) * value
                  for name, value in traits.items()) / total)
        for index in (1, 3, 5)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def draw_pigeon(canvas: tk.Canvas, pigeon: Pigeon, phase: float, paused: bool,
                holding_pointer: bool = False, paper_tears=(),
                feather_playing: bool = False, outfit: str | None = None,
                expression: str | None = None, look_phase: float = 0) -> None:
    canvas.delete("all")
    body_color = _trait_color(
        pigeon, {"curiosity": "#aab4c4", "calm": "#a7b6ae", "sociability": "#b6a6b3"},
        "#a7b3c2")
    wing_color = _trait_color(
        pigeon, {"curiosity": "#75889e", "calm": "#71897f", "sociability": "#907783"},
        "#75889e")
    head_color = _trait_color(
        pigeon, {"curiosity": "#718499", "calm": "#698e84", "sociability": "#947986"},
        "#718499")
    walking = pigeon.behavior in (Behavior.ROAMING, Behavior.APPROACHING, Behavior.ESCAPING)
    bob = math.sin(phase * 14) * 2 if walking and not paused else 0
    peck = 7 if pigeon.behavior == Behavior.THEFT and int(phase * 5) % 2 else 0

    def points(*coords):
        result = []
        for index, value in enumerate(coords):
            if index % 2 == 0:
                result.append(value if pigeon.facing_right else 96 - value)
            else:
                result.append(value + bob)
        return result

    def oval(x1, y1, x2, y2, **kwargs):
        x1, y1, x2, y2 = points(x1, y1, x2, y2)
        canvas.create_oval(min(x1, x2), y1, max(x1, x2), y2, **kwargs)

    def arc(x1, y1, x2, y2, **kwargs):
        x1, y1, x2, y2 = points(x1, y1, x2, y2)
        canvas.create_arc(min(x1, x2), y1, max(x1, x2), y2, **kwargs)

    label = "Paused" if paused else f"{pigeon.hunger_label} {pigeon.hunger:.0f}%"
    if pigeon.fed_for > 0:
        label = "Coo! Thank you!"
    canvas.create_text(48, 10, text=label, fill="#9d342c" if pigeon.hunger > 70 else "#344557",
                       font=("TkDefaultFont", 9, "bold"))
    stride = math.sin(phase * 14) * 4 if walking and not paused else 0
    for x, lift in ((40, stride), (57, -stride)):
        canvas.create_line(*points(x, 70, x + lift, 83, x + lift + 7, 83),
                           fill="#c86c60", width=3)
    canvas.create_polygon(*points(27, 58, 5, 70, 34, 73),
                          fill="#647488", outline="#3d4b5c")
    oval(23, 40, 72, 77, fill=body_color, outline="#526075", width=2)
    oval(27, 48, 61, 71, fill=wing_color, outline="#526075", width=2)
    canvas.create_line(*points(33, 60, 51, 65), fill="#becad6", width=2)
    oval(54, 32 + peck, 76, 60 + peck, fill="#579c91", outline="#3c746d")
    oval(54, 23 + peck, 82, 47 + peck, fill=head_color, outline="#3d4b5c", width=2)
    eye_x = 75 + math.sin(look_phase) * 2
    oval(eye_x - 2.5, 29 + peck, eye_x + 2.5, 34 + peck,
         fill="#111921", outline="white")
    canvas.create_polygon(*points(80, 35 + peck, 93, 39 + peck, 80, 42 + peck),
                          fill="#dcad71", outline="#8a6842")
    if expression == "happy":
        arc(76, 38, 85, 46, start=200, extent=140, style="arc",
            outline="#28323b", width=2)
    elif expression == "displeased":
        canvas.create_line(*points(76, 44, 81, 41, 86, 44), fill="#28323b", width=2)
    elif expression == "curious":
        canvas.create_oval(*points(75, 38, 86, 47), outline="#28323b", width=2)
    if pigeon.hunger > 90:
        canvas.create_line(*points(70, 27 + peck, 79, 30 + peck), fill="#27313e", width=2)
    if pigeon.startled:
        canvas.create_text(49, 25, text="!", fill="#e26e31",
                           font=("TkDefaultFont", 16, "bold"))
        canvas.create_line(*points(30, 45, 20, 32), fill="#becad6", width=4)
        canvas.create_line(*points(63, 44, 72, 30), fill="#becad6", width=4)
    if holding_pointer:
        canvas.create_polygon(*points(38, 32, 38, 51, 43, 46, 47, 55, 51, 53,
                                     47, 44, 54, 44),
                              fill="white", outline="#19232d", width=2)
    if pigeon.carrying and pigeon.treasure is not None:
        canvas.create_polygon(*points(88, 43, 95, 50, 88, 57, 81, 50),
                              fill=pigeon.treasure.color, outline="#7c6537")
    outfit = outfit or (pigeon.companion.outfit if pigeon.companion else "Natural")
    if outfit == "Ribbon":
        canvas.create_polygon(*points(62, 25, 56, 18, 64, 20, 68, 15, 69, 25),
                              fill="#dc7184", outline="#8d4352")
    elif outfit == "Scarf":
        canvas.create_polygon(*points(56, 51, 77, 51, 75, 58, 58, 58),
                              fill="#8e6eb3", outline="#594778")
        canvas.create_polygon(*points(59, 56, 66, 57, 61, 68),
                              fill="#8e6eb3", outline="#594778")
    elif outfit == "Cap":
        arc(57, 17, 82, 35, start=0, extent=180, style="pieslice",
            fill="#d1aa55", outline="#806538")
        canvas.create_line(*points(58, 27, 81, 27), fill="#806538", width=3)
    elif outfit == "Flower":
        x = 63 if pigeon.facing_right else 33
        for angle in range(0, 360, 90):
            radians = math.radians(angle)
            canvas.create_oval(x + math.cos(radians) * 4 - 3,
                               24 + math.sin(radians) * 4 - 3,
                               x + math.cos(radians) * 4 + 3,
                               24 + math.sin(radians) * 4 + 3,
                               fill="#ed9aaf", outline="#b95d76")
        canvas.create_oval(x - 2, 22, x + 2, 26, fill="#e7c45b", outline="")
    for tear in paper_tears:
        progress = min(1, tear["age"] / 0.3)
        fade = min(1, (9 - tear["age"]) / 2)
        size = 17 * progress * fade
        x, y = tear["x"], tear["y"]
        canvas.create_polygon(x - size, y, x - size / 3, y - 3, x, y + 2,
                              x + size, y, x + size * 0.3, y + size * 0.55,
                              fill="#f3ecd9", outline="#b7ac94")
        for index in range(2):
            sx = x + math.sin(tear["angle"] + index * 2) * tear["age"] * 5
            sy = y + progress * (8 + index * 5)
            small = 2.5 * fade
            canvas.create_polygon(sx - small, sy, sx + small, sy - small,
                                  sx + small / 2, sy + small,
                                  fill="#e2d6ba", outline="")
    if feather_playing:
        canvas.create_oval(70, 50, 83, 68, fill="#c8a2d4", outline="#876094")
        canvas.create_line(80, 52, 73, 70, fill="#785785", width=2)
