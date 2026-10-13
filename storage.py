"""Versioned JSON saves in the application's own directory, with atomic writes."""

from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import sys
import tempfile

from config import HUNGER_MAX, MAX_STORED_ITEMS, NEST_DATA_FILE
from desktop import TREASURES
from companion import ATTIRE, Companion, GIFTS, RARE_ATTIRE, STARTER_ATTIRE
from nest import Item, Nest
from progression import Progression
from datetime import datetime
from flock import Flock
from chronicle import Chronicle, Event


class SaveError(Exception):
    pass


def data_directory() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "DesktopPigeon"


class Store:
    def __init__(self, directory: Path | None = None):
        self.directory = directory if directory is not None else data_directory()
        self.path = self.directory / NEST_DATA_FILE
        self.disabled = False

    def load(self) -> tuple[float, Nest]:
        try:
            with self.path.open(encoding="utf-8") as handle:
                # Reject oversized/corrupt saves without reading arbitrary amounts of data.
                raw = handle.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError("Save is too large")
            def unique_object(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate JSON field")
                    result[key] = value
                return result
            data = json.loads(raw, object_pairs_hook=unique_object)
            if type(data["version"]) is not int or data["version"] not in (1, 2, 3, 4, 5, 6, 7, 8):
                raise ValueError("Unsupported save version")
            expected = {"version", "hunger", "items"} | ({"companion"} if data["version"] >= 2 else set())
            if data["version"] >= 4:
                expected.add("flock")
            if set(data) != expected:
                raise ValueError("Invalid save fields")
            hunger = data["hunger"]
            if (type(hunger) not in (int, float) or not math.isfinite(hunger)
                    or not 0 <= hunger <= HUNGER_MAX):
                raise ValueError("Invalid hunger")
            entries = data["items"]
            if not isinstance(entries, list) or len(entries) > MAX_STORED_ITEMS:
                raise ValueError("Invalid nest")
            items = []
            names = {(name, kind) for name, kind, _ in TREASURES}
            if data["version"] >= 2:
                names.update((name, "Gift") for name in GIFTS)
            ids = set()
            for entry in entries:
                item = Item(**entry)
                if (not all(isinstance(value, str) and 0 < len(value) <= 100
                            for value in asdict(item).values())
                        or (item.name, item.kind) not in names or item.id in ids):
                    raise ValueError("Invalid item")
                ids.add(item.id)
                datetime.fromisoformat(item.collected_at)
                items.append(item)
            if data["version"] >= 2:
                profile_data = data["companion"]
                if data["version"] == 2:
                    if (not isinstance(profile_data, dict)
                            or set(profile_data) != set(Companion.__dataclass_fields__)
                            - {"progression", "pet_preference", "outfit",
                               "appeal_preference", "wardrobe"}):
                        raise ValueError("Invalid legacy companion")
                    profile_data = dict(profile_data, progression=asdict(Progression()),
                                         pet_preference=None)
                elif data["version"] == 3:
                    legacy_progression = profile_data["progression"]
                    if (type(legacy_progression) is not dict
                            or set(legacy_progression) != set(Progression.__dataclass_fields__) - {"grace"}):
                        raise ValueError("Invalid legacy progression")
                    profile_data = dict(profile_data, progression=dict(legacy_progression, grace=0),
                                         pet_preference=None)
                elif data["version"] < 6:
                    profile_data = dict(profile_data, pet_preference=None)
                if data["version"] < 7:
                    profile_data = _add_style_defaults(profile_data)
                if data["version"] < 8:
                    profile_data = _add_wardrobe_defaults(profile_data)
                profile = Companion.from_data(profile_data)
            else:
                profile = Companion(traits=dict.fromkeys(("curiosity", "calm", "sociability"), 50))
            if data["version"] >= 4:
                flock_data = data["flock"]
                if data["version"] == 4:
                    old_fields = set(Flock.__dataclass_fields__) - {"bonds", "chronicle"}
                    if type(flock_data) is not dict or set(flock_data) != old_fields:
                        raise ValueError("Invalid legacy flock fields")
                    origins = [asdict(Event("origins", [b["id"]], b["companion"]["traits"]))
                               for b in flock_data["records"]]
                    origins += [asdict(Event("egg_origins", [e["id"]], e["traits"]))
                                for e in flock_data["eggs"]]
                    flock_data = dict(flock_data, bonds=[], chronicle={"core": origins, "recent": []})
                if data["version"] < 8:
                    flock_data = dict(
                        flock_data,
                        records=[
                            dict(
                                bird,
                                companion=_add_wardrobe_defaults(
                                   _add_style_defaults(dict(
                                       bird["companion"],
                                       **({"pet_preference": None}
                                          if data["version"] < 6 else {})))
                                   if data["version"] < 7 else
                                   dict(bird["companion"]),
                                ),
                            )
                            for bird in flock_data["records"]
                        ],
                    )
                flock = Flock.from_data(flock_data)
            else:
                flock = Flock.initial(profile, float(hunger))
            if data["version"] < 5:
                flock.chronicle = Chronicle()
                for identity in flock.records + flock.eggs:
                    traits = (identity.companion.traits if hasattr(identity, "companion")
                              else identity.traits)
                    flock.chronicle.record("origins" if hasattr(identity, "companion") else "egg_origins",
                                           [identity.id], traits)
            linked = flock.selected or flock.records[0]
            if data["version"] >= 4 and (linked.hunger != hunger or linked.companion != profile):
                raise ValueError("Inconsistent selected profile")
            return float(hunger), Nest(items, linked.companion, flock)
        except FileNotFoundError:
            nest = Nest()
            nest.flock = Flock.initial(nest.companion)
            return 25.0, nest
        except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError) as exc:
            self.disabled = True
            raise SaveError("Save unreadable; original kept. Saving disabled for this session.") from exc

    def save(self, hunger: float, nest: Nest) -> None:
        temporary = None
        try:
            if self.disabled:
                raise ValueError("Saving disabled after unreadable save")
            if type(hunger) not in (int, float) or not math.isfinite(hunger) or not 0 <= hunger <= HUNGER_MAX:
                raise ValueError("Invalid hunger")
            Companion.from_data(asdict(nest.companion))
            if nest.flock is None:
                nest.flock = Flock.initial(nest.companion, hunger)
            linked = nest.flock.selected or nest.flock.records[0]
            if linked.companion is not nest.companion:
                raise ValueError("Selected companion linkage lost")
            linked.hunger = hunger
            Flock.from_data(asdict(nest.flock))
            names = {(name, kind) for name, kind, _ in TREASURES} | {(name, "Gift") for name in GIFTS}
            if len(nest.items) > MAX_STORED_ITEMS or len({item.id for item in nest.items}) != len(nest.items):
                raise ValueError("Invalid nest")
            for item in nest.items:
                if (not all(type(value) is str and 0 < len(value) <= 100 for value in asdict(item).values())
                        or (item.name, item.kind) not in names):
                    raise ValueError("Invalid item")
                datetime.fromisoformat(item.collected_at)
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=self.directory, prefix=".nest-",
                                             suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump({"version": 8, "hunger": hunger,
                           "companion": asdict(nest.companion),
                           "flock": asdict(nest.flock),
                           "items": [asdict(item) for item in nest.items]}, handle,
                          allow_nan=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError, TypeError) as exc:
            raise SaveError("Could not save locally. Check the app data folder permissions.") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


def _add_style_defaults(companion_data):
    """Supply style fields when migrating saves written before dressing rooms."""
    data = dict(companion_data)
    data["outfit"] = "Natural"
    data["appeal_preference"] = None
    return data


def _add_wardrobe_defaults(companion_data):
    data = dict(companion_data)
    owned = list(STARTER_ATTIRE)
    outfit = data.get("outfit")
    if outfit in (*ATTIRE, *RARE_ATTIRE) and outfit not in owned:
        owned.append(outfit)
    data["wardrobe"] = owned
    return data
