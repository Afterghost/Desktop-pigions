"""A five-round shiny-sorting game, with a one-time completion reward."""

import random

from desktop import TREASURES
from progression import GAME_NAMES


class ShinySorting:
    def __init__(self, rng: random.Random | None = None):
        rng = rng if rng is not None else random.Random()
        self.rounds = [rng.choice(TREASURES) for _ in range(5)]
        self.index = 0
        self.score = 0
        self.claimed = False
        self.cancelled = False

    def cancel(self):
        self.cancelled = True
        self.claimed = True
        self.index = len(self.rounds)

    @property
    def complete(self) -> bool:
        return self.index == len(self.rounds)

    @property
    def current(self) -> tuple[str, str, str] | None:
        return None if self.complete else self.rounds[self.index]

    def answer(self, kind: str) -> bool:
        if kind not in ("Treasure", "Fragment"):
            raise ValueError("Choose Treasure or Fragment")
        if self.complete:
            return False
        correct = kind == self.current[1]
        self.score += int(correct)
        self.index += 1
        return correct

    def claim_reward(self) -> int | None:
        if not self.complete or self.claimed:
            return None
        self.claimed = True
        return self.score if self.score >= 3 else None


INSTRUCTIONS = {
    "Shiny Sorting": "Sort five shinies. Buttons/marbles: Treasure; foil/paper: Fragment.",
    "Peck Finder": "Find the edible crumb in each 3×3 patch. Pick its numbered square, not a stone.",
    "Follow Crumb Trail": "Follow the numbered trail in ascending order. Choose the next crumb, not a detour.",
    "Pigeon Memory": "Study five colors, then press Hide / recall. Recall the colors in order.",
    "Rooftop Dash": "Cross five roof sections: Jump gaps, Duck wires, Run on clear roofs.",
    "Human Inspection": "Inspect five drawn human scenes. Approach food offers, Wait for busy humans, Retreat from danger.",
    "Daily Foraging": "Manage energy: Search costs 2 energy and finds food. Rest restores 3. Start with 4; never search exhausted.",
}


class LocalGame(ShinySorting):
    """Shared five-turn rules; game-specific prompts and legal choices."""

    def __init__(self, name, rng=None):
        if name not in GAME_NAMES or name == "Shiny Sorting":
            raise ValueError("Unknown local game")
        super().__init__(rng)
        self.name = name
        rng = rng if rng is not None else random.Random()
        self.energy = 4
        self.revealing = name == "Pigeon Memory"
        if name == "Peck Finder":
            self.rounds = [rng.randint(1, 9) for _ in range(5)]
        elif name == "Follow Crumb Trail":
            self.rounds = [1, 2, 3, 4, 5]
        elif name == "Pigeon Memory":
            self.rounds = [rng.choice(("Red", "Blue", "Gold")) for _ in range(5)]
        elif name == "Rooftop Dash":
            self.rounds = [rng.choice(("Gap", "Wire", "Clear")) for _ in range(5)]
        elif name == "Human Inspection":
            self.rounds = [rng.choice(("Open palm with seeds", "Typing at a desk", "Waving a broom"))
                           for _ in range(5)]
        else:
            self.rounds = list(range(5))

    @property
    def choices(self):
        return {
            "Peck Finder": tuple(str(i) for i in range(1, 10)),
            "Follow Crumb Trail": tuple(str(i) for i in range(1, 6)),
            "Pigeon Memory": ("Red", "Blue", "Gold"),
            "Rooftop Dash": ("Jump", "Duck", "Run"),
            "Human Inspection": ("Approach", "Wait", "Retreat"),
            "Daily Foraging": ("Search", "Rest"),
        }[self.name]

    @property
    def prompt(self):
        if self.complete:
            return ""
        if self.name == "Peck Finder":
            return "\n".join("  ".join(f"{i}: {'crumb' if i == self.current else 'stone'}"
                                     for i in range(row, row + 3)) for row in (1, 4, 7))
        if self.name == "Follow Crumb Trail":
            return f"Trail: 1 → 2 → 3 → 4 → 5\nYou reached crumb {self.index}. Choose next."
        if self.name == "Pigeon Memory":
            return ("Remember: " + " → ".join(self.rounds) if self.revealing
                    else f"Recall color {self.index + 1}.")
        if self.name == "Daily Foraging":
            return f"Energy: {self.energy}. {'Rest before searching!' if self.energy < 2 else 'Enough energy to search.'}"
        return self.current

    def hide_memory(self):
        self.revealing = False

    def answer(self, choice):
        if choice not in self.choices:
            raise ValueError("Invalid choice")
        if self.complete or self.revealing:
            return False
        if self.name == "Peck Finder":
            correct = choice == str(self.current)
        elif self.name == "Follow Crumb Trail":
            correct = choice == str(self.index + 1)
        elif self.name == "Pigeon Memory":
            correct = choice == self.current
        elif self.name == "Rooftop Dash":
            correct = choice == {"Gap": "Jump", "Wire": "Duck", "Clear": "Run"}[self.current]
        elif self.name == "Human Inspection":
            correct = choice == {"Open palm with seeds": "Approach", "Typing at a desk": "Wait",
                                 "Waving a broom": "Retreat"}[self.current]
        else:
            correct = choice == ("Rest" if self.energy < 2 else "Search")
            self.energy = min(6, self.energy + 3) if choice == "Rest" else max(0, self.energy - 2)
        self.score += int(correct)
        self.index += 1
        return correct
