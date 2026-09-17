import yaml

from app.models import Floorplan, Person, WorldObject


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
            desk_index = entry["desk"]
            if not (0 <= desk_index < len(desks)):
                raise ConfigError(
                    f"Person '{entry.get('name')}' has invalid desk index "
                    f"{desk_index}; floorplan has {len(desks)} desks"
                )
            name = entry["name"]
            if name in seen_names:
                raise ConfigError(
                    f"Duplicate person name '{name}' in {path}; names must be unique"
                )
            seen_names.add(name)
            desk_obj = desks[desk_index]
            cx = desk_obj.x * floorplan.tile_size + floorplan.tile_size / 2
            cy = desk_obj.y * floorplan.tile_size + floorplan.tile_size / 2
            people.append(
                Person(
                    name=name,
                    sprite=entry["sprite"],
                    desk=desk_index,
                    idle_phrases=list(entry["idle_phrases"]),
                    x=cx,
                    y=cy,
                    state="at_desk",
                    target_x=None,
                    target_y=None,
                    current_phrase=None,
                    phrase_expires_at=None,
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
