const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");

const COLORS = {
  floor: "#d9c9a3",
  desk: "#8b5e34",
  plant: "#3f7a3f",
  window: "#bcd8f0",
};

let latestState = null;
let floorplanDrawn = false;

function drawFloorplan(floorplan) {
  canvas.width = floorplan.width * floorplan.tile_size;
  canvas.height = floorplan.height * floorplan.tile_size;
  ctx.fillStyle = COLORS.floor;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  for (const obj of floorplan.objects) {
    const px = obj.x * floorplan.tile_size;
    const py = obj.y * floorplan.tile_size;
    ctx.fillStyle = COLORS[obj.type] || "#999999";
    ctx.fillRect(px, py, floorplan.tile_size, floorplan.tile_size);
  }
}

function drawPeople(people) {
  for (const person of people) {
    ctx.fillStyle = person.state === "talking" ? "#f0a500" : "#2b6cb0";
    ctx.beginPath();
    ctx.arc(person.x, person.y, 10, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#ffffff";
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    ctx.fillText(person.name, person.x, person.y - 14);

    if (person.phrase) {
      const bubbleY = person.y - 30;
      ctx.fillStyle = "#ffffff";
      const textWidth = ctx.measureText(person.phrase).width;
      ctx.fillRect(person.x - textWidth / 2 - 4, bubbleY - 12, textWidth + 8, 16);
      ctx.fillStyle = "#000000";
      ctx.fillText(person.phrase, person.x, bubbleY);
    }
  }
}

function render() {
  if (latestState) {
    if (!floorplanDrawn) {
      // floor/desks/plants/windows are static; redraw each frame is cheap
      // enough at this scale (21 people, ~1200 tiles) so no offscreen
      // caching is needed for v1.
      floorplanDrawn = true;
    }
    drawFloorplan(latestState.floorplan);
    drawPeople(latestState.people);
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
    latestState = JSON.parse(event.data);
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
