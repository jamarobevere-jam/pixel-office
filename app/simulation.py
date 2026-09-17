import random
from collections import deque

from app.models import Floorplan, Person

WALK_SPEED_PX_PER_SEC = 60
IDLE_MIN_SECONDS = 4
IDLE_MAX_SECONDS = 12
PHRASE_DURATION_SECONDS = 3
# Walk targets snap to tile centers, so the smallest possible non-zero
# distance between two of them is a diagonal-adjacent pair (tile_size *
# sqrt(2)). The threshold must clear that, or "adjacent" people never
# actually count as close.
TALK_PROXIMITY_PX = 50
TALK_CHANCE_PER_TICK = 0.08
# Fraction of the time an idle person's next walk target is chosen near
# another currently-idle person instead of a uniformly random tile — makes
# people occasionally wander over to a coworker instead of relying on
# fully independent random walks ever lining up by chance.
SOCIAL_WALK_CHANCE = 0.35


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

        blocked = floorplan.blocked_tiles()
        self._walkable_tiles = [
            (x, y)
            for x in range(floorplan.width)
            for y in range(floorplan.height)
            if (x, y) not in blocked
        ]
        self._walkable_set = set(self._walkable_tiles)

    def tick(self, now: float, dt: float) -> None:
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
            tile_size = self.floorplan.tile_size
            start_tile = (int(person.x // tile_size), int(person.y // tile_size))
            goal_tile = self._pick_walk_target(person, tile_size)
            tiles = self._find_path_tiles(start_tile, goal_tile) or [goal_tile]
            waypoints = [
                (tx * tile_size + tile_size / 2, ty * tile_size + tile_size / 2)
                for tx, ty in tiles
            ]
            person.target_x, person.target_y = waypoints[0]
            person.path = waypoints[1:]
            person.state = "walking"

    def _pick_walk_target(self, person: Person, tile_size: int) -> tuple[int, int]:
        others_idle = [p for p in self.people if p is not person and p.state == "at_desk"]
        if others_idle and self.rng.random() < SOCIAL_WALK_CHANCE:
            target_person = self.rng.choice(others_idle)
            ptx = int(target_person.x // tile_size)
            pty = int(target_person.y // tile_size)
            nearby = [
                (ptx + dx, pty + dy)
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                if (ptx + dx, pty + dy) in self._walkable_set
            ]
            if nearby:
                return self.rng.choice(nearby)
        return self.rng.choice(self._walkable_tiles)

    def _find_path_tiles(
        self, start: tuple[int, int], goal: tuple[int, int]
    ) -> list[tuple[int, int]] | None:
        """4-directional BFS avoiding furniture; the start tile itself is
        always allowed even if blocked (a person standing at their desk is
        already there)."""
        if start == goal:
            return [goal]

        visited = {start}
        parent: dict[tuple[int, int], tuple[int, int]] = {}
        queue = deque([start])
        width, height = self.floorplan.width, self.floorplan.height

        while queue:
            current = queue.popleft()
            if current == goal:
                break
            cx, cy = current
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cx + dx, cy + dy)
                if nxt in visited:
                    continue
                if not (0 <= nxt[0] < width and 0 <= nxt[1] < height):
                    continue
                if nxt != goal and nxt not in self._walkable_set:
                    continue
                visited.add(nxt)
                parent[nxt] = current
                queue.append(nxt)
        else:
            return None  # goal unreachable

        path = [goal]
        node = goal
        while node != start:
            node = parent[node]
            path.append(node)
        path.reverse()
        return path[1:]

    def _tick_walking(self, person: Person, dt: float, now: float) -> None:
        dx = person.target_x - person.x
        dy = person.target_y - person.y
        dist = (dx ** 2 + dy ** 2) ** 0.5
        step = WALK_SPEED_PX_PER_SEC * dt
        if dist <= step:
            person.x = person.target_x
            person.y = person.target_y
            if person.path:
                person.target_x, person.target_y = person.path.pop(0)
                return
            person.target_x = None
            person.target_y = None
            person.path = None
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
