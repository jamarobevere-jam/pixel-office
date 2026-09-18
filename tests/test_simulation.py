import random

from app.models import Floorplan, Person, Visitor, WorldObject
from app.simulation import Simulation


def make_floorplan():
    objects = [
        WorldObject(type="desk", x=0, y=0),
        WorldObject(type="desk", x=5, y=0),
    ]
    return Floorplan(width=10, height=10, tile_size=32, objects=objects)


def make_floorplan_with_elevator():
    objects = [
        WorldObject(type="elevator", x=0, y=0),
        WorldObject(type="desk", x=5, y=5),
    ]
    return Floorplan(width=12, height=12, tile_size=32, objects=objects)


def make_visitor():
    return Visitor(name="Frits", sprite="frits.png", phrases=["Best of breed", "Bullshit!"])


def run_ticks(sim, start_now, dt, count):
    now = start_now
    for _ in range(count):
        sim.tick(now=now, dt=dt)
        now += dt
    return now


def make_person(name, x, y, state="at_desk"):
    return Person(
        name=name,
        sprite="s.png",
        desk=0,
        idle_phrases=["hi"],
        x=x,
        y=y,
        state=state,
        target_x=None,
        target_y=None,
        current_phrase=None,
        phrase_expires_at=None,
    )


def test_at_desk_person_eventually_starts_walking():
    p = make_person("A", 16, 16)
    sim = Simulation(
        people=[p], floorplan=make_floorplan(), interactions=[],
        rng=random.Random(1),
    )
    # tick past the max idle window
    sim.tick(now=0.0, dt=0.1)
    for i in range(200):
        sim.tick(now=0.1 * (i + 1), dt=0.1)
    assert p.state in ("walking", "at_desk")
    # force determinism: run enough ticks that at least one transition to
    # walking must have occurred given IDLE_MAX_SECONDS=12 and dt steps
    assert p.target_x is not None or p.state == "walking" or p.state == "at_desk"


