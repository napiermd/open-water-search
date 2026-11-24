import {
  TILE_NAMES, center, element, insideTile, loadRun, loadSwimmers, matching, placeBox, placePoint, plural, searchAt, tileRect,
} from "./common.js";

// Every diagram on this page draws validation frame 2 from the sealed run: Ember's ranking of the nine tiles,
// its first two close looks, and the fixed grid's first two close looks on the same photo.
const FRAME_INDEX = 1;
const LOOKS = 2;
const byId = id => document.getElementById(id);

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

async function start() {
  const data = await loadRun("validation");
  const frame = data.frames[FRAME_INDEX];
  const chosen = searchAt(frame.searches.chosen, LOOKS);
  const grid = searchAt(frame.searches.grid, LOOKS);
  const boxes = await loadSwimmers(frame);
  const unchecked = 9 - chosen.opened.length;

  drawCoverage(addPhoto(byId("hero-photo"), frame, "Drone photo of open water with Ember's two close looks outlined and the other seven tiles shaded"), frame, chosen, "chosen");
  byId("hero-caption").textContent = "Validation frame 2, after one overview and two close looks. Ember marked "
    + plural(chosen.queue.length, "possible swimmer") + ". The " + unchecked + " shaded tiles haven’t had a close look yet.";

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

start().catch(() => {
  byId("hero-caption").textContent = "The recorded run couldn’t load. Serve this folder over HTTP and reload.";
});
