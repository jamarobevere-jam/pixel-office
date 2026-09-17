const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");

const COLORS = {
  floor: "#d9c9a3",
  desk: "#8b5e34",
  plant: "#3f7a3f",
  window: "#bcd8f0",
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

  floorplanCtx.fillStyle = COLORS.floor;
  floorplanCtx.fillRect(0, 0, floorplanCanvas.width, floorplanCanvas.height);

  for (const obj of floorplan.objects) {
    const px = obj.x * floorplan.tile_size;
    const py = obj.y * floorplan.tile_size;
    floorplanCtx.fillStyle = COLORS[obj.type] || "#999999";
    floorplanCtx.fillRect(px, py, floorplan.tile_size, floorplan.tile_size);
  }

  cachedFloorplan = floorplan;

  if (canvas.width !== floorplanCanvas.width || canvas.height !== floorplanCanvas.height) {
    canvas.width = floorplanCanvas.width;
    canvas.height = floorplanCanvas.height;
  }
}

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

function drawPeople(people, factor, prevPeopleByName) {
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
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    ctx.fillText(person.name, x, y - SPRITE_SIZE / 2 - 4);

    if (person.phrase) {
      const bubbleY = y - SPRITE_SIZE / 2 - 20;
      ctx.fillStyle = "#ffffff";
      const textWidth = ctx.measureText(person.phrase).width;
      ctx.fillRect(x - textWidth / 2 - 4, bubbleY - 12, textWidth + 8, 16);
      ctx.fillStyle = "#000000";
      ctx.fillText(person.phrase, x, bubbleY);
    }
  }
}

function render() {
  if (latestState) {
    if (floorplanChanged(latestState.floorplan)) {
      drawFloorplanToOffscreen(latestState.floorplan);
    }

    ctx.drawImage(floorplanCanvas, 0, 0);

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
