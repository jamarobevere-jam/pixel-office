from dataclasses import dataclass


@dataclass
class WorldObject:
    type: str
    x: int
    y: int


@dataclass
class Floorplan:
    width: int
    height: int
    tile_size: int
    objects: list[WorldObject]

    def desks(self) -> list[WorldObject]:
        return [o for o in self.objects if o.type == "desk"]

    @staticmethod
    def desk_seat_tile(desk: WorldObject) -> tuple[int, int]:
        """Tile a person sitting at this desk should render at — the chair
        spot in front of the monitor, not the desk's own (back-left) tile."""
        return (desk.x + 1, desk.y + 1)

    def blocked_tiles(self) -> set[tuple[int, int]]:
        """Tiles occupied by furniture people shouldn't walk through."""
        blocked: set[tuple[int, int]] = set()
        for obj in self.objects:
            if obj.type == "desk":
                blocked.add((obj.x, obj.y))
                blocked.add((obj.x + 1, obj.y))
                blocked.add((obj.x + 1, obj.y + 1))  # chair
            elif obj.type == "elevator":
                blocked.add((obj.x, obj.y))
                blocked.add((obj.x + 1, obj.y))
                blocked.add((obj.x, obj.y + 1))
                blocked.add((obj.x + 1, obj.y + 1))
            elif obj.type in ("plant", "water_dispenser"):
                blocked.add((obj.x, obj.y))
        return blocked


@dataclass
class Person:
    name: str
    sprite: str
    desk: int
    idle_phrases: list[str]
    x: float
    y: float
    state: str  # "at_desk" | "walking" | "talking"
    target_x: float | None
    target_y: float | None
    current_phrase: str | None
    phrase_expires_at: float | None
    path: list[tuple[float, float]] | None = None


@dataclass
class Visitor:
    name: str
    sprite: str
    phrases: list[str]
