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
        assert len(payload["people"]) == 21


def test_index_served_at_root():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<html" in resp.content.lower()
