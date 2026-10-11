"""Bounded local collection of generated treasures and fragments."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from config import MAX_STORED_ITEMS
from desktop import Treasure


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    kind: str
    collected_at: str


@dataclass
class Nest:
    items: list[Item] = field(default_factory=list)

    def collect(self, treasure: Treasure) -> Item:
        item = Item(str(uuid4()), treasure.name, treasure.kind,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self.items.append(item)
        del self.items[:-MAX_STORED_ITEMS]
        return item
