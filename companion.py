"""Persistent Phase 2 relationships, personality, earned food, and gifts."""

from dataclasses import dataclass, field
import math
import random

from config import FOOD_TYPES
from progression import Progression


GIFTS = ("Soft feather", "Lucky coin", "Tiny glass pebble", "Ribbon bouquet",
         "Polished bottle cap", "Friendship twig")
TRAITS = ("curiosity", "calm", "sociability")
PETTING_SPEEDS = ("slow", "steady", "quick")
STARTER_ATTIRE = ("Natural", "Ribbon", "Scarf", "Cap", "Flower")
RARE_ATTIRE = (
    "Feather Crown", "Postbird Cap", "Moon Scarf", "Lucky Coin Necklace",
    "Toast Necklace", "Rooftop Jacket", "Pigeon Pin",
)
ATTIRE = (*STARTER_ATTIRE, *RARE_ATTIRE)
APPEAL_STYLES = ("Ribbon", "Scarf", "Cap", "Flower")
ATTIRE_STYLE = {
    "Natural": None,
    "Ribbon": "Ribbon",
    "Scarf": "Scarf",
    "Cap": "Cap",
    "Flower": "Flower",
    "Feather Crown": "Cap",
    "Postbird Cap": "Cap",
    "Moon Scarf": "Scarf",
    "Lucky Coin Necklace": "Ribbon",
    "Toast Necklace": "Ribbon",
    "Rooftop Jacket": "Scarf",
    "Pigeon Pin": "Flower",
}


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
    progression: Progression = field(default_factory=Progression)
    pet_preference: str | None = None
    outfit: str = "Natural"
    appeal_preference: str | None = None
    wardrobe: list[str] = field(default_factory=lambda: list(STARTER_ATTIRE))

    def __post_init__(self):
        if self.pet_preference is None:
            dominant = max(TRAITS, key=lambda name: self.traits[name])
            self.pet_preference = {"calm": "slow", "sociability": "steady",
                                   "curiosity": "quick"}[dominant]
        if self.appeal_preference is None:
            dominant = max(TRAITS, key=lambda name: self.traits[name])
            self.appeal_preference = {
                "calm": "Scarf", "sociability": "Ribbon", "curiosity": "Cap",
            }[dominant]

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
        evolved = [title for action, title in (("care", "Gentle Soul"),
                   ("collect", "Treasure Seeker"), ("play", "Playful Acrobat"))
                   if self.progression.actions[action] >= 5]
        if len(evolved) > 1:
            title = "Hybrid: " + " + ".join(evolved)
        elif evolved:
            title = evolved[0]
        else:
            title = None
        if title:
            return title + (" · Forgiven" if self.progression.forgiven else "")
        dominant = max(TRAITS, key=lambda name: self.traits[name])
        return ({"curiosity": "Shiny explorer", "calm": "Laid-back lounger",
                "sociability": "Sociable companion"}[dominant]
                + (" · Forgiven" if self.progression.forgiven else ""))

    @property
    def pet_speed_preference(self) -> str:
        return self.pet_preference

    def evolve(self, action):
        self.progression.record(action)
        trait = {"care": "calm", "collect": "curiosity", "play": "sociability",
                 "govern": "calm", "return": "sociability"}[action]
        self.traits[trait] = min(100, self.traits[trait] + 1)
        if action in ("care", "play", "return"):
            self.progression.reconcile()

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
            self.evolve("care")
        return True

    def pet(self, speed: str | None = None) -> bool:
        if self.pet_cooldown > 0:
            return False
        points = 2 + self.traits["sociability"] // 40
        if speed is not None:
            if speed not in PETTING_SPEEDS:
                raise ValueError("Unknown petting speed")
            if speed == self.pet_speed_preference:
                points += 2
        self.befriend(points)
        self.pet_cooldown = 15
        self.evolve("care")
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
        self.evolve("play")
        self.befriend(score)
        self.food["sunflower_seeds"] = min(99, self.food["sunflower_seeds"] + 2)
        if score == 5:
            self.food["golden_corn"] = min(99, self.food["golden_corn"] + 1)

    def try_find_rare_attire(self, rng: random.Random, chance: float) -> str | None:
        if (type(chance) not in (int, float) or not math.isfinite(chance)
                or not 0 <= chance <= 1):
            raise ValueError("Invalid rare attire chance")
        available = [item for item in RARE_ATTIRE if item not in self.wardrobe]
        if not available or rng.random() >= chance:
            return None
        found = rng.choice(available)
        self.wardrobe.append(found)
        return found

    @classmethod
    def from_data(cls, data: dict) -> "Companion":
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid companion")
        profile = cls(**data)
        profile.progression = Progression.from_data(data["progression"])
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
        if profile.pet_preference not in PETTING_SPEEDS:
            raise ValueError("Invalid petting preference")
        if (profile.outfit not in ATTIRE
                or profile.appeal_preference not in APPEAL_STYLES
                or not isinstance(profile.wardrobe, list)
                or not all(isinstance(item, str) and item in ATTIRE
                           for item in profile.wardrobe)
                or len(profile.wardrobe) != len(set(profile.wardrobe))
                or not set(STARTER_ATTIRE).issubset(profile.wardrobe)
                or profile.outfit not in profile.wardrobe):
            raise ValueError("Invalid outfit or appeal preference")
        return profile


class PettingGesture:
    """Recognize two consecutive horizontal mouse strokes and their pace."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.last_x = None
        self.last_time = None
        self.direction = 0
        self.segment_x = None
        self.segment_time = None
        self.speeds = []

    def move(self, x: float, now: float) -> str | None:
        if (self.last_x is None or now <= self.last_time or now - self.last_time > 2.5):
            self.reset()
            self.last_x, self.last_time = x, now
            return None

        delta = x - self.last_x
        direction = (delta > 0) - (delta < 0)
        if direction and self.direction and direction != self.direction:
            distance = abs(self.last_x - self.segment_x)
            duration = self.last_time - self.segment_time
            if distance >= 24 and duration > 0:
                speed = distance / duration
                pace = "slow" if speed < 140 else "steady" if speed < 500 else "quick"
                self.speeds.append(pace)
                self.speeds = self.speeds[-2:]
                if len(self.speeds) == 2 and self.speeds[0] == self.speeds[1]:
                    self.reset()
                    return pace
            self.segment_x, self.segment_time = self.last_x, self.last_time
        elif direction and not self.direction:
            self.segment_x, self.segment_time = self.last_x, self.last_time
        if direction:
            self.direction = direction
        self.last_x, self.last_time = x, now
        return None
