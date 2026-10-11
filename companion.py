"""Persistent Phase 2 relationships, personality, earned food, and gifts."""

from dataclasses import dataclass, field
import math
import random

from config import FOOD_TYPES


GIFTS = ("Soft feather", "Lucky coin", "Tiny glass pebble")
TRAITS = ("curiosity", "calm", "sociability")


@dataclass
class Companion:
    friendship: int = 0
    traits: dict[str, int] = field(
        default_factory=lambda: {name: random.randint(20, 80) for name in TRAITS})
    food: dict[str, int] = field(
        default_factory=lambda: {name: 3 for name in FOOD_TYPES if name != "seed_mix"})
    pet_cooldown: float = 0
    gift_timer: float = 0
    games_won: int = 0

    @property
    def relationship(self) -> str:
        if self.friendship >= 75:
            return "Best friend"
        if self.friendship >= 40:
            return "Friend"
        if self.friendship >= 20:
            return "Familiar"
        return "New acquaintance"

    @property
    def personality(self) -> str:
        dominant = max(TRAITS, key=lambda name: self.traits[name])
        return {"curiosity": "Shiny explorer", "calm": "Laid-back lounger",
                "sociability": "Sociable companion"}[dominant]

    def befriend(self, points: int) -> None:
        self.friendship = min(100, self.friendship + points)

    def feed(self, food: str, hunger: float) -> bool:
        effect = FOOD_TYPES[food]
        if food != "seed_mix":
            if self.food[food] <= 0:
                return False
            self.food[food] -= 1
        if hunger > 0:
            self.befriend(effect["friendship"])
        return True

    def pet(self) -> bool:
        if self.pet_cooldown > 0:
            return False
        self.befriend(2 + self.traits["sociability"] // 40)
        self.pet_cooldown = 15
        return True

    def advance(self, seconds: float, rng: random.Random) -> str | None:
        self.pet_cooldown = max(0, self.pet_cooldown - seconds)
        if self.friendship < 20:
            return None
        self.gift_timer = min(120, self.gift_timer + seconds)
        if self.gift_timer >= 120:
            self.gift_timer = 0
            return rng.choice(GIFTS)
        return None

    def reward_game(self, score: int) -> None:
        if type(score) is not int or not 3 <= score <= 5:
            raise ValueError("A winning score must be between 3 and 5")
        self.games_won = min(1_000_000, self.games_won + 1)
        self.befriend(score)
        self.food["sunflower_seeds"] = min(99, self.food["sunflower_seeds"] + 2)
        if score == 5:
            self.food["golden_corn"] = min(99, self.food["golden_corn"] + 1)

    @classmethod
    def from_data(cls, data: dict) -> "Companion":
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid companion")
        profile = cls(**data)
        for value, maximum in ((profile.friendship, 100), (profile.games_won, 1_000_000)):
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError("Invalid progression")
        for values, keys in ((profile.traits, TRAITS),
                             (profile.food, tuple(name for name in FOOD_TYPES if name != "seed_mix"))):
            if not isinstance(values, dict) or set(values) != set(keys):
                raise ValueError("Invalid traits or food")
            if any(type(value) is not int or not 0 <= value <= 100 for value in values.values()):
                raise ValueError("Invalid trait or food value")
        for value, maximum in ((profile.pet_cooldown, 15), (profile.gift_timer, 120)):
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or not 0 <= value <= maximum):
                raise ValueError("Invalid companion timer")
        return profile
