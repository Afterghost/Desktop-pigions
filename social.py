"""Mutual flock bonds and transient, model-controlled social movement."""

from dataclasses import dataclass
from itertools import combinations

from companion import TRAITS
from config import BASE_MOVEMENT_SPEED
from pigeon import Behavior

BOND_LIMIT = 200


@dataclass
class Bond:
    actors: list
    affinity: int = 0
    meetings: int = 0

    @property
    def status(self):
        return "Friendship" if self.affinity >= 20 else "Rivalry" if self.affinity <= -20 else "Acquaintance"

    @staticmethod
    def compatibility(a, b):
        return 100 - sum(abs(a.companion.traits[t] - b.companion.traits[t]) for t in TRAITS) // 3


def socialize(flock):
    active = flock.active
    for a, b in combinations(active, 2):
        bond = flock.bond(a.id, b.id, create=True)
        if bond is None:
            continue
        before = bond.status
        compatibility = Bond.compatibility(a, b)
        bond.meetings = min(1_000_000, bond.meetings + 1)
        delta = 5 if compatibility >= 65 else -6
        # Personality clashes occasionally outweigh otherwise compatible routines.
        if bond.meetings % 7 == 0 and min(a.companion.traits["calm"], b.companion.traits["calm"]) < 45:
            delta = -18
        bond.affinity = max(-100, min(100, bond.affinity + delta))
        if bond.status != before:
            kind = {"Friendship": "friendship", "Rivalry": "rivalry",
                    "Acquaintance": "reconciliation" if before == "Rivalry" else None}[bond.status]
            if kind:
                flock.chronicle.record(kind, bond.actors)
    elder = max(active, key=lambda b: b.lifetime)
    for pupil in active:
        if (pupil != elder and elder.lifetime > pupil.lifetime
                and flock.bond(elder.id, pupil.id) is not None):
            pupil.companion.traits["calm"] = min(100, pupil.companion.traits["calm"] + 1)
            flock.chronicle.record("mentorship", [elder.id, pupil.id])


@dataclass
class Collaboration:
    leader: str
    partner: str
    target: object
    remaining: float = 30


