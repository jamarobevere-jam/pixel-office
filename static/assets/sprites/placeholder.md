# Sprites

v1 renders people as plain colored circles (see `static/js/render.js`) —
no image assets required yet. `people.yaml` already assigns each person a
`sprite` filename (e.g. `sprite_01.png`) for forward-compatibility.

To switch to real pixelart sprites later:
1. Drop a licensed free pixelart character pack's frames into this
   directory, named to match the `sprite` field in `data/people.yaml`
   (or update `people.yaml` to match the pack's filenames).
2. Update `drawPeople()` in `static/js/render.js` to `drawImage()` the
   sprite at `person.x, person.y` instead of drawing a circle.

No backend changes are needed for this swap.
