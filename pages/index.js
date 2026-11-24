import {
  TILE_NAMES, center, element, insideTile, loadRun, loadSwimmers, matching, placeBox, placePoint, plural, searchAt, tileRect,
} from "./common.js";

// The page opens with the live two-minute MOBDrone run, replayed from what the command printed and when.
// The photo diagrams below it draw validation frame 2 from the sealed run: Ember's ranking of the nine tiles,
// its first two close looks, and the fixed grid's first two close looks on the same photo.
const FRAME_INDEX = 1;
const LOOKS = 2;
const REPLAY_SPEED = 8;
const SHOWN_LINES = 40;
const STATUS_CLASS = { "not checked": "never", "checked, no sighting": "clear", flagged: "flagged", unreadable: "unreadable" };
const byId = id => document.getElementById(id);
let playback = 0;

function clock(seconds) {
  const whole = Math.floor(seconds);
  return Math.floor(whole / 60) + ":" + String(whole % 60).padStart(2, "0");
}

// One column per second of the flight, one cell per section of its frame, top left first.
function buildTimeline(clip) {
  const cells = clip.timeline.map(tiles => tiles.map(() => element("span")));
  byId("flight-timeline").replaceChildren(...cells.flat());
  return cells;
}

// Prints one recorded line and updates the coverage timeline: an overview turns its second's water unsearched,
// and a close look gives its section the status it ended the run with.
function showPrinted(entry, clip, cells) {
  const line = element("li");
  line.append(element("span", "at", clock(entry.t)), entry.line);
  if (entry.second === undefined) {
    line.className = entry.line.startsWith("Possible person") ? "handoff" : "summary";
  } else if (entry.tile === -1) {
    for (const cell of cells[entry.second]) cell.className = "never";
  } else {
    const status = clip.timeline[entry.second][entry.tile];
    cells[entry.second][entry.tile].className = STATUS_CLASS[status];
    if (status === "flagged") line.className = "sighting";
  }
  const printed = byId("flight-printed");
  printed.append(line);
  while (printed.children.length > SHOWN_LINES) printed.firstChild.remove();
}

function playFlight(clip, cells) {
  cancelAnimationFrame(playback);
  byId("flight-printed").replaceChildren();
  for (const cell of cells.flat()) cell.className = "";
  const finished = () => { byId("flight-clock").textContent = "Finished · recorded run, replayed at " + REPLAY_SPEED + "×"; };
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    for (const entry of clip.printed) showPrinted(entry, clip, cells);
    finished();
    return;
  }
  const started = performance.now();
  let next = 0;
  const step = now => {
    const elapsed = (now - started) / 1000 * REPLAY_SPEED;
    while (next < clip.printed.length && clip.printed[next].t <= elapsed) showPrinted(clip.printed[next++], clip, cells);
    if (next === clip.printed.length) {
      finished();
      return;
    }
    byId("flight-clock").textContent = clock(elapsed) + " into the run · replayed at " + REPLAY_SPEED + "×";
    playback = requestAnimationFrame(step);
  };
  playback = requestAnimationFrame(step);
}

function showPeople(clip) {
  const seconds = clip.timeline.length;
  const select = (person, button) => {
    for (const other of byId("people").querySelectorAll("button")) other.setAttribute("aria-pressed", String(other === button));
    byId("handoff-title").textContent = "Handoff message for possible person " + person.number;
    byId("handoff-text").textContent = person.message;
    byId("handoff-truth").textContent = person.labeled_people.length
      ? "MOBDrone’s labels put labeled person " + person.labeled_people.join(" and ") + " under these sightings."
      : "No labeled person is under these sightings. MOBDrone labels only people, so this may be a boat, a buoy or a false sighting.";
  };
  const rows = clip.people.map(person => {
    const held = person.labeled_people.join(", ");
    const span = element("span", "span" + (held ? "" : " none"));
    span.style.left = (100 * person.first / seconds) + "%";
    span.style.width = (100 * (person.last - person.first + 1) / seconds) + "%";
    const track = element("span", "track");
    track.append(span);
    const button = element("button");
    button.type = "button";
    button.append(element("span", "number", String(person.number)), track, element("span", "held", held ? "person " + held : "none"));
    button.setAttribute("aria-label", "Possible person " + person.number + ", seen " + clock(person.first) + " to " + clock(person.last)
      + (held ? ", labeled person " + held : ", no labeled person"));
    button.addEventListener("click", () => select(person, button));
    const row = element("li");
    row.append(button);
    return row;
  });
  byId("people").replaceChildren(...rows);
  select(clip.people[0], rows[0].firstChild);
}

async function startFlight() {
  const clip = await loadRun("live-clip");
  const cells = buildTimeline(clip);
  showPeople(clip);
  const replay = byId("flight-replay");
  replay.hidden = matchMedia("(prefers-reduced-motion: reduce)").matches;
  replay.addEventListener("click", () => playFlight(clip, cells));
  playFlight(clip, cells);
}

function addPhoto(container, frame, alt) {
  const image = element("img");
  image.src = frame.image;
  image.alt = alt;
  const layer = element("div", "layer");
  container.replaceChildren(image, layer);
  return layer;
}

