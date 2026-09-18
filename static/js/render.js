const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");

const COLORS = {
  floor: "#d9c9a3",
};

const TICK_INTERVAL_MS = 100; // matches server's ~10Hz tick rate
const SPRITE_SIZE = 40;

const spriteImages = new Map();

function getSpriteImage(filename) {
  let img = spriteImages.get(filename);
  if (!img) {
    img = new Image();
    img.src = `/static/assets/sprites/${filename}`;
    spriteImages.set(filename, img);
  }
  return img;
}

// Furniture is a small fixed set, preloaded eagerly so the offscreen
// floorplan (drawn once) doesn't race image decode.
const FURNITURE_FILES = {
  floor: "floor.png",
  deskLeft: "desk_left.png",
  deskRight: "desk_right.png",
  chair: "chair_gray_B.png",
  plant: "plant.png",
  waterDispenser: "Water_dispenser.png",
  trashEmpty: "trash_can_empty.png",
  trashFull: "trash_can_full.png",
  papers: "messy_papers.png",
  elevator: "elevator_closed.png",
  elevatorOpen: "elevator_open.png",
};
const MONITOR_FILES = ["Monitor1_B.png", "Monitor1_F.png", "Monitor3_off_F.png", "Monitor3_on_F.png"];
const MONITOR_LIFT = 20; // px shifted up so the monitor sits on the desk surface
const CHAIR_LIFT = 14; // px shifted up so the chair tucks under the monitor's tile
const CLUTTER_SCALE = 1.7; // bins/papers drawn this many times tile size, centered

const furnitureImages = {};
let furnitureReady = false;

function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(img); // degrade gracefully, don't block forever
    img.src = src;
  });
}

async function preloadFurniture() {
  const entries = Object.entries(FURNITURE_FILES);
  const monitorEntries = MONITOR_FILES.map((f) => [f, f]);
  const all = [...entries, ...monitorEntries];
  const loaded = await Promise.all(all.map(([, file]) => loadImage(`/static/assets/furniture/${file}`)));
  all.forEach(([key], i) => {
    furnitureImages[key] = loaded[i];
  });
  furnitureReady = true;
  cachedFloorplan = null; // force one offscreen redraw now that images are ready
}
preloadFurniture();

// Deterministic pick so a desk's monitor variant stays stable across redraws.
function pickMonitor(x, y) {
  const hash = (x * 73856093) ^ (y * 19349663);
  const index = Math.abs(hash) % MONITOR_FILES.length;
  return furnitureImages[MONITOR_FILES[index]];
}

let previousState = null;
let latestState = null;
let latestReceivedAt = null;

let floorplanCanvas = null;
let floorplanCtx = null;
let cachedFloorplan = null;

