import random
from collections import deque

from app.models import Floorplan, Person, Visitor

WALK_SPEED_PX_PER_SEC = 60
IDLE_MIN_SECONDS = 4
IDLE_MAX_SECONDS = 12
PHRASE_DURATION_SECONDS = 6
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

# "Boss visit" scenario: a visitor appears from a random elevator, everyone
# rushes silently to their own desk until they leave, then normal life
# resumes.
VISITOR_MIN_INTERVAL_SECONDS = 90
VISITOR_MAX_INTERVAL_SECONDS = 240
VISITOR_WANDER_SECONDS = 20
VISITOR_DOOR_OPEN_SECONDS = 1.5
VISITOR_PHRASE_CHANCE = 0.85


class Simulation:
    def __init__(
        self,
        people: list[Person],
        floorplan: Floorplan,
        interactions: list[tuple[str, str]],
        visitor: Visitor | None = None,
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

        # Walk *destinations* stay one tile clear of the outer border, so a
        # person idling there never renders with their sprite/name partly
        # off-canvas (a sprite is wider than half a tile). Pathfinding
        # itself still uses the full _walkable_set above, so a route is
        # free to pass through the border strip in transit.
        self._walk_target_tiles = [
            (x, y)
            for (x, y) in self._walkable_tiles
            if 0 < x < floorplan.width - 1 and 0 < y < floorplan.height - 1
        ] or self._walkable_tiles
        self._walk_target_set = set(self._walk_target_tiles)

        self._elevators = [o for o in floorplan.objects if o.type == "elevator"]

        self.visitor: Person | None = None
        self.visitor_active = False  # a visit is in progress (freezes everyone)
        self.visitor_visible = False  # visitor should be included in to_state()
        self.open_elevator: tuple[int, int] | None = None
        self._visitor_phase = "away"  # away | entering | wandering | returning | exiting
        self._visitor_phase_until = 0.0
        self._visitor_wander_until = 0.0
        self._visitor_doorway_tile: tuple[int, int] | None = None
        self._visitor_next_trigger_at = 0.0

        if visitor is not None and self._elevators:
            self.visitor = Person(
                name=visitor.name,
                sprite=visitor.sprite,
                desk=-1,
                idle_phrases=visitor.phrases,
                x=0.0,
                y=0.0,
                state="at_desk",
                target_x=None,
                target_y=None,
                current_phrase=None,
                phrase_expires_at=None,
            )
            self._schedule_next_visitor(0.0)

    def tick(self, now: float, dt: float) -> None:
        for person in self.people:
            self._dispatch_person(person, now, dt)

        self._tick_visitor_lifecycle(now, dt)

        if not self.visitor_active:
            self._maybe_start_conversations(now)

    def _dispatch_person(self, person: Person, now: float, dt: float) -> None:
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

    def _tick_at_desk(self, person: Person, now: float) -> None:
        if self.visitor_active and person is not self.visitor:
            return  # frozen at desk for the duration of a visit
        idle_until = self._idle_until.get(person.name)
        if idle_until is None:
            idle_until = now + self.rng.uniform(IDLE_MIN_SECONDS, IDLE_MAX_SECONDS)
            self._idle_until[person.name] = idle_until
            return
        if now >= idle_until:
            del self._idle_until[person.name]
            tile_size = self.floorplan.tile_size
            goal_tile = self._pick_walk_target(person, tile_size)
            self._begin_walk_to(person, goal_tile)

    def _begin_walk_to(self, person: Person, goal_tile: tuple[int, int]) -> None:
        tile_size = self.floorplan.tile_size
        start_tile = (int(person.x // tile_size), int(person.y // tile_size))
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
                if (ptx + dx, pty + dy) in self._walk_target_set
            ]
            if nearby:
                return self.rng.choice(nearby)
        return self.rng.choice(self._walk_target_tiles)

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
            is_visitor = person is self.visitor
            phrase_chance = VISITOR_PHRASE_CHANCE if is_visitor else 0.5
            if (is_visitor or not self.visitor_active) and self.rng.random() < phrase_chance:
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

    # -- Visitor ("boss visit") scenario --------------------------------

    def _schedule_next_visitor(self, now: float) -> None:
        self._visitor_next_trigger_at = now + self.rng.uniform(
            VISITOR_MIN_INTERVAL_SECONDS, VISITOR_MAX_INTERVAL_SECONDS
        )

    def _elevator_doorway_tile(self, elevator) -> tuple[int, int]:
        candidates = [(elevator.x, elevator.y + 2), (elevator.x + 1, elevator.y + 2)]
        for c in candidates:
            if c in self._walk_target_set:
                return c
        return candidates[0]

    def _tick_visitor_lifecycle(self, now: float, dt: float) -> None:
        if self.visitor is None:
            return

        if self._visitor_phase == "away":
            if now >= self._visitor_next_trigger_at:
                self._start_visitor_entrance(now)
            return

        if self._visitor_phase == "entering":
            if now >= self._visitor_phase_until:
                self.open_elevator = None
                self._visitor_phase = "wandering"
                self._visitor_wander_until = now + VISITOR_WANDER_SECONDS
                tile_size = self.floorplan.tile_size
                goal_tile = self._pick_walk_target(self.visitor, tile_size)
                self._begin_walk_to(self.visitor, goal_tile)
            return

        if self._visitor_phase == "wandering":
            self._dispatch_person(self.visitor, now, dt)
            if now >= self._visitor_wander_until:
                self._visitor_phase = "returning"
                self._begin_walk_to(self.visitor, self._visitor_doorway_tile)
            return

        if self._visitor_phase == "returning":
            self._dispatch_person(self.visitor, now, dt)
            if self.visitor.state == "at_desk":
                self.visitor.current_phrase = None
                self.visitor.phrase_expires_at = None
                self.visitor_visible = False
                elevator = self._visitor_elevator
                self.open_elevator = (elevator.x, elevator.y)
                self._visitor_phase = "exiting"
                self._visitor_phase_until = now + VISITOR_DOOR_OPEN_SECONDS
            return

        if self._visitor_phase == "exiting":
            if now >= self._visitor_phase_until:
                self.open_elevator = None
                self.visitor_active = False
                self._visitor_phase = "away"
                self._schedule_next_visitor(now)
            return

    def _start_visitor_entrance(self, now: float) -> None:
        elevator = self.rng.choice(self._elevators)
        doorway = self._elevator_doorway_tile(elevator)
        tile_size = self.floorplan.tile_size

        self.visitor.x = doorway[0] * tile_size + tile_size / 2
        self.visitor.y = doorway[1] * tile_size + tile_size / 2
        self.visitor.state = "at_desk"
        self.visitor.target_x = None
        self.visitor.target_y = None
        self.visitor.path = None
        self.visitor.current_phrase = None
        self.visitor.phrase_expires_at = None

        self._visitor_elevator = elevator
        self._visitor_doorway_tile = doorway
        self.open_elevator = (elevator.x, elevator.y)
        self.visitor_active = True
        self.visitor_visible = True
        self._visitor_phase = "entering"
        self._visitor_phase_until = now + VISITOR_DOOR_OPEN_SECONDS

        self._send_everyone_to_desk(now)

    def _send_everyone_to_desk(self, now: float) -> None:
        desks = self.floorplan.desks()
        for person in self.people:
            person.current_phrase = None
            person.phrase_expires_at = None
            self._talk_until.pop(person.name, None)
            self._idle_until.pop(person.name, None)
            desk_obj = desks[person.desk]
            self._begin_walk_to(person, (desk_obj.x, desk_obj.y))

    def to_state(self) -> dict:
        people_state = [self._person_state(p) for p in self.people]
        if self.visitor_visible and self.visitor is not None:
            people_state.append(self._person_state(self.visitor))
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
            "open_elevator": (
                {"x": self.open_elevator[0], "y": self.open_elevator[1]}
                if self.open_elevator
                else None
            ),
        }

    @staticmethod
    def _person_state(p: Person) -> dict:
        return {
            "name": p.name,
            "x": p.x,
            "y": p.y,
            "state": p.state,
            "sprite": p.sprite,
            "phrase": p.current_phrase,
        }