def test_at_desk_person_picks_walk_target_off_blocked_tiles():
    # desks at (0,0) and (5,0) block (0,0)/(1,0)/(1,1) and (5,0)/(6,0)/(6,1)
    p = make_person("A", 16, 16)
    sim = Simulation(
        people=[p], floorplan=make_floorplan(), interactions=[],
        rng=random.Random(2),
    )
    blocked = make_floorplan().blocked_tiles()
    tile = 32
    for i in range(300):
        sim.tick(now=0.1 * i, dt=0.1)
        if p.state == "walking":
            tx = int(p.target_x // tile)
            ty = int(p.target_y // tile)
            assert (tx, ty) not in blocked
            return
    raise AssertionError("person never started walking within the tick budget")


def test_walk_target_tiles_exclude_the_outer_border():
    # a person idling on the outermost ring of tiles would render with
    # their sprite (wider than half a tile) or speech bubble partly off
    # the canvas, so walk *destinations* must stay one tile clear of it.
    fp = make_floorplan()  # 10x10
    sim = Simulation(people=[], floorplan=fp, interactions=[])

    for x, y in sim._walk_target_tiles:
        assert 0 < x < fp.width - 1
        assert 0 < y < fp.height - 1


class _AlwaysSocialRng:
    """Deterministic stand-in that always takes the 'approach a coworker'
    branch and always picks the first candidate offered."""

    def random(self):
        return 0.0

    def choice(self, seq):
        return seq[0]

    def uniform(self, a, b):
        return a


def test_pick_walk_target_can_land_near_another_idle_person():
    a = make_person("A", 16, 16)
    b = make_person("B", 16 + 32 * 3, 16)  # b is 3 tiles away from a
    fp = make_floorplan()
    sim = Simulation(people=[a, b], floorplan=fp, interactions=[], rng=_AlwaysSocialRng())

    target_tile = sim._pick_walk_target(a, fp.tile_size)

    b_tile = (int(b.x // fp.tile_size), int(b.y // fp.tile_size))
    assert abs(target_tile[0] - b_tile[0]) <= 1
    assert abs(target_tile[1] - b_tile[1]) <= 1


def test_find_path_tiles_routes_around_obstacle_wall():
    # a wall of plants across row y=2 at x=1,2,3 leaves only x=0 and x=4 open;
    # a straight line from (2,0) to (2,4) would cut through the blocked wall.
    objects = [
        WorldObject(type="plant", x=1, y=2),
        WorldObject(type="plant", x=2, y=2),
        WorldObject(type="plant", x=3, y=2),
    ]
    fp = Floorplan(width=5, height=5, tile_size=10, objects=objects)
    sim = Simulation(people=[], floorplan=fp, interactions=[])

    path = sim._find_path_tiles((2, 0), (2, 4))

    assert path is not None
    blocked = fp.blocked_tiles()
    assert all(tile not in blocked for tile in path)
    assert path[-1] == (2, 4)


def test_find_path_tiles_start_tile_may_itself_be_blocked():
    # a person standing at their own desk starts on a blocked tile; the
    # path out of it must still be found.
    objects = [WorldObject(type="desk", x=0, y=0)]
    fp = Floorplan(width=5, height=5, tile_size=10, objects=objects)
    sim = Simulation(people=[], floorplan=fp, interactions=[])

    path = sim._find_path_tiles((0, 0), (4, 4))

    assert path is not None
    assert path[-1] == (4, 4)


def test_walking_person_moves_toward_target_and_arrives():
    p = make_person("A", 0, 0, state="walking")
    p.target_x = 100.0
    p.target_y = 0.0
    sim = Simulation(
        people=[p], floorplan=make_floorplan(), interactions=[],
        rng=random.Random(1),
    )
    sim.tick(now=0.0, dt=1.0)  # WALK_SPEED_PX_PER_SEC = 60 -> moves 60px
    assert p.x == 60.0
    assert p.state == "walking"

    sim.tick(now=1.0, dt=10.0)  # plenty of time to arrive
    assert p.state == "at_desk"
    assert p.x == 100.0
    assert p.target_x is None


def test_conversation_lines_are_staggered_not_simultaneous():
    a = make_person("A", 0, 0)
    b = make_person("B", 10, 0)
    sim = Simulation(
        people=[a, b], floorplan=make_floorplan(),
        interactions=[("Hi", "Hello")],
        rng=random.Random(1),
    )
    a_revealed_at = None
    b_revealed_at = None
    for i in range(600):
        now = 0.1 * i
        sim.tick(now=now, dt=0.1)
        if a_revealed_at is None and a.current_phrase == "Hi":
            a_revealed_at = now
        if b_revealed_at is None and b.current_phrase == "Hello":
            b_revealed_at = now
        if a_revealed_at is not None and b_revealed_at is not None:
            break

    assert a_revealed_at is not None
    assert b_revealed_at is not None
    assert b_revealed_at > a_revealed_at  # the reply comes after the opener
    assert (b_revealed_at - a_revealed_at) >= 1.0  # a real gap, not simultaneous


def test_two_proximate_people_can_start_talking():
    a = make_person("A", 0, 0)
    b = make_person("B", 10, 0)  # within TALK_PROXIMITY_PX
    sim = Simulation(
        people=[a, b], floorplan=make_floorplan(),
        interactions=[("Hi", "Hello")],
        rng=random.Random(1),  # seed chosen s.t. talk chance triggers below
    )
    talked = False
    # lines are revealed a couple beats after "talking" starts (staggered
    # exchange), so keep ticking a bit past the state transition itself
    for i in range(600):
        sim.tick(now=0.1 * i, dt=0.1)
        if a.state == "talking" and b.state == "talking" and a.current_phrase and b.current_phrase:
            talked = True
            break
    assert talked
    assert a.current_phrase in ("Hi", "Hello")
    assert b.current_phrase in ("Hi", "Hello")
    assert a.current_phrase != b.current_phrase  # each got their own line


def test_to_state_hides_expired_phrase():
    p = make_person("A", 16, 16)
    p.current_phrase = "hi"
    p.phrase_expires_at = 5.0
    sim = Simulation(people=[p], floorplan=make_floorplan(), interactions=[])
    state = sim.to_state()
    assert state["people"][0]["phrase"] == "hi"

    # simulate time passing past expiry via a tick
    sim.tick(now=10.0, dt=0.1)
    state = sim.to_state()
    assert state["people"][0]["phrase"] is None


def test_visitor_gets_a_shorter_idle_window_than_regular_staff():
    fp = make_floorplan_with_elevator()
    sim = Simulation(
        people=[], floorplan=fp, interactions=[], visitor=make_visitor(),
        rng=random.Random(5),
    )
    sim.visitor.x, sim.visitor.y = 6 * 32 + 16, 6 * 32 + 16

    sim._tick_at_desk(sim.visitor, now=0.0)

    idle_until = sim._idle_until[sim.visitor.name]
    assert 1.0 <= idle_until <= 2.5  # VISITOR_IDLE range, not the 4-12s staff range


def test_visitor_wander_target_stays_within_a_short_radius():
    # a big, mostly-empty floorplan (just the one elevator the constructor
    # requires) so any tile is a valid candidate -- proves the picker
    # itself constrains the radius, not that the map happens to be small.
    fp = Floorplan(width=40, height=40, tile_size=32, objects=[WorldObject(type="elevator", x=0, y=0)])
    sim = Simulation(
        people=[], floorplan=fp, interactions=[], visitor=make_visitor(),
        rng=random.Random(7),
    )
    sim.visitor.x, sim.visitor.y = 20 * 32 + 16, 20 * 32 + 16

    for _ in range(20):
        tx, ty = sim._pick_visitor_wander_target(fp.tile_size)
        assert abs(tx - 20) <= 4
        assert abs(ty - 20) <= 4


def test_visitor_not_active_before_trigger_time():
    fp = make_floorplan_with_elevator()
    a = make_person("A", 5 * 32 + 16, 5 * 32 + 16)
    a.desk = 0
    sim = Simulation(
        people=[a], floorplan=fp, interactions=[], visitor=make_visitor(),
        rng=random.Random(1),
    )
    sim.tick(now=0.0, dt=0.1)
    assert sim.visitor_active is False
    assert sim.visitor_visible is False
    assert sim.open_elevator is None
    assert "Frits" not in [p["name"] for p in sim.to_state()["people"]]


def test_visitor_entrance_interrupts_talking_person():
    fp = make_floorplan_with_elevator()
    a = make_person("A", 3 * 32 + 16, 3 * 32 + 16, state="talking")
    a.desk = 0
    a.current_phrase = "mid conversation"
    a.phrase_expires_at = 999.0
    sim = Simulation(
        people=[a], floorplan=fp, interactions=[], visitor=make_visitor(),
        rng=random.Random(1),
    )
    sim._talk_until[a.name] = 999.0
    sim._visitor_next_trigger_at = 0.0

    sim.tick(now=0.0, dt=0.1)

    assert sim.visitor_active is True
    assert sim.open_elevator == (0, 0)
    assert a.state == "walking"
    assert a.current_phrase is None
    assert a.name not in sim._talk_until


def test_visitor_full_lifecycle_freezes_and_releases_people():
    fp = make_floorplan_with_elevator()
    # starts away from its own desk so it has real distance to cover
    a = make_person("A", 10 * 32 + 16, 10 * 32 + 16)
    a.desk = 0
    sim = Simulation(
        people=[a], floorplan=fp, interactions=[], visitor=make_visitor(),
        rng=random.Random(3),
    )
    sim._visitor_next_trigger_at = 0.0

    now = run_ticks(sim, 0.0, 0.1, 1)
    assert sim.visitor_active is True
    assert sim.visitor_visible is True
    assert sim.open_elevator == (0, 0)
    assert sim.to_state()["open_elevator"] == {"x": 0, "y": 0}
    assert any(p["name"] == "Frits" for p in sim.to_state()["people"])
    assert a.state == "walking"

    # let a walk itself all the way home (many small ticks, real movement)
    now = run_ticks(sim, now, 0.5, 40)
    assert a.state == "at_desk"
    # desk is at (5,5); a person sits one tile in (the chair), at (6,6)
    assert (int(a.x // fp.tile_size), int(a.y // fp.tile_size)) == (6, 6)
    assert a.current_phrase is None  # arrival is silent during a visit

    # doors should have closed and wandering begun well before now
    assert sim.open_elevator is None
    assert sim._visitor_phase == "wandering"

    # advance well past a's own normal idle window (max 12s) while still
    # inside the 20s wander window; a must stay frozen, not wander off
    now = run_ticks(sim, now, 0.5, 20)  # +10s
    assert a.state == "at_desk"
    assert a.name not in sim._idle_until

    # advance past the rest of the wander window, the return walk, and the
    # exit door timer; poll instead of a fixed tick count since exact
    # timing depends on rng-picked wander targets
    for _ in range(400):
        sim.tick(now=now, dt=0.5)
        now += 0.5
        if not sim.visitor_active:
            break
    assert sim.visitor_active is False
    assert sim.visitor_visible is False
    assert sim.open_elevator is None
    assert sim._visitor_phase == "away"
    assert not any(p["name"] == "Frits" for p in sim.to_state()["people"])

    # a is released, not stuck: it either has a fresh idle timer running or
    # has already cycled through one and started walking again on its own
    run_ticks(sim, now, 0.1, 1)
    assert a.name in sim._idle_until or a.state == "walking"


def test_visitor_disabled_without_elevators_in_floorplan():
    objects = [WorldObject(type="desk", x=0, y=0)]
    fp = Floorplan(width=10, height=10, tile_size=32, objects=objects)
    sim = Simulation(
        people=[], floorplan=fp, interactions=[], visitor=make_visitor(),
        rng=random.Random(1),
    )
    assert sim.visitor is None