function drawFloorplanToOffscreen(floorplan) {
  floorplanCanvas = document.createElement("canvas");
  floorplanCanvas.width = floorplan.width * floorplan.tile_size;
  floorplanCanvas.height = floorplan.height * floorplan.tile_size;
  floorplanCtx = floorplanCanvas.getContext("2d");

  const tile = floorplan.tile_size;

  if (furnitureReady && furnitureImages.floor && furnitureImages.floor.naturalWidth) {
    const floorPattern = floorplanCtx.createPattern(furnitureImages.floor, "repeat");
    floorplanCtx.fillStyle = floorPattern;
    floorplanCtx.fillRect(0, 0, floorplanCanvas.width, floorplanCanvas.height);
  } else {
    floorplanCtx.fillStyle = COLORS.floor;
    floorplanCtx.fillRect(0, 0, floorplanCanvas.width, floorplanCanvas.height);
  }

  // Bottom-anchored: an image taller than one tile (plants, water dispenser)
  // is drawn so its bottom edge sits on the tile's bottom edge, growing
  // upward, matching how these assets are authored.
  function drawBottomAnchored(img, x, y) {
    if (!img || !img.naturalWidth) return;
    const drawY = y * tile + tile - img.naturalHeight;
    floorplanCtx.drawImage(img, x * tile, drawY);
  }

  function drawTile(img, x, y) {
    if (!img || !img.naturalWidth) return;
    floorplanCtx.drawImage(img, x * tile, y * tile);
  }

  // Small clutter (bins, papers) reads as too tiny at native tile size on
  // a kiosk display; draw it larger, centered on its tile.
  function drawTileScaled(img, x, y, scale) {
    if (!img || !img.naturalWidth) return;
    const size = tile * scale;
    const cx = x * tile + tile / 2;
    const cy = y * tile + tile / 2;
    floorplanCtx.drawImage(img, cx - size / 2, cy - size / 2, size, size);
  }

  for (const obj of floorplan.objects) {
    const px = obj.x * tile;
    const py = obj.y * tile;

    if (!furnitureReady) {
      // First paint before furniture images finish loading: flat rects so
      // the scene isn't blank; preloadFurniture() triggers a real redraw.
      floorplanCtx.fillStyle = "#999999";
      floorplanCtx.fillRect(px, py, tile, tile);
      continue;
    }

    switch (obj.type) {
      case "elevator":
        if (furnitureImages.elevator && furnitureImages.elevator.naturalWidth) {
          floorplanCtx.drawImage(furnitureImages.elevator, px, py);
        }
        break;
      case "desk": {
        const chair = furnitureImages.chair;
        if (chair && chair.naturalWidth) {
          floorplanCtx.drawImage(chair, obj.x * tile, (obj.y + 1) * tile - CHAIR_LIFT);
        }
        drawTile(furnitureImages.deskLeft, obj.x, obj.y);
        drawTile(furnitureImages.deskRight, obj.x + 1, obj.y);
        const monitor = pickMonitor(obj.x, obj.y);
        if (monitor && monitor.naturalWidth) {
          floorplanCtx.drawImage(monitor, (obj.x + 1) * tile, obj.y * tile - MONITOR_LIFT);
        }
        break;
      }
      case "plant":
        drawBottomAnchored(furnitureImages.plant, obj.x, obj.y);
        break;
      case "water_dispenser":
        drawBottomAnchored(furnitureImages.waterDispenser, obj.x, obj.y);
        break;
      case "trash_empty":
        drawTileScaled(furnitureImages.trashEmpty, obj.x, obj.y, CLUTTER_SCALE);
        break;
      case "trash_full":
        drawTileScaled(furnitureImages.trashFull, obj.x, obj.y, CLUTTER_SCALE);
        break;
      case "papers":
        drawTileScaled(furnitureImages.papers, obj.x, obj.y, CLUTTER_SCALE);
        break;
      default:
        floorplanCtx.fillStyle = "#999999";
        floorplanCtx.fillRect(px, py, tile, tile);
    }
  }

  cachedFloorplan = floorplan;

  if (canvas.width !== floorplanCanvas.width || canvas.height !== floorplanCanvas.height) {
    canvas.width = floorplanCanvas.width;
    canvas.height = floorplanCanvas.height;
  }
  scaleCanvasToFit();
}

// Scales the canvas's CSS box (not its pixel buffer) to fill the viewport
// while preserving the floorplan's aspect ratio, so the whole office is
// always visible and as large as the screen allows — relying on
// object-fit for this proved unreliable across environments, so the scale
// is computed and applied directly.
function scaleCanvasToFit() {
  if (!canvas.width || !canvas.height) return;
  const scale = Math.min(window.innerWidth / canvas.width, window.innerHeight / canvas.height);
  canvas.style.width = `${canvas.width * scale}px`;
  canvas.style.height = `${canvas.height * scale}px`;
}

window.addEventListener("resize", scaleCanvasToFit);

