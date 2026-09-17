from app.models import WorldObject, Floorplan, Person


def test_floorplan_desks_returns_only_desks_in_order():
    objs = [
        WorldObject(type="window", x=0, y=0),
        WorldObject(type="desk", x=4, y=6),
        WorldObject(type="plant", x=2, y=2),
        WorldObject(type="desk", x=9, y=6),
    ]
    fp = Floorplan(width=40, height=30, tile_size=32, objects=objs)
    desks = fp.desks()
    assert [d.x for d in desks] == [4, 9]


def test_floorplan_blocked_tiles_covers_desk_footprint_and_chair():
    objs = [WorldObject(type="desk", x=4, y=6)]
    fp = Floorplan(width=40, height=30, tile_size=32, objects=objs)
    blocked = fp.blocked_tiles()
    assert (4, 6) in blocked  # desk_left
    assert (5, 6) in blocked  # desk_right
    assert (5, 7) in blocked  # chair


def test_floorplan_blocked_tiles_covers_plants_water_windows():
    objs = [
        WorldObject(type="plant", x=2, y=2),
        WorldObject(type="water_dispenser", x=1, y=15),
        WorldObject(type="window", x=4, y=0),
    ]
    fp = Floorplan(width=40, height=30, tile_size=32, objects=objs)
    blocked = fp.blocked_tiles()
    assert blocked == {(2, 2), (1, 15), (4, 0)}


def test_floorplan_blocked_tiles_excludes_floor_litter():
    objs = [
        WorldObject(type="trash_empty", x=6, y=10),
        WorldObject(type="trash_full", x=16, y=18),
        WorldObject(type="papers", x=12, y=11),
    ]
    fp = Floorplan(width=40, height=30, tile_size=32, objects=objs)
    assert fp.blocked_tiles() == set()


def test_person_defaults():
    p = Person(
        name="Sebastian",
        sprite="sprite_01.png",
        desk=0,
        idle_phrases=["Hello Hello"],
        x=100.0,
        y=200.0,
        state="at_desk",
        target_x=None,
        target_y=None,
        current_phrase=None,
        phrase_expires_at=None,
    )
    assert p.state == "at_desk"
    assert p.current_phrase is None
