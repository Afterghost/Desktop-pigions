"""Active-time generations and permanent local legacy records, without Tk."""

from dataclasses import dataclass, field
from uuid import uuid4, UUID

from companion import Companion, TRAITS
from progression import number

CAPACITIES = (1, 2, 3, 5)
UPGRADE_COSTS = (5, 10, 20)
HATCH_SECONDS = 60
HISTORY_LIMIT = 100
LIFETIME_LIMIT = 1_000_000_000


@dataclass
class Legacy:
    name: str
    personality: str
    reputation: int
    lifetime: float
    reason: str = "Neglect: Last Chance expired"


@dataclass
class BirdRecord:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Pigeon"
    parent: str | None = None
    generation: int = 1
    status: str = "active"
    hunger: float = 25
    lifetime: float = 0
    forage_timer: float = 6
    companion: Companion = field(default_factory=Companion)
    legacy: Legacy | None = None


@dataclass
class Egg:
    id: str
    parent: str | None
    generation: int
    traits: dict
    remaining: float = HATCH_SECONDS


@dataclass
class Flock:
    records: list = field(default_factory=list)
    eggs: list = field(default_factory=list)
    level: int = 0
    treasury: int = 0
    selected_id: str | None = None
    social_timer: float = 0
    interactions: int = 0

    @classmethod
    def initial(cls, companion, hunger=25):
        bird = BirdRecord(companion=companion, hunger=hunger)
        return cls(records=[bird], selected_id=bird.id)

    @property
    def capacity(self):
        return CAPACITIES[self.level]

    @property
    def active(self):
        return [bird for bird in self.records if bird.status == "active"]

    @property
    def selected(self):
        return next((bird for bird in self.records if bird.id == self.selected_id), None)

    def upgrade(self):
        if self.level == 3 or self.treasury < UPGRADE_COSTS[self.level]:
            return False
        self.treasury -= UPGRADE_COSTS[self.level]
        self.level += 1
        return True

    def lay(self, parent_id=None):
        if (len(self.records) + len(self.eggs) >= HISTORY_LIMIT
                or len(self.active) + len(self.eggs) >= self.capacity):
            return False
        parent = next((b for b in self.active if b.id == parent_id), None)
        if parent_id is not None and parent is None:
            return False
        traits = {key: (parent.companion.traits[key] + 50) // 2 if parent else 50
                  for key in TRAITS}
        self.eggs.append(Egg(str(uuid4()), parent_id,
                             parent.generation + 1 if parent else 1, traits))
        return True

    def depart(self, bird):
        if bird.status != "active":
            return False
        # A single immutable-in-practice legacy snapshot per identity never disappears.
        if bird.legacy is None:
            bird.legacy = Legacy(bird.name, bird.companion.personality,
                                 bird.companion.progression.reputation, bird.lifetime)
        bird.status = "departed"
        if self.selected_id == bird.id:
            self.selected_id = self.active[0].id if self.active else None
        return True

    def rejoin(self, bird_id):
        bird = next((b for b in self.records if b.id == bird_id), None)
        if (bird is None or bird.status != "departed"
                or len(self.active) + len(self.eggs) >= self.capacity):
            return False
        bird.status = "active"
        bird.companion.progression.reconcile()
        self.selected_id = bird.id
        return True

    def advance(self, seconds):
        if not number(seconds, 1_000_000):
            raise ValueError("Invalid active time")
        hatched = []
        for egg in list(self.eggs):
            egg.remaining = max(0, egg.remaining - seconds)
            if egg.remaining == 0 and len(self.active) < self.capacity:
                bird = BirdRecord(id=egg.id, name=f"Pigeon {len(self.records) + 1}",
                                  parent=egg.parent, generation=egg.generation,
                                  companion=Companion(traits=dict(egg.traits)))
                self.records.append(bird)
                self.eggs.remove(egg)
                hatched.append(bird)
                if self.selected_id is None:
                    self.selected_id = bird.id
        if len(self.active) >= 2:
            self.social_timer = min(30, self.social_timer + seconds)
            if self.social_timer >= 30:
                self.social_timer = 0
                self.interactions = min(1_000_000, self.interactions + 1)
                elder = max(self.active, key=lambda b: b.lifetime)
                for bird in self.active:
                    bird.companion.befriend(1)
                    if bird != elder:
                        bird.companion.traits["calm"] = min(100, bird.companion.traits["calm"] + 1)
        return hatched

    @classmethod
    def from_data(cls, data):
        if type(data) is not dict or set(data) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid flock fields")
        result = cls(**data)
        if (type(result.level) is not int or not 0 <= result.level <= 3
                or type(result.treasury) is not int or not 0 <= result.treasury <= 1_000_000
                or type(result.interactions) is not int or not 0 <= result.interactions <= 1_000_000
                or not number(result.social_timer, 30)):
            raise ValueError("Invalid flock counters")
        if (type(result.records) is not list or type(result.eggs) is not list
                or not 1 <= len(result.records) <= HISTORY_LIMIT
                or len(result.records) + len(result.eggs) > HISTORY_LIMIT
                or len(result.eggs) > 5):
            raise ValueError("Invalid history size")
        ids = set()
        def identity(value):
            if type(value) is not str or str(UUID(value)) != value or value in ids:
                raise ValueError("Invalid/duplicate identity")
            ids.add(value)
        def text(value, limit=100):
            if type(value) is not str or not 0 < len(value) <= limit:
                raise ValueError("Invalid history text")
        records = []
        for entry in result.records:
            if type(entry) is not dict or set(entry) != set(BirdRecord.__dataclass_fields__):
                raise ValueError("Invalid bird fields")
            bird = BirdRecord(**entry)
            identity(bird.id)
            text(bird.name)
            if (type(bird.status) is not str or bird.status not in ("active", "departed")
                    or not number(bird.hunger, 100) or not number(bird.lifetime, LIFETIME_LIMIT)
                    or not number(bird.forage_timer, 60)
                    or type(bird.generation) is not int or not 1 <= bird.generation <= HISTORY_LIMIT):
                raise ValueError("Invalid bird")
            bird.companion = Companion.from_data(bird.companion)
            if bird.legacy is not None:
                if type(bird.legacy) is not dict or set(bird.legacy) != set(Legacy.__dataclass_fields__):
                    raise ValueError("Invalid legacy fields")
                bird.legacy = Legacy(**bird.legacy)
                text(bird.legacy.name)
                text(bird.legacy.personality, 200)
                if (bird.legacy.reason != "Neglect: Last Chance expired"
                        or type(bird.legacy.reputation) is not int
                        or not 0 <= bird.legacy.reputation <= 1000
                        or not number(bird.legacy.lifetime, bird.lifetime)):
                    raise ValueError("Invalid legacy")
            if bird.status == "departed" and (bird.legacy is None or bird.companion.progression.grace != 120):
                raise ValueError("Departure without history")
            if bird.status == "active" and bird.companion.progression.grace >= 120:
                raise ValueError("Expired active bird")
            records.append(bird)
        result.records = records
        eggs = []
        for entry in result.eggs:
            if type(entry) is not dict or set(entry) != set(Egg.__dataclass_fields__):
                raise ValueError("Invalid egg fields")
            egg = Egg(**entry)
            identity(egg.id)
            if (not number(egg.remaining, HATCH_SECONDS)
                    or type(egg.generation) is not int or not 1 <= egg.generation <= HISTORY_LIMIT
                    or type(egg.traits) is not dict or set(egg.traits) != set(TRAITS)
                    or any(type(v) is not int or not 0 <= v <= 100 for v in egg.traits.values())):
                raise ValueError("Invalid egg")
            eggs.append(egg)
        result.eggs = eggs
        by_id = {bird.id: bird for bird in records}
        for child in records + eggs:
            if child.parent is None:
                if child.generation != 1:
                    raise ValueError("Invalid founding generation")
            elif (type(child.parent) is not str or child.parent not in by_id
                  or child.generation != by_id[child.parent].generation + 1):
                raise ValueError("Invalid parent/generation (cycles forbidden)")
        if len(result.active) + len(eggs) > result.capacity:
            raise ValueError("Over capacity")
        if ((result.selected_id is not None and
             (type(result.selected_id) is not str or result.selected_id not in {b.id for b in result.active}))
                or (bool(result.active) != (result.selected_id is not None))):
            raise ValueError("Invalid selected bird")
        return result
