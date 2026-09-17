import random

from app.models import Floorplan, Person

WALK_SPEED_PX_PER_SEC = 60
IDLE_MIN_SECONDS = 4
IDLE_MAX_SECONDS = 12
PHRASE_DURATION_SECONDS = 3
TALK_PROXIMITY_PX = 40
TALK_CHANCE_PER_TICK = 0.02


class Simulation:
    def __init__(
        self,
        people: list[Person],
        floorplan: Floorplan,
        interactions: list[tuple[str, str]],
        rng: random.Random | None = None,
    ):
        self.people = people
        self.floorplan = floorplan
        self.interactions = interactions
        self.rng = rng or random.Random()
        self._idle_until: dict[str, float] = {}
        self._talk_until: dict[str, float] = {}

    def tick(self, now: float, dt: float) -> None:
        self._now = now
        for person in self.people:
            if person.state == "at_desk":
                self._tick_at_desk(person, now)
            elif person.state == "walking":
                self._tick_walking(person, dt, now)
            elif person.state == "talking":
                self._tick_talking(person, now)

            if (
                person.current_phrase is not None
                and person.phrase_expires_at is not None
                and now >= person.phrase_expires_at
                and person.state != "talking"
            ):
                person.current_phrase = None
                person.phrase_expires_at = None

        self._maybe_start_conversations(now)

    def _tick_at_desk(self, person: Person, now: float) -> None:
        idle_until = self._idle_until.get(person.name)
        if idle_until is None:
            idle_until = now + self.rng.uniform(IDLE_MIN_SECONDS, IDLE_MAX_SECONDS)
            self._idle_until[person.name] = idle_until
            return
        if now >= idle_until:
            del self._idle_until[person.name]
            person.target_x = self.rng.uniform(0, self.floorplan.width * self.floorplan.tile_size)
            person.target_y = self.rng.uniform(0, self.floorplan.height * self.floorplan.tile_size)
            person.state = "walking"

    def _tick_walking(self, person: Person, dt: float, now: float) -> None:
        dx = person.target_x - person.x
        dy = person.target_y - person.y
        dist = (dx ** 2 + dy ** 2) ** 0.5
        step = WALK_SPEED_PX_PER_SEC * dt
        if dist <= step:
            person.x = person.target_x
            person.y = person.target_y
            person.target_x = None
            person.target_y = None
            person.state = "at_desk"
            if self.rng.random() < 0.5:
                person.current_phrase = self.rng.choice(person.idle_phrases)
                person.phrase_expires_at = now + PHRASE_DURATION_SECONDS
        else:
            person.x += dx / dist * step
            person.y += dy / dist * step

    def _tick_talking(self, person: Person, now: float) -> None:
        talk_until = self._talk_until.get(person.name)
        if talk_until is not None and now >= talk_until:
            del self._talk_until[person.name]
            person.state = "at_desk"
            person.current_phrase = None
            person.phrase_expires_at = None

    def _maybe_start_conversations(self, now: float) -> None:
        if not self.interactions:
            return
        idle_people = [p for p in self.people if p.state == "at_desk"]
        for i, a in enumerate(idle_people):
            for b in idle_people[i + 1:]:
                dist = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
                if dist <= TALK_PROXIMITY_PX and self.rng.random() < TALK_CHANCE_PER_TICK:
                    line_a, line_b = self.rng.choice(self.interactions)
                    a.state = "talking"
                    b.state = "talking"
                    a.current_phrase = line_a
                    b.current_phrase = line_b
                    a.phrase_expires_at = now + PHRASE_DURATION_SECONDS
                    b.phrase_expires_at = now + PHRASE_DURATION_SECONDS
                    self._talk_until[a.name] = now + PHRASE_DURATION_SECONDS
                    self._talk_until[b.name] = now + PHRASE_DURATION_SECONDS
                    return

    def to_state(self) -> dict:
        people_state = [
            {
                "name": p.name,
                "x": p.x,
                "y": p.y,
                "state": p.state,
                "sprite": p.sprite,
                "phrase": p.current_phrase,
            }
            for p in self.people
        ]
        return {
            "people": people_state,
            "floorplan": {
                "width": self.floorplan.width,
                "height": self.floorplan.height,
                "tile_size": self.floorplan.tile_size,
                "objects": [
                    {"type": o.type, "x": o.x, "y": o.y}
                    for o in self.floorplan.objects
                ],
            },
        }
