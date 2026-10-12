"""Bounded local facts; prose is deterministic and never observes the desktop."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from companion import TRAITS

RECENT_LIMIT = 60
CORE_LIMIT = 4000
KINDS = {"founding": 1, "origins": 1, "egg_origins": 1, "egg": 1, "hatch": 1,
         "care": 1, "treasure": 1, "gift": 1, "game": 1, "win": 1,
         "departure": 1, "return": 1, "friendship": 2, "rivalry": 2,
         "reconciliation": 2, "mentorship": 2, "foraging": 2, "shared_gift": 2}
ORIGINS = {"founding", "origins", "egg_origins", "egg", "hatch"}


@dataclass
class Event:
    kind: str
    actors: list
    traits: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def key(self):
        return (self.kind, *self.actors)


@dataclass
class Chronicle:
    core: list = field(default_factory=list)
    recent: list = field(default_factory=list)

    def record(self, kind, actors, traits=None, permanent=True):
        event = Event(kind, list(actors), dict(traits or {}))
        if permanent and not any(e.key == event.key for e in self.core):
            if len(self.core) >= CORE_LIMIT:
                raise ValueError("Chronicle identity limit reached")
            self.core.append(event)
        # Recent is an explicitly pruned activity feed, not permanent family history.
        self.recent.append(event)
        del self.recent[:-RECENT_LIMIT]

    def prose(self, event, flock):
        by_id = {b.id: b for b in flock.records + flock.eggs}
        names = [getattr(by_id[i], "name", "Waiting egg") for i in event.actors]
        first = by_id[event.actors[0]]
        if event.kind in ORIGINS:
            parent = by_id.get(first.parent)
            ancestry = (f"child of {parent.name}; inherited " if parent else "founding line; traits ")
            if event.kind in {"origins", "egg_origins"}:
                ancestry = (f"family of {parent.name}; recorded traits " if parent
                            else "founding line; recorded traits ")
            traits = ", ".join(f"{t} {event.traits[t]}" for t in TRAITS)
            verbs = {"founding": "founded the nest", "origins": "joined the migrated family record",
                     "egg_origins": "joined the migrated incubation record",
                     "egg": "began incubating", "hatch": "hatched"}
            return f"{names[0]} {verbs[event.kind]}: generation {first.generation}, {ancestry}{traits}."
        single = {"care": "received their first recorded caring gesture", "treasure": "stored their first recorded treasure",
                  "gift": "brought their first recorded gift", "game": "started their first recorded game",
                  "win": "won their first recorded game", "departure": "departed; their legacy remains",
                  "return": "returned to the same family and identity"}
        if event.kind in single:
            if event.kind == "departure":
                legacy = first.legacy
                return (f"{names[0]} departed: {legacy.personality}, reputation {legacy.reputation}, "
                        f"{legacy.lifetime:.0f} active seconds. {legacy.reason}. Legacy remains.")
            return f"{names[0]} {single[event.kind]}."
        if event.kind == "mentorship":
            return f"Elder {names[0]} mentored {names[1]}, sharing calm across the family."
        pair = {"friendship": "formed a flock friendship", "rivalry": "became rivals",
                "reconciliation": "made peace after rivalry", "mentorship": "shared elder calm",
                "foraging": "completed a cooperative collection",
                "shared_gift": "shared a gift delivery"}
        return f"{names[0]} and {names[1]} {pair[event.kind]}."

    def family_ids(self, flock, anchor=None, mode="All"):
        by_id = {b.id: b for b in flock.records}
        if anchor not in by_id or mode == "All":
            return set(by_id)
        ancestors = {anchor}
        current = by_id[anchor]
        while current.parent:
            ancestors.add(current.parent)
            current = by_id[current.parent]
        if mode == "Ancestors":
            return ancestors
        root = current.id if mode == "Lineage" else anchor
        result = {root}
        for bird in sorted(flock.records, key=lambda b: b.generation):
            if bird.parent in result:
                result.add(bird.id)
        return result

    @classmethod
    def from_data(cls, data, flock):
        if type(data) is not dict or set(data) != {"core", "recent"}:
            raise ValueError("Invalid chronicle fields")
        result = cls()
        identities = {b.id: b for b in flock.records + flock.eggs}
        birds = {b.id for b in flock.records}
        seen_ids = {}
        for name, limit in (("core", CORE_LIMIT), ("recent", RECENT_LIMIT)):
            entries = data[name]
            if type(entries) is not list or len(entries) > limit:
                raise ValueError("Invalid chronicle size")
            keys = set()
            ids = set()
            for entry in entries:
                if type(entry) is not dict or set(entry) != set(Event.__dataclass_fields__):
                    raise ValueError("Invalid event fields")
                event = Event(**entry)
                if (type(event.id) is not str or str(UUID(event.id)) != event.id
                        or event.id in ids or (event.id in seen_ids and seen_ids[event.id] != event)):
                    raise ValueError("Invalid/duplicate event identity")
                ids.add(event.id)
                seen_ids[event.id] = event
                if (type(event.kind) is not str or event.kind not in KINDS
                        or type(event.actors) is not list or len(event.actors) != KINDS[event.kind]
                        or any(type(i) is not str or i not in identities for i in event.actors)
                        or len(set(event.actors)) != len(event.actors)):
                    raise ValueError("Invalid event actors")
                if event.kind not in {"egg", "egg_origins"} and any(i not in birds for i in event.actors):
                    raise ValueError("Invalid bird event")
                if len(event.actors) == 2 and event.kind != "mentorship" and event.actors != sorted(event.actors):
                    raise ValueError("Noncanonical pair event")
                if (type(event.traits) is not dict or
                        set(event.traits) != (set(TRAITS) if event.kind in ORIGINS else set())
                        or any(type(v) is not int or not 0 <= v <= 100 for v in event.traits.values())):
                    raise ValueError("Invalid event traits")
                if event.kind == "founding" and identities[event.actors[0]].parent is not None:
                    raise ValueError("Invalid founding event")
                if name == "core" and event.key in keys:
                    raise ValueError("Duplicate core event")
                keys.add(event.key)
                getattr(result, name).append(event)
        for identity in identities.values():
            origins = [e for e in result.core if e.actors == [identity.id]
                       and e.kind in {"founding", "hatch", "origins"}]
            if identity.id in birds and len(origins) != 1:
                raise ValueError("Missing/duplicate family origin")
            egg_events = [e for e in result.core if e.actors == [identity.id]
                          and e.kind in {"egg", "egg_origins"}]
            hatch_events = [e for e in origins if e.kind == "hatch"]
            if identity.id not in birds and (len(egg_events) != 1 or egg_events[0].traits != identity.traits):
                raise ValueError("Missing egg snapshot")
            if hatch_events and (len(egg_events) != 1 or hatch_events[0].traits != egg_events[0].traits):
                raise ValueError("Inconsistent inherited snapshot")
        for event in result.core + result.recent:
            actor = identities[event.actors[0]]
            if event.kind in {"departure", "return"} and actor.legacy is None:
                raise ValueError("Missing departure legacy")
        return result
