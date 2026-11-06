import json

from fastapi.testclient import TestClient

from app.main import app


def test_websocket_streams_initial_state():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        data = ws.receive_text()
        payload = json.loads(data)
        assert "people" in payload
        assert "floorplan" in payload
        assert len(payload["people"]) == 22
        jessica = next(person for person in payload["people"] if person["name"] == "Jessica")
        assert jessica["visitor"] is False
        assert jessica["has_desk"] is False
        assert (jessica["x"], jessica["y"]) == (48, 720)
        assert "Ghost" not in [person["name"] for person in payload["people"]]


def test_index_served_at_root():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<html" in resp.content.lower()


def test_jessica_sprite_is_served():
    client = TestClient(app)
    resp = client.get("/static/assets/sprites/jessica.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
