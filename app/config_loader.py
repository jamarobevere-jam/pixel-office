import math

import yaml

from app.models import Floorplan, Person, Visitor, WorldObject


class ConfigError(Exception):
    pass


def _load_yaml(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"Config file not found: {path}") from e
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e


def load_floorplan(path: str) -> Floorplan:
    data = _load_yaml(path)
    try:
        grid = data["grid"]
        objects = [
            WorldObject(type=o["type"], x=o["x"], y=o["y"])
            for o in data.get("objects", [])
        ]
        return Floorplan(
            width=grid["width"],
            height=grid["height"],
            tile_size=grid["tile_size"],
            objects=objects,
        )
    except (KeyError, TypeError) as e:
        raise ConfigError(f"Malformed floorplan config {path}: {e}") from e


def load_people(path: str, floorplan: Floorplan) -> list[Person]:
    data = _load_yaml(path)
    desks = floorplan.desks()
    people = []
    seen_names: set[str] = set()
    try:
        for entry in data["people"]:
            if not isinstance(entry, dict):
                raise ConfigError(f"Malformed person entry in {path}; expected a mapping")
            desk_index = entry.get("desk")
            if desk_index is None:
                try:
                    spawn_x, spawn_y = entry["spawn_tile"]
                    if not (0 <= spawn_x < floorplan.width and 0 <= spawn_y < floorplan.height):
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    raise ConfigError(
                        f"Person '{entry.get('name')}' without a desk must have a valid spawn_tile"
                    ) from None
                cx = spawn_x * floorplan.tile_size + floorplan.tile_size / 2
                cy = spawn_y * floorplan.tile_size + floorplan.tile_size / 2
            else:
                if not isinstance(desk_index, int) or not (0 <= desk_index < len(desks)):
                    raise ConfigError(
                        f"Person '{entry.get('name')}' has invalid desk index "
                        f"{desk_index}; floorplan has {len(desks)} desks"
                    )
                desk_obj = desks[desk_index]
                seat_x, seat_y = floorplan.desk_seat_tile(desk_obj)
                cx = seat_x * floorplan.tile_size + floorplan.tile_size / 2
                cy = seat_y * floorplan.tile_size + floorplan.tile_size / 2
            name = entry["name"]
            if name in seen_names:
                raise ConfigError(
                    f"Duplicate person name '{name}' in {path}; names must be unique"
                )
            seen_names.add(name)
            idle_phrases = list(entry["idle_phrases"])
            idle_phrase_weights = entry.get("idle_phrase_weights")
            if idle_phrase_weights is not None and (
                not isinstance(idle_phrase_weights, list)
                or len(idle_phrase_weights) != len(idle_phrases)
                or any(
                    not isinstance(weight, (int, float))
                    or not math.isfinite(weight)
                    or weight < 0
                    for weight in idle_phrase_weights
                )
                or not any(weight > 0 for weight in idle_phrase_weights)
            ):
                raise ConfigError(
                    f"Person '{name}' must have one non-negative idle phrase weight "
                    "per phrase, with at least one positive weight"
                )
            people.append(
                Person(
                    name=name,
                    sprite=entry["sprite"],
                    desk=desk_index,
                    idle_phrases=idle_phrases,
                    x=cx,
                    y=cy,
                    state="at_desk",
                    target_x=None,
                    target_y=None,
                    current_phrase=None,
                    phrase_expires_at=None,
                    idle_phrase_weights=idle_phrase_weights,
                )
            )
    except (KeyError, TypeError) as e:
        raise ConfigError(f"Malformed people config {path}: {e}") from e
    return people


def load_interactions(path: str) -> list[tuple[str, str]]:
    data = _load_yaml(path)
    try:
        return [tuple(pair) for pair in data["exchanges"]]
    except (KeyError, TypeError) as e:
        raise ConfigError(f"Malformed interactions config {path}: {e}") from e


def load_visitor(path: str) -> Visitor:
    data = _load_yaml(path)
    try:
        return Visitor(
            name=data["name"],
            sprite=data["sprite"],
            phrases=list(data["phrases"]),
        )
    except (KeyError, TypeError) as e:
        raise ConfigError(f"Malformed visitor config {path}: {e}") from e
