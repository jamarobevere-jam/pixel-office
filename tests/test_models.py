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
