import pytest
import yaml

from app.config_loader import (
    ConfigError,
    load_floorplan,
    load_people,
    load_interactions,
    load_visitor,
)


FLOORPLAN_YAML = """
grid:
  width: 40
  height: 30
  tile_size: 32
objects:
  - {type: desk, x: 4, y: 6}
  - {type: desk, x: 9, y: 6}
  - {type: plant, x: 2, y: 2}
"""

PEOPLE_YAML = """
people:
  - name: Sebastian
    sprite: sprite_01.png
    desk: 0
    idle_phrases:
      - "Hello Hello"
  - name: Jose
    sprite: sprite_02.png
    desk: 1
    idle_phrases:
      - "It works on my machine"
"""

PEOPLE_YAML_BAD_DESK = """
people:
  - name: Sebastian
    sprite: sprite_01.png
    desk: 99
    idle_phrases:
      - "Hello Hello"
"""

PEOPLE_YAML_MALFORMED_ENTRY = """
people:
  - "just a string, not a mapping"
"""

PEOPLE_YAML_DUPLICATE_NAMES = """
people:
  - name: Sebastian
    sprite: sprite_01.png
    desk: 0
    idle_phrases:
      - "Hello Hello"
  - name: Sebastian
    sprite: sprite_02.png
    desk: 1
    idle_phrases:
      - "It works on my machine"
"""

INTERACTIONS_YAML = """
exchanges:
  - ["Coffee?", "Always."]
"""

VISITOR_YAML = """
name: Frits
sprite: frits.png
phrases:
  - "Best of breed"
  - "Bullshit!"
"""

VISITOR_YAML_MALFORMED = """
name: Frits
sprite: frits.png
"""


def test_load_floorplan(tmp_path):
    p = tmp_path / "floorplan.yaml"
    p.write_text(FLOORPLAN_YAML)
    fp = load_floorplan(str(p))
    assert fp.width == 40
    assert fp.tile_size == 32
    assert len(fp.desks()) == 2


def test_load_people_sets_initial_position_at_desk_center(tmp_path):
    fp_path = tmp_path / "floorplan.yaml"
    fp_path.write_text(FLOORPLAN_YAML)
    fp = load_floorplan(str(fp_path))

    people_path = tmp_path / "people.yaml"
    people_path.write_text(PEOPLE_YAML)
    people = load_people(str(people_path), fp)

    assert len(people) == 2
    sebastian = people[0]
    assert sebastian.name == "Sebastian"
    assert sebastian.state == "at_desk"
    # desk 0 is at tile (4,6); a person sits at the chair tile in front of
    # it, (5,7), tile_size 32 -> center (176, 240)
    assert sebastian.x == 5 * 32 + 16
    assert sebastian.y == 7 * 32 + 16


def test_load_people_raises_on_bad_desk_index(tmp_path):
    fp_path = tmp_path / "floorplan.yaml"
    fp_path.write_text(FLOORPLAN_YAML)
    fp = load_floorplan(str(fp_path))

    people_path = tmp_path / "people.yaml"
    people_path.write_text(PEOPLE_YAML_BAD_DESK)

    with pytest.raises(ConfigError):
        load_people(str(people_path), fp)


def test_load_people_raises_config_error_on_empty_file(tmp_path):
    fp_path = tmp_path / "floorplan.yaml"
    fp_path.write_text(FLOORPLAN_YAML)
    fp = load_floorplan(str(fp_path))

    people_path = tmp_path / "people.yaml"
    people_path.write_text("")  # yaml.safe_load("") -> None

    with pytest.raises(ConfigError):
        load_people(str(people_path), fp)


def test_load_people_raises_config_error_on_malformed_entry(tmp_path):
    fp_path = tmp_path / "floorplan.yaml"
    fp_path.write_text(FLOORPLAN_YAML)
    fp = load_floorplan(str(fp_path))

    people_path = tmp_path / "people.yaml"
    people_path.write_text(PEOPLE_YAML_MALFORMED_ENTRY)

    with pytest.raises(ConfigError):
        load_people(str(people_path), fp)


def test_load_people_raises_on_duplicate_names(tmp_path):
    fp_path = tmp_path / "floorplan.yaml"
    fp_path.write_text(FLOORPLAN_YAML)
    fp = load_floorplan(str(fp_path))

    people_path = tmp_path / "people.yaml"
    people_path.write_text(PEOPLE_YAML_DUPLICATE_NAMES)

    with pytest.raises(ConfigError):
        load_people(str(people_path), fp)


def test_load_floorplan_missing_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError):
        load_floorplan(str(tmp_path / "does_not_exist.yaml"))


def test_load_interactions(tmp_path):
    p = tmp_path / "interactions.yaml"
    p.write_text(INTERACTIONS_YAML)
    pairs = load_interactions(str(p))
    assert pairs == [("Coffee?", "Always.")]


def test_load_visitor(tmp_path):
    p = tmp_path / "visitor.yaml"
    p.write_text(VISITOR_YAML)
    visitor = load_visitor(str(p))
    assert visitor.name == "Frits"
    assert visitor.sprite == "frits.png"
    assert visitor.phrases == ["Best of breed", "Bullshit!"]


def test_load_visitor_raises_config_error_on_malformed_entry(tmp_path):
    p = tmp_path / "visitor.yaml"
    p.write_text(VISITOR_YAML_MALFORMED)
    with pytest.raises(ConfigError):
        load_visitor(str(p))
