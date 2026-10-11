"""Phase 1 food is freely available; later phases can add earned inventory."""

from config import FOOD_TYPES, HUNGER_MAX, HUNGER_PER_TICK, HUNGER_STATES, HUNGER_TICK_INTERVAL


def hunger_state(hunger: float) -> str:
    for name, (_, upper) in HUNGER_STATES.items():
        if hunger <= upper:
            return name.replace("_", " ").title()
    return "Angry"


def advance_hunger(hunger: float, seconds: float) -> float:
    return min(HUNGER_MAX, max(0, hunger + max(0, seconds) * HUNGER_PER_TICK
                               / (HUNGER_TICK_INTERVAL / 1000)))


def feed(hunger: float, food: str) -> float:
    return max(0, hunger - FOOD_TYPES[food]["hunger_reduction"])
