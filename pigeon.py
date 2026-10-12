"""Headless, in-memory simulation for the desktop pigeon overlay."""

from dataclasses import dataclass
import math
import random

import config


MAX_ITEMS = 20
MAX_TEARS = 8
TEAR_LIFETIME = 9.0
EAT_DURATION = 1.2
PLAY_DURATION = 2.0


@dataclass
class Item:
    kind: str
    x: float
    y: float


@dataclass
class Tear:
    x: float
    y: float
    age: float = 0.0
    angle: float = 0.0


class Pigeon:
    """All state is session-local; food costs are not charged (no economy yet)."""

    def __init__(self, width, height, rng=None):
        self.rng = rng if rng is not None else random.Random()
        self.width = width
        self.height = height
        self.x, self.y = width / 2, height / 2
        self.hunger = 45
        self.friendship = 0
        self.items = []
        self.tears = []
        self.state = "idle"
        self.action_time = 0.0
        self.target = None
        self.destination = None
        self.facing = 1
        self.clock = 0.0
        self.hunger_time = 0.0
        self.idle_time = self._idle_duration()
        # Config expresses speed per historical update, not per rendering frame.
        self.speed = config.BASE_MOVEMENT_SPEED * 1000 / config.MOVEMENT_UPDATE_INTERVAL

    def _idle_duration(self):
        return self.rng.uniform(config.IDLE_DURATION_MIN, config.IDLE_DURATION_MAX) / 1000

    def resize(self, width, height):
        self.width, self.height = max(1, width), max(1, height)
        self.x, self.y = self._clamp(self.x, self.y)
        for item in self.items:
            item.x, item.y = self._clamp(item.x, item.y)
        if self.destination:
            self.destination = self._clamp(*self.destination)

    def _clamp(self, x, y):
        margin = min(config.PIGEON_SIZE / 2, self.width / 2, self.height / 2)
        return (min(max(x, margin), self.width - margin),
                min(max(y, margin), self.height - margin))

    def place(self, kind, x, y):
        if kind not in config.FOOD_TYPES and kind != "feather":
            return False
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        if len(self.items) >= MAX_ITEMS:
            return False
        x, y = self._clamp(x, y)
        self.items.append(Item(kind, x, y))
        return True

    def clear_effects(self):
        self.tears.clear()
        if self.state == "tearing":
            self.state = "idle"
            self.action_time = 0.0
            self.idle_time = self._idle_duration()

    def _choose_target(self):
        foods = [item for item in self.items if item.kind in config.FOOD_TYPES]
        candidates = foods or self.items
        if candidates:
            self.target = min(candidates, key=lambda item: math.hypot(item.x - self.x, item.y - self.y))
            self.destination = None
            self.state = "walking"

    def _move(self, point, seconds):
        dx, dy = point[0] - self.x, point[1] - self.y
        distance = math.hypot(dx, dy)
        if dx:
            self.facing = 1 if dx > 0 else -1
        step = self.speed * seconds
        if distance <= step:
            self.x, self.y = point
            return True
        if distance:
            self.x += dx / distance * step
            self.y += dy / distance * step
        return False

    def update(self, seconds):
        """Advance using elapsed seconds; actions apply rewards only on completion."""
        if seconds <= 0:
            return
        self.clock += seconds
        self.hunger_time += seconds
        interval = config.HUNGER_TICK_INTERVAL / 1000
        ticks = int(self.hunger_time / interval)
        self.hunger_time -= ticks * interval
        self.hunger = min(config.HUNGER_MAX, self.hunger + ticks * config.HUNGER_PER_TICK)
        for tear in self.tears:
            tear.age += seconds
        self.tears[:] = [tear for tear in self.tears if tear.age < TEAR_LIFETIME]

        if self.state in ("eating", "playing", "tearing"):
            self.action_time += seconds
            duration = {"eating": EAT_DURATION, "playing": PLAY_DURATION, "tearing": 2.0}[self.state]
            if self.action_time >= duration:
                if self.target is not None and any(item is self.target for item in self.items):
                    if self.state == "eating":
                        food = config.FOOD_TYPES[self.target.kind]
                        self.hunger = max(0, self.hunger - food["hunger_reduction"])
                        self.friendship += food["friendship"]
                    self.items[:] = [item for item in self.items if item is not self.target]
                self.target = None
                self.state = "idle"
                self.action_time = 0.0
                self.idle_time = self._idle_duration()
            return

        if self.target is None:
            self._choose_target()
        if self.target is not None:
            if self._move((self.target.x, self.target.y), seconds):
                self.state = "playing" if self.target.kind == "feather" else "eating"
                self.action_time = 0.0
            return
        if self.destination is not None:
            self.state = "walking"
            if self._move(self.destination, seconds):
                self.destination = None
                self.state = "idle"
            return

        self.idle_time -= seconds
        if self.idle_time <= 0:
            self.idle_time = self._idle_duration()
            if self.rng.random() < 0.6:
                self.state = "tearing"
                self.action_time = 0.0
                self.tears.append(Tear(self.x + self.facing * 28, self.y + 18,
                                       angle=self.rng.uniform(-0.5, 0.5)))
                self.tears[:] = self.tears[-MAX_TEARS:]
            else:
                radius = config.ROAM_RADIUS
                self.destination = self._clamp(self.x + self.rng.uniform(-radius, radius),
                                               self.y + self.rng.uniform(-radius, radius))
