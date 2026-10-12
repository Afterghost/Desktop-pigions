"""Work-area bounds and synthetic treasures; never inspect desktop content."""

from dataclasses import dataclass
import random
import sys

from config import PIGEON_SIZE, ROAM_RADIUS


@dataclass(frozen=True)
class Bounds:
    x: int
    y: int
    width: int
    height: int

    def clamp(self, x: float, y: float) -> tuple[float, float]:
        return (
            max(self.x, min(x, self.x + max(0, self.width - PIGEON_SIZE))),
            max(self.y, min(y, self.y + max(0, self.height - PIGEON_SIZE))),
        )

    def nearby(self, x: float, y: float, rng: random.Random) -> tuple[float, float]:
        return self.clamp(
            x + rng.uniform(-ROAM_RADIUS, ROAM_RADIUS),
            y + rng.uniform(-ROAM_RADIUS, ROAM_RADIUS),
        )


def work_area(screen_width: int, screen_height: int) -> Bounds:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return Bounds(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    return Bounds(0, 0, screen_width, screen_height)


TREASURES = (
    ("Shiny button", "Treasure", "#f6c453"),
    ("Blue marble", "Treasure", "#72c9ed"),
    ("Silver foil fragment", "Fragment", "#cbd4df"),
    ("Rainbow paper fragment", "Fragment", "#d49bee"),
)


@dataclass(frozen=True)
class Treasure:
    name: str
    kind: str
    color: str
    x: float
    y: float


def make_treasure(bounds: Bounds, x: float, y: float, rng: random.Random) -> Treasure:
    name, kind, color = rng.choice(TREASURES)
    tx, ty = bounds.nearby(x, y, rng)
    return Treasure(name, kind, color, tx, ty)