function floorplanChanged(floorplan) {
  if (!cachedFloorplan) return true;
  if (
    cachedFloorplan.width !== floorplan.width ||
    cachedFloorplan.height !== floorplan.height ||
    cachedFloorplan.tile_size !== floorplan.tile_size
  ) {
    return true;
  }
  return JSON.stringify(cachedFloorplan.objects) !== JSON.stringify(floorplan.objects);
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

const FONT_SIZE = 15;
const NAME_FONT = `${FONT_SIZE}px monospace`;
const BUBBLE_FONT = `bold ${FONT_SIZE}px monospace`;
const BUBBLE_HEIGHT = 24;
const BUBBLE_TOP_OFFSET = 18; // distance from text baseline to the bubble's top edge
const BUBBLE_PADDING = 6;
const BUBBLE_GAP = 4; // enforced clearance between stacked bubbles

function bubbleRectsOverlap(a, b) {
  return !(
    a.right < b.left - BUBBLE_GAP ||
    a.left > b.right + BUBBLE_GAP ||
    a.bottom < b.top - BUBBLE_GAP ||
    a.top > b.bottom + BUBBLE_GAP
  );
}

// Nearby people (especially mid-conversation) can have overlapping bubble
// rects at their natural anchor position; push a colliding bubble straight
// up, one bubble-height at a time, until it clears every bubble already
// placed this frame.
function layoutAndDrawBubbles(candidates) {
  const placedRects = [];
  for (const c of candidates) {
    let bubbleY = c.anchorY;
    // Clamp the half-width itself in case a phrase is somehow wider than
    // the whole canvas, then clamp the bubble's horizontal center so its
    // full width stays on-canvas even when the speaker is right at the
    // (now edge-avoiding, but not guaranteed for arbitrary text) border.
    const halfWidth = Math.min(c.width / 2 + BUBBLE_PADDING, canvas.width / 2);
    const bubbleX = Math.min(Math.max(c.x, halfWidth), canvas.width - halfWidth);
    for (let attempt = 0; attempt < 20; attempt++) {
      const rect = {
        left: bubbleX - halfWidth,
        right: bubbleX + halfWidth,
        top: bubbleY - BUBBLE_TOP_OFFSET,
        bottom: bubbleY - BUBBLE_TOP_OFFSET + BUBBLE_HEIGHT,
      };
      if (!placedRects.some((r) => bubbleRectsOverlap(rect, r))) {
        placedRects.push(rect);
        break;
      }
      bubbleY -= BUBBLE_HEIGHT + BUBBLE_GAP;
    }
    bubbleY = Math.max(bubbleY, BUBBLE_TOP_OFFSET); // keep the bubble top on-canvas too

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(bubbleX - halfWidth, bubbleY - BUBBLE_TOP_OFFSET, halfWidth * 2, BUBBLE_HEIGHT);
    ctx.fillStyle = "#000000";
    ctx.font = BUBBLE_FONT;
    ctx.textAlign = "center";
    ctx.fillText(c.text, bubbleX, bubbleY);
  }
}

function drawPeople(people, factor, prevPeopleByName) {
  const bubbleCandidates = [];

  for (const person of people) {
    let x = person.x;
    let y = person.y;
    const prev = prevPeopleByName ? prevPeopleByName.get(person.name) : null;
    if (prev) {
      x = lerp(prev.x, person.x, factor);
      y = lerp(prev.y, person.y, factor);
    }

    const sprite = getSpriteImage(person.sprite);
    if (sprite.complete && sprite.naturalWidth > 0) {
      ctx.drawImage(sprite, x - SPRITE_SIZE / 2, y - SPRITE_SIZE / 2, SPRITE_SIZE, SPRITE_SIZE);
    }

    ctx.fillStyle = "#ffffff";
    ctx.font = NAME_FONT;
    ctx.textAlign = "center";
    ctx.fillText(person.name, x, y - SPRITE_SIZE / 2 - 6);

    if (person.phrase) {
      ctx.font = BUBBLE_FONT; // measure at the font it'll actually draw with
      bubbleCandidates.push({
        x,
        anchorY: y - SPRITE_SIZE / 2 - 26,
        text: person.phrase,
        width: ctx.measureText(person.phrase).width,
      });
    }
  }

  layoutAndDrawBubbles(bubbleCandidates);
}

// The cached offscreen floorplan always draws elevators closed (door state
// isn't part of floorplan.objects); an open elevator is drawn fresh each
// frame on top, from the WebSocket state's separate open_elevator field.
function drawOpenElevator(openElevator, tile) {
  if (!openElevator) return;
  const img = furnitureImages.elevatorOpen;
  if (!img || !img.naturalWidth) return;
  ctx.drawImage(img, openElevator.x * tile, openElevator.y * tile);
}

function render() {
  if (latestState) {
    if (floorplanChanged(latestState.floorplan)) {
      drawFloorplanToOffscreen(latestState.floorplan);
    }

    ctx.drawImage(floorplanCanvas, 0, 0);
    drawOpenElevator(latestState.open_elevator, latestState.floorplan.tile_size);

    let factor = 1;
    let prevPeopleByName = null;
    if (previousState && latestReceivedAt !== null) {
      const elapsed = performance.now() - latestReceivedAt;
      factor = Math.min(1, Math.max(0, elapsed / TICK_INTERVAL_MS));
      prevPeopleByName = new Map(previousState.people.map((p) => [p.name, p]));
    }

    drawPeople(latestState.people, factor, prevPeopleByName);
  }
  requestAnimationFrame(render);
}

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

  ws.onopen = () => {
    statusEl.hidden = true;
  };

  ws.onmessage = (event) => {
    previousState = latestState;
    latestState = JSON.parse(event.data);
    latestReceivedAt = performance.now();
  };

  ws.onclose = () => {
    statusEl.hidden = false;
    setTimeout(connect, 2000);
  };

  ws.onerror = () => {
    ws.close();
  };
}

connect();
requestAnimationFrame(render);
