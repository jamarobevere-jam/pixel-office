import pytest
import yaml

from app.config_loader import (
    ConfigError,
    load_floorplan,
    load_people,
    load_interactions,
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

INTERACTIONS_YAML = """
exchanges:
  - ["Coffee?", "Always."]
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
    # desk 0 is at tile (4,6), tile_size 32 -> center (144, 208)
    assert sebastian.x == 4 * 32 + 16
    assert sebastian.y == 6 * 32 + 16


def test_load_people_raises_on_bad_desk_index(tmp_path):
    fp_path = tmp_path / "floorplan.yaml"
    fp_path.write_text(FLOORPLAN_YAML)
    fp = load_floorplan(str(fp_path))

    people_path = tmp_path / "people.yaml"
    people_path.write_text(PEOPLE_YAML_BAD_DESK)

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
