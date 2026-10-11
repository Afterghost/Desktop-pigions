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
from companion import Companion, GIFTS
from nest import Item, Nest
from progression import Progression
from datetime import datetime


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

    def load(self) -> tuple[float, Nest]:
        try:
            with self.path.open(encoding="utf-8") as handle:
                # Reject oversized/corrupt saves without reading arbitrary amounts of data.
                raw = handle.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("Save is too large")
            data = json.loads(raw)
            if type(data["version"]) is not int or data["version"] not in (1, 2, 3):
                raise ValueError("Unsupported save version")
            expected = {"version", "hunger", "items"} | ({"companion"} if data["version"] >= 2 else set())
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
                            or set(profile_data) != set(Companion.__dataclass_fields__) - {"progression"}):
                        raise ValueError("Invalid legacy companion")
                    profile_data = dict(profile_data, progression=asdict(Progression()))
                profile = Companion.from_data(profile_data)
            else:
                profile = Companion(traits=dict.fromkeys(("curiosity", "calm", "sociability"), 50))
            return float(hunger), Nest(items, profile)
        except FileNotFoundError:
            return 25.0, Nest()
        except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError) as exc:
            raise SaveError("Save unreadable; original kept. Saving disabled for this session.") from exc

    def save(self, hunger: float, nest: Nest) -> None:
        temporary = None
        try:
            if type(hunger) not in (int, float) or not math.isfinite(hunger) or not 0 <= hunger <= HUNGER_MAX:
                raise ValueError("Invalid hunger")
            Companion.from_data(asdict(nest.companion))
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
                json.dump({"version": 3, "hunger": hunger,
                           "companion": asdict(nest.companion),
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