class SocialMotion:
    """No persisted unfinished rewards; one leader owns each shared target."""

    def __init__(self):
        self.collaboration = None
        self.avoidance = None
        self.greeting = None
        self.labels = {}

    def cancel(self, pigeons):
        task = self.collaboration
        if task:
            leader = pigeons.get(task.leader)
            if leader and leader.treasure is task.target:
                leader.cancel_theft()
        self.collaboration = None
        self.avoidance = None
        self.greeting = None
        self.labels.clear()

    def valid(self, flock, pigeons):
        task = self.collaboration
        if not task:
            return False
        active = {b.id for b in flock.active}
        return (task.leader in active and task.partner in active
                and task.leader in pigeons and task.partner in pigeons
                and pigeons[task.leader].treasure is task.target
                and pigeons[task.partner].treasure is None
                and all(task.target.kind not in pigeons[i].companion.progression.protected
                        for i in (task.leader, task.partner)))

    def start(self, flock, pigeons, target_factory, allow_foraging=True):
        if self.collaboration or self.avoidance or self.greeting:
            return
        active = {b.id for b in flock.active}
        bonds = [b for b in flock.bonds if all(i in active for i in b.actors)]
        if allow_foraging:
            for bond in sorted(bonds, key=lambda b: b.affinity, reverse=True):
                a, b = (pigeons[i] for i in bond.actors)
                if a.treasure is not None or b.treasure is not None:
                    continue
                if bond.status == "Friendship":
                    target = target_factory(a)
                    if target.kind in b.companion.progression.protected or not a.investigate(target):
                        continue
                    self.collaboration = Collaboration(*bond.actors, target)
                    self.labels = {bond.actors[0]: "Shared forage", bond.actors[1]: "Following friend"}
                    return
        for bond in bonds:
            if bond.status == "Rivalry" and all(pigeons[i].treasure is None for i in bond.actors):
                self.avoidance = [*bond.actors, 5.0]
                self.labels = {bond.actors[0]: "Giving space", bond.actors[1]: "Rival nearby"}
                return

    def start_foraging(self, leader_id, flock, pigeons, target_factory):
        if self.collaboration or self.avoidance or self.greeting:
            return False
        active = {bird.id for bird in flock.active}
        bonds = sorted(
            (bond for bond in flock.bonds if leader_id in bond.actors
             and bond.status == "Friendship"
             and all(identity in active for identity in bond.actors)),
            key=lambda bond: bond.affinity, reverse=True)
        for bond in bonds:
            partner_id = next(identity for identity in bond.actors if identity != leader_id)
            leader, partner = pigeons[leader_id], pigeons[partner_id]
            if leader.treasure is not None or partner.treasure is not None:
                continue
            target = target_factory(leader)
            if (target.kind in partner.companion.progression.protected
                    or not leader.investigate(target)):
                continue
            self.collaboration = Collaboration(leader_id, partner_id, target)
            self.labels = {leader_id: "Shared forage", partner_id: "Following friend"}
            return True
        return False

    def advance(self, seconds, flock, pigeons):
        active = {b.id for b in flock.active}
        task = self.collaboration
        if task:
            if not self.valid(flock, pigeons) or task.remaining <= 0:
                self.cancel(pigeons)
                return
            task.remaining = max(0, task.remaining - seconds)
            a, b = pigeons[task.leader], pigeons[task.partner]
            b.destination = b.bounds.clamp(a.x - 65, a.y + 20)
            b._move(seconds, BASE_MOVEMENT_SPEED)
        if self.avoidance:
            a_id, b_id, remaining = self.avoidance
            if (a_id not in active or b_id not in active
                    or a_id not in pigeons or b_id not in pigeons or remaining <= 0):
                self.cancel(pigeons)
                return
            a, b = pigeons[a_id], pigeons[b_id]
            a.destination = a.bounds.clamp(a.x + (100 if a.x >= b.x else -100), a.y + 40)
            a._move(seconds, BASE_MOVEMENT_SPEED)
            self.avoidance[2] = max(0, remaining - seconds)
        if self.greeting:
            a_id, b_id, remaining = self.greeting
            if (a_id not in active or b_id not in active
                    or a_id not in pigeons or b_id not in pigeons or remaining <= 0
                    or pigeons[a_id].treasure or pigeons[b_id].treasure):
                self.cancel(pigeons)
                return
            a, b = pigeons[a_id], pigeons[b_id]
            a.destination = a.nest_position
            a._move(seconds, BASE_MOVEMENT_SPEED)
            b.destination = b.bounds.clamp(a.x - 65, a.y + 20)
            b._move(seconds, BASE_MOVEMENT_SPEED)
            self.greeting[2] = max(0, remaining - seconds)

    def finish(self, collector, target, flock, pigeons):
        task = self.collaboration
        if not task or collector != task.leader or target is not task.target:
            return False
        partner = next((b for b in flock.active if b.id == task.partner), None)
        # Called immediately after the leader's state machine consumes its target.
        valid = (partner is not None and task.partner in pigeons and task.remaining > 0
                 and pigeons[task.partner].treasure is None
                 and all(target.kind not in pigeons[i].companion.progression.protected
                         for i in (task.leader, task.partner)))
        if valid:
            bond = flock.bond(task.leader, task.partner)
            bond.affinity = min(100, bond.affinity + 2)
            flock.chronicle.record("foraging", sorted([task.leader, task.partner]), permanent=False)
        self.collaboration = None
        self.labels.clear()
        return valid

    def gift_partner(self, bird_id, flock):
        for bond in flock.bonds:
            if bird_id in bond.actors and bond.status == "Friendship":
                other = next(i for i in bond.actors if i != bird_id)
                if other in {b.id for b in flock.active}:
                    return other
        return None

    def share_gift(self, bird_id, flock, pigeons):
        if (bird_id not in {b.id for b in flock.active}
                or self.collaboration or self.avoidance or self.greeting):
            return None
        other = self.gift_partner(bird_id, flock)
        if other and all(pigeons[i].treasure is None for i in (bird_id, other)):
            self.greeting = [bird_id, other, 5.0]
            self.labels = {bird_id: "Shared gift", other: "Gift escort"}
            bond = flock.bond(bird_id, other)
            bond.affinity = min(100, bond.affinity + 1)
            flock.chronicle.record("shared_gift", sorted([bird_id, other]), permanent=False)
            return other
        return None