function addMark(layer, point, frame) {
  const mark = element("div", "mark");
  placePoint(mark, point, frame);
  layer.append(mark);
}

// Opened tiles get an outline and their order, every other tile is shaded, and each mark becomes a pin.
function drawCoverage(layer, frame, search, arm) {
  for (let tile = 0; tile < 9; tile++) {
    const node = element("div", "tile");
    placeBox(node, tileRect(frame.width, frame.height, tile), frame);
    const order = search.opened.indexOf(tile);
    if (order === -1) {
      node.classList.add("unchecked");
    } else {
      node.classList.add("opened", arm);
      node.append(element("span", "order", String(order + 1)));
    }
    layer.append(node);
  }
  for (const point of search.queue) addMark(layer, point, frame);
}

function drawRanking(layer, frame, ranking) {
  ranking.forEach((tile, position) => {
    const node = element("div", "tile ranked" + (position < LOOKS ? " top" : ""));
    placeBox(node, tileRect(frame.width, frame.height, tile), frame);
    node.append(element("span", "rank", String(position + 1)));
    layer.append(node);
  });
}

function drawCrop(frame, tile, points, position) {
  const [left, top, right, bottom] = tileRect(frame.width, frame.height, tile);
  const view = element("div", "crop-view");
  const image = element("img");
  image.src = frame.image;
  image.alt = "Close look at the " + TILE_NAMES[tile] + " tile, " + plural(points.length, "mark");
  // Scale the whole photo so this tile fills the view, then shift the tile into place.
  image.style.width = (100 * frame.width / (right - left)) + "%";
  image.style.left = (-100 * left / (right - left)) + "%";
  image.style.top = (-100 * top / (bottom - top)) + "%";
  view.append(image, element("span", "tag", "Close look " + position + " · " + TILE_NAMES[tile]));
  for (const [x, y] of points) {
    const mark = element("div", "mark");
    mark.style.left = (100 * (x - left) / (right - left)) + "%";
    mark.style.top = (100 * (y - top) / (bottom - top)) + "%";
    view.append(mark);
  }
  return view;
}

function drawSwimmers(layer, frame, boxes, search) {
  const found = new Set(matching(search.queue, boxes).values());
  const opened = search.opened.map(tile => tileRect(frame.width, frame.height, tile));
  boxes.forEach((box, index) => {
    const node = element("div", "box" + (found.has(index) ? "" : " missed"));
    placeBox(node, box, frame);
    // Notes on swimmers near the right edge sit to their left so they stay inside the photo.
    node.classList.toggle("flip", center(box)[0] > frame.width * 0.7);
    if (!found.has(index)) {
      node.append(element("span", "note", opened.some(rect => insideTile(center(box), rect)) ? "Checked, missed" : "Never checked"));
    }
    layer.append(node);
  });
  return found.size;
}

function tileList(search) {
  return search.opened.map(tile => TILE_NAMES[tile]).join(" and ");
}

async function startSteps() {
  const data = await loadRun("validation");
  const frame = data.frames[FRAME_INDEX];
  const chosen = searchAt(frame.searches.chosen, LOOKS);
  const grid = searchAt(frame.searches.grid, LOOKS);
  const boxes = await loadSwimmers(frame);

  drawRanking(addPhoto(byId("step-overview"), frame, "The same photo split into nine tiles, numbered by Ember's ranking"), frame, chosen.overview.ranking);
  byId("step-crops").replaceChildren(...chosen.opened.map((tile, index) => {
    const call = frame.searches.chosen.find(item => item.tile === tile);
    return drawCrop(frame, tile, call.points ?? [], index + 1);
  }));
  drawCoverage(addPhoto(byId("step-handoff"), frame, "Coverage map: two tiles checked with a pin in each, seven tiles shaded"), frame, chosen, "chosen");

  const chosenLayer = addPhoto(byId("compare-chosen"), frame, "Ember's two close looks on validation frame 2");
  const gridLayer = addPhoto(byId("compare-grid"), frame, "The fixed grid's two close looks on validation frame 2");
  drawCoverage(chosenLayer, frame, chosen, "chosen");
  drawCoverage(gridLayer, frame, grid, "grid");
  const caption = (name, search, layer) => {
    const lead = element("b", "", name + " opened the " + tileList(search) + " tiles");
    const result = boxes
      ? "Found " + drawSwimmers(layer, frame, boxes, search) + " of " + plural(boxes.length, "swimmer") + "."
      : plural(search.queue.length, "mark") + " to review.";
    return [lead, result];
  };
  byId("compare-chosen-caption").replaceChildren(...caption("Ember", chosen, chosenLayer));
  byId("compare-grid-caption").replaceChildren(...caption("The fixed grid", grid, gridLayer));
}

const loadFailed = "The recorded run couldn’t load. Serve this folder over HTTP and reload.";
startFlight().catch(() => { byId("flight-clock").textContent = loadFailed; });
startSteps().catch(() => { byId("steps-note").textContent = loadFailed; });
