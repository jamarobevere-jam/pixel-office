import asyncio
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config_loader import load_floorplan, load_interactions, load_people, load_visitor
from app.simulation import Simulation

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TICK_HZ = 10

floorplan = load_floorplan(os.path.join(DATA_DIR, "floorplan.yaml"))
people = load_people(os.path.join(DATA_DIR, "people.yaml"), floorplan)
interactions = load_interactions(os.path.join(DATA_DIR, "interactions.yaml"))
visitor = load_visitor(os.path.join(DATA_DIR, "visitor.yaml"))
simulation = Simulation(
    people=people, floorplan=floorplan, interactions=interactions, visitor=visitor
)

connected_websockets: set[WebSocket] = set()


async def _broadcast_loop() -> None:
    """Single server-side tick loop: ticks the shared simulation at ~TICK_HZ
    and broadcasts the resulting state to every connected WebSocket."""
    last_time = time.monotonic()
    while True:
        await asyncio.sleep(1 / TICK_HZ)
        now = time.monotonic()
        dt = now - last_time
        last_time = now
        simulation.tick(now=now, dt=dt)
        state = simulation.to_state()

        stale = set()
        for ws in list(connected_websockets):
            try:
                await ws.send_json(state)
            except Exception:
                stale.add(ws)
        connected_websockets.difference_update(stale)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_broadcast_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_heuristic_static_caching(request: Request, call_next):
    # StaticFiles sets no Cache-Control header, so browsers fall back to
    # heuristic caching and can keep serving a stale index.html/JS/CSS for
    # a while after a real edit even on a manual reload. This forces
    # revalidation on every request instead (still cheap: a 304 when the
    # file hasn't changed) — a kiosk that stays open for days must pick up
    # deploys reliably.
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        # Send an immediate snapshot so a fresh connection doesn't wait up
        # to a full tick interval for its first frame.
        await websocket.send_json(simulation.to_state())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected_websockets.discard(websocket)
