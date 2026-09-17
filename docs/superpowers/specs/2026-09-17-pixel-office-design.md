# Pixel Office — Design Spec

Date: 2026-09-17

## Purpose

Webapp showing pixelart "people" moving around a pixelart office floorplan
(desks, plants, windows), idling at desks, wandering, and occasionally
showing speech-bubble phrases — including scripted 2-line exchanges when
two people are near each other. Deployed on Azure App Service, displayed
on company monitors (kiosk-style, no user interaction needed).

## Architecture

- **Backend:** Python, FastAPI. Runs the simulation tick loop in-memory
  (no DB — ephemeral state is fine for a kiosk display). Pushes state to
  connected clients over a WebSocket. Serves static frontend files.
- **Frontend:** Plain HTML/CSS/JS + HTML5 Canvas. Connects to the
  WebSocket, receives person state each tick, renders floorplan + sprites
  + speech bubbles. No frontend framework — keeps it light for a kiosk
  browser tab that may run unattended for days.
- **Deploy:** Dockerized FastAPI app → Azure App Service (single
  container, always-on).

## Data model

### `data/floorplan.yaml`
Grid-based layout: overall grid size, and placement of desks, plants,
windows, walls. Hardcoded to start as one big square open-plan office;
structured so it can be swapped/edited later without code changes.

```yaml
grid:
  width: 40
  height: 30
  tile_size: 32
objects:
  - type: desk
    x: 4
    y: 3
  - type: plant
    x: 10
    y: 2
  - type: window
    x: 0
    y: 5
  # ... walls, more desks, etc.
```

### `data/people.yaml`
One entry per person: name, assigned desk (by index or coordinates),
sprite variant (cycled/assigned from the free pixelart pack), idle
phrases, and interaction phrases (used in 2-person exchanges).

```yaml
people:
  - name: Sebastian
    sprite: variant_01
    desk: 0
    idle_phrases:
      - "Hello Hello"
  - name: Jose
    sprite: variant_02
    desk: 1
    idle_phrases:
      - "It works on my machine ¯\\_(ツ)_/¯"
  # ... one entry per person below
```

Full initial roster (21 people, one idle phrase each — can grow later):

| Name | Phrase |
|---|---|
| Sebastian | Hello Hello |
| Jose | It works on my machine ¯\_(ツ)_/¯ |
| Abhishek | Blaming Microsoft Since Forever |
| Rahul | Relationships. Not just records. |
| Leandro | I should be working |
| Violetta | They're supposed to be working |
| Chandra | Dynamic(s) by design |
| Lukas | I'm supposed to be working |
| Kit | I'm working |
| Yogesh | Keep Calm and Sync CRM |
| Azamat | I know what you broke last summer |
| Gustavo | I need coffee |
| Luis | Well, actually… |
| Joao | Blaming Microsoft Since Forever |
| Gaurav | Quick Call ? |
| Irina | I don't break your app, I test its patience. |
| Daan | You're on mute |
| Madhuri | Blaming Microsoft Since Forever |
| Raksha | Everything is stable, until QA logs in |
| Matei | Working as intended |
| Rachel | Low Risk Appetite |

Interaction phrase pairs (scripted 2-line exchanges) are a separate list
in `people.yaml` (or a sibling `interactions.yaml`), each entry a
`[speaker_a_line, speaker_b_line]` pair, chosen randomly and assigned to
whichever two people happen to be proximate — not tied to specific named
pairs, so any two idle people can trigger any exchange.

## Simulation logic

Each person is a simple state machine:

- **at_desk** — sitting, occasionally shows an idle phrase bubble on a
  random timer.
- **walking** — moving toward a randomly chosen destination (another
  desk area or open floor tile), pixel-stepped per tick.
- **talking** — triggered when two `at_desk`-or-idle people end up
  within a small proximity radius; both pause, show a 2-line scripted
  exchange (one bubble each, staggered), then resume.

Tick loop (server-side, ~10 Hz): update positions, evaluate state
transitions (idle timeout → pick new walk target; arrived → idle;
proximity check → maybe start exchange), broadcast full state snapshot
over WebSocket.

## Frontend rendering

- Canvas sized to floorplan grid × tile_size.
- Static layer: floorplan tiles (floor, walls, desks, plants, windows)
  drawn once (or cached to an offscreen canvas).
- Dynamic layer: redraw each person's sprite at its current pixel
  position every animation frame (interpolating between server ticks for
  smoothness), plus speech bubble overlay when active.

## Assets

Free pixelart office/character tileset (LPC-style or similar, itch.io /
OpenGameArt, license permitting) for the floor/desks/plants/windows and
character sprites. Assigned to people round-robin or by simple mapping
in `people.yaml`.

## Project structure

```
app/
  main.py            # FastAPI app, WebSocket endpoint, static file serving
  simulation.py      # tick loop, state machine, movement, phrase/interaction logic
  models.py          # Person, Floorplan dataclasses
  config_loader.py   # loads people.yaml / floorplan.yaml
data/
  people.yaml
  floorplan.yaml
  interactions.yaml
static/
  index.html
  js/render.js
  css/style.css
  assets/sprites/...
requirements.txt
Dockerfile
```

## Error handling

- Missing/invalid YAML config → fail fast at startup with a clear error
  (kiosk deploy should never silently show a broken/empty office).
- WebSocket disconnect/reconnect handled client-side with simple retry —
  kiosk browser must recover without manual intervention.

## Testing

- Unit tests for simulation state machine transitions (idle → walking →
  talking → idle) and config loading (valid/invalid YAML).
- Manual browser check for rendering/animation smoothness (no automated
  visual testing planned for v1).

## Out of scope (v1)

- User interaction/control (kiosk is view-only).
- Persistent state across restarts.
- Admin UI for editing people/floorplan (edit YAML files directly).
- Scripted per-person daily schedules (random walk only, per approved
  design).
