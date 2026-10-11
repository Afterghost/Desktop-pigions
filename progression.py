"""Bounded, local milestones and active-time neglect; no offline clock."""

from dataclasses import dataclass, field
import math

GAME_NAMES = ("Shiny Sorting", "Peck Finder", "Follow Crumb Trail", "Pigeon Memory",
              "Rooftop Dash", "Human Inspection", "Daily Foraging")
ACTIONS = ("care", "collect", "play", "govern", "return")
ACHIEVEMENTS = tuple(f"{action}:{count}" for action in ACTIONS for count in (1, 5, 20)) + GAME_NAMES + ("The Day We Made Up",)
PROTECTED_TYPES = ("Treasure", "Fragment")


def number(value, maximum):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum


@dataclass
class Progression:
    actions: dict = field(default_factory=lambda: dict.fromkeys(ACTIONS, 0))
    achievements: list = field(default_factory=list)
    neglect: float = 0
    forgiven: bool = False
    intervention_cooldown: float = 0
    forage_cooldown: float = 0
    protected: list = field(default_factory=list)

    @property
    def reputation(self):
        return len(self.achievements) * 10

    @property
    def title(self):
        points = self.reputation
        return ("Unknown Pigeon" if points < 30 else "Neighborhood Regular" if points < 80
                else "Trusted Companion" if points < 150 else "Rooftop Legend")

    @property
    def neglect_stage(self):
        return ("Last Chance Coo — Preparing to Leave (awaiting reconciliation)" if self.neglect >= 240
                else "Preparing to Leave" if self.neglect >= 180
                else "Resentful" if self.neglect >= 120
                else "Bitter" if self.neglect >= 60
                else "Grumpy" if self.neglect > 0 else "At ease")

    def unlock(self, name):
        if name not in ACHIEVEMENTS:
            raise ValueError("Unknown achievement")
        if name not in self.achievements:
            self.achievements.append(name)

    def record(self, action):
        if action not in ACTIONS:
            raise ValueError("Unknown action")
        self.actions[action] = min(1_000_000, self.actions[action] + 1)
        for count in (1, 5, 20):
            if self.actions[action] >= count:
                self.unlock(f"{action}:{count}")

    def reconcile(self):
        if self.neglect <= 0:
            return False
        self.neglect = 0
        self.forgiven = True
        self.unlock("The Day We Made Up")
        return True

    def advance(self, seconds, hunger):
        if not number(seconds, 1_000_000) or not number(hunger, 100):
            raise ValueError("Invalid active time or hunger")
        self.intervention_cooldown = max(0, self.intervention_cooldown - seconds)
        self.forage_cooldown = max(0, self.forage_cooldown - seconds)
        if hunger >= 90:
            self.neglect = min(240, self.neglect + seconds)

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid progression fields")
        result = cls(**data)
        if (not isinstance(result.actions, dict) or set(result.actions) != set(ACTIONS)
                or any(type(v) is not int or not 0 <= v <= 1_000_000 for v in result.actions.values())):
            raise ValueError("Invalid action counts")
        for values, allowed in ((result.achievements, ACHIEVEMENTS), (result.protected, PROTECTED_TYPES)):
            if (not isinstance(values, list) or len(values) > len(allowed)
                    or any(type(v) is not str or v not in allowed for v in values)
                    or len(set(values)) != len(values)):
                raise ValueError("Invalid history or protection")
        if type(result.forgiven) is not bool:
            raise ValueError("Invalid forgiveness")
        for value, maximum in ((result.neglect, 240), (result.intervention_cooldown, 10),
                               (result.forage_cooldown, 300)):
            if not number(value, maximum):
                raise ValueError("Invalid progression timer")
        if result.forgiven != ("The Day We Made Up" in result.achievements):
            raise ValueError("Inconsistent journal")
        return result
