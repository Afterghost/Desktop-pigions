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
from nest import Item, Nest


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
            if data["version"] != 1:
                raise ValueError("Unsupported save version")
            hunger = data["hunger"]
            if (type(hunger) not in (int, float) or not math.isfinite(hunger)
                    or not 0 <= hunger <= HUNGER_MAX):
                raise ValueError("Invalid hunger")
            entries = data["items"]
            if not isinstance(entries, list) or len(entries) > MAX_STORED_ITEMS:
                raise ValueError("Invalid nest")
            items = []
            names = {(name, kind) for name, kind, _ in TREASURES}
            ids = set()
            for entry in entries:
                item = Item(**entry)
                if (not all(isinstance(value, str) and 0 < len(value) <= 100
                            for value in asdict(item).values())
                        or (item.name, item.kind) not in names or item.id in ids):
                    raise ValueError("Invalid item")
                ids.add(item.id)
                items.append(item)
            return float(hunger), Nest(items)
        except FileNotFoundError:
            return 25.0, Nest()
        except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError) as exc:
            raise SaveError("Save unreadable; original kept. Saving disabled for this session.") from exc

    def save(self, hunger: float, nest: Nest) -> None:
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=self.directory, prefix=".nest-",
                                             suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump({"version": 1, "hunger": hunger,
                           "items": [asdict(item) for item in nest.items]}, handle,
                          allow_nan=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError) as exc:
            raise SaveError("Could not save locally. Check the app data folder permissions.") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
