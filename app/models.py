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
