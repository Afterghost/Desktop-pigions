"""Single-companion simulation, independent of the desktop UI and persistence."""

from enum import Enum
import math
import random

from config import (
    BASE_MOVEMENT_SPEED, IDLE_DURATION_MAX, IDLE_DURATION_MIN,
    MOVEMENT_UPDATE_INTERVAL, THEFT_ANIMATION_DURATION,
    THEFT_APPROACH_SPEED, THEFT_ESCAPE_SPEED,
)
from desktop import Bounds, Treasure
from companion import Companion
from feeding import advance_hunger, feed, hunger_state


class Behavior(Enum):
    IDLE = "Resting"
    ROAMING = "Roaming"
    INVESTIGATING = "Investigating"
    APPROACHING = "Approaching"
    THEFT = "Theft attempt"
    ESCAPING = "Escaping to nest"
    STORING = "Nest storage"


class Pigeon:
    def __init__(self, bounds: Bounds, nest_position: tuple[float, float],
                 hunger: float = 25, rng: random.Random | None = None,
                 companion: Companion | None = None):
        self.bounds = bounds
        self.rng = rng if rng is not None else random.Random()
        self.x, self.y = bounds.clamp(bounds.x + bounds.width / 2,
                                      bounds.y + bounds.height / 2)
        self.nest_position = bounds.clamp(*nest_position)
        self.hunger = hunger
        self.behavior = Behavior.IDLE
        self.destination = (self.x, self.y)
        self.wait = 1.0
        self.treasure: Treasure | None = None
        self.facing_right = True
        self.fed_for = 0.0
        self.companion = companion

    @property
    def hunger_label(self) -> str:
        return hunger_state(self.hunger)

    @property
    def carrying(self) -> bool:
        return self.behavior in (Behavior.ESCAPING, Behavior.STORING)

    def feed(self, food: str) -> None:
        self.hunger = feed(self.hunger, food)
        self.fed_for = 3.0

    def investigate(self, treasure: Treasure) -> bool:
        if (self.treasure is not None or (self.companion is not None
                and treasure.kind in self.companion.progression.protected)):
            return False
        self.treasure = treasure
        self.behavior = Behavior.INVESTIGATING
        self.wait = 0.8
        return True

    def cancel_theft(self) -> bool:
        if self.treasure is None:
            return False
        self.treasure = None
        self.behavior = Behavior.IDLE
        self.destination = (self.x, self.y)
        self.wait = 2
        return True

    def _move(self, seconds: float, speed: float) -> bool:
        dx, dy = self.destination[0] - self.x, self.destination[1] - self.y
        distance = math.hypot(dx, dy)
        step = speed * seconds * 1000 / MOVEMENT_UPDATE_INTERVAL
        if dx:
            self.facing_right = dx > 0
        if distance <= step:
            self.x, self.y = self.destination
            return True
        self.x, self.y = self.bounds.clamp(
            self.x + dx / distance * step, self.y + dy / distance * step,
        )
        return False

    def step(self, seconds: float, social_movement: bool = False) -> Treasure | None:
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Elapsed time must be finite and non-negative")
        self.hunger = advance_hunger(self.hunger, seconds)
        self.fed_for = max(0, self.fed_for - seconds)
        if social_movement and self.treasure is None:
            return None
        if self.behavior in (Behavior.IDLE, Behavior.INVESTIGATING,
                             Behavior.THEFT, Behavior.STORING):
            self.wait -= seconds
            if self.wait > 0:
                return None
            if self.behavior == Behavior.IDLE:
                self.destination = self.bounds.nearby(self.x, self.y, self.rng)
                self.behavior = Behavior.ROAMING
            elif self.behavior == Behavior.INVESTIGATING:
                self.destination = self.bounds.clamp(self.treasure.x, self.treasure.y)
                self.behavior = Behavior.APPROACHING
            elif self.behavior == Behavior.THEFT:
                self.destination = self.nest_position
                self.behavior = Behavior.ESCAPING
            else:
                collected = self.treasure
                self.treasure = None
                self.behavior = Behavior.IDLE
                self.wait = 2.0
                return collected
        elif self.behavior == Behavior.ROAMING:
            if self._move(seconds, BASE_MOVEMENT_SPEED):
                self.behavior = Behavior.IDLE
                calm = self.companion.traits["calm"] / 100 if self.companion else 0.5
                self.wait = self.rng.uniform(IDLE_DURATION_MIN, IDLE_DURATION_MAX) / 1000 * (0.5 + calm)
        elif self.behavior == Behavior.APPROACHING:
            if self._move(seconds, THEFT_APPROACH_SPEED):
                self.behavior = Behavior.THEFT
                self.wait = THEFT_ANIMATION_DURATION / 1000
        elif self.behavior == Behavior.ESCAPING:
            if self._move(seconds, THEFT_ESCAPE_SPEED):
                self.behavior = Behavior.STORING
                self.wait = 0.8
        return None
