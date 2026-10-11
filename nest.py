"""Bounded local collection of generated treasures and fragments."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from config import MAX_STORED_ITEMS
from companion import Companion
from desktop import Treasure
from companion import GIFTS
from flock import Flock


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    kind: str
    collected_at: str


@dataclass
class Nest:
    items: list[Item] = field(default_factory=list)
    companion: Companion = field(default_factory=Companion)
    flock: Flock | None = None

    def collect(self, treasure: Treasure, companion=None) -> Item:
        item = Item(str(uuid4()), treasure.name, treasure.kind,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self.items.append(item)
        del self.items[:-MAX_STORED_ITEMS]
        if treasure.kind != "Gift":
            (companion or self.companion).evolve("collect")
            if self.flock is not None:
                self.flock.treasury = min(1_000_000, self.flock.treasury + 1)
        return item

    def return_item(self, item_id: str) -> bool:
        item = next((item for item in self.items if item.id == item_id), None)
        if item is None:
            return False
        self.items.remove(item)
        self.companion.befriend(4 if item.kind == "Gift" and item.name in GIFTS else 2)
        self.companion.evolve("return")
        return True
