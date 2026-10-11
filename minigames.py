"""A five-round shiny-sorting game, with a one-time completion reward."""

import random

from desktop import TREASURES


class ShinySorting:
    def __init__(self, rng: random.Random | None = None):
        rng = rng if rng is not None else random.Random()
        self.rounds = [rng.choice(TREASURES) for _ in range(5)]
        self.index = 0
        self.score = 0
        self.claimed = False

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
