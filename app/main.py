import asyncio
import os
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config_loader import load_floorplan, load_interactions, load_people
from app.simulation import Simulation

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TICK_HZ = 10

app = FastAPI()

floorplan = load_floorplan(os.path.join(DATA_DIR, "floorplan.yaml"))
people = load_people(os.path.join(DATA_DIR, "people.yaml"), floorplan)
interactions = load_interactions(os.path.join(DATA_DIR, "interactions.yaml"))
simulation = Simulation(people=people, floorplan=floorplan, interactions=interactions)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    last_time = time.monotonic()
    try:
        while True:
            now = time.monotonic()
            dt = now - last_time
            last_time = now
            simulation.tick(now=now, dt=dt)
            await websocket.send_json(simulation.to_state())
            await asyncio.sleep(1 / TICK_HZ)
    except WebSocketDisconnect:
        pass
