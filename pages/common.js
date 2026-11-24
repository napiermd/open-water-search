// Shared by the replay and judge pages. Everything comes from the sealed runs, so viewing costs nothing.

export const TILE_NAMES = [
  "top left", "top center", "top right",
  "middle left", "center", "middle right",
  "bottom left", "bottom center", "bottom right",
];
export const REVIEW_LIMIT = 5;
export const SEARCH_NAMES = { chosen: "Ember chooses", grid: "Fixed grid" };

export async function loadRun(name) {
  const response = await fetch("runs/" + name + ".json");
  if (!response.ok) throw new Error("Missing run data for " + name);
  return response.json();
}

// Same integer tile boundaries as probe/runner.py.
export function tileRect(width, height, tile) {
  const column = tile % 3;
  const row = Math.floor(tile / 3);
  return [
    Math.floor(width * column / 3), Math.floor(height * row / 3),
    Math.floor(width * (column + 1) / 3), Math.floor(height * (row + 1) / 3),
  ];
}

// Swimmer boxes from a YOLO label file, or null when probe/fetch_frames.py has not downloaded it.
export async function loadSwimmers(frame) {
  const response = await fetch(frame.labels);
  if (!response.ok) return null;
  const boxes = [];
  for (const line of (await response.text()).split("\n")) {
    const parts = line.trim().split(/\s+/).map(Number);
    if (parts.length !== 5 || parts[0] !== 0) continue;
    const [, x, y, w, h] = parts;
    boxes.push([(x - w / 2) * frame.width, (y - h / 2) * frame.height, (x + w / 2) * frame.width, (y + h / 2) * frame.height]);
  }
  return boxes;
}

export function contains(point, box) {
  return box[0] <= point[0] && point[0] <= box[2] && box[1] <= point[1] && point[1] <= box[3];
}

export function center(box) {
  return [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2];
}

export function insideTile(point, rect) {
  return rect[0] <= point[0] && point[0] < rect[2] && rect[1] <= point[1] && point[1] < rect[3];
}

// Maximum one-to-one matching of points to swimmer boxes, as in probe/score.py. Returns point index -> box index.
export function matching(points, boxes) {
  const owners = new Map();
  function visit(i, seen) {
    for (let j = 0; j < boxes.length; j++) {
      if (seen.has(j) || !contains(points[i], boxes[j])) continue;
      seen.add(j);
      if (!owners.has(j) || visit(owners.get(j), seen)) {
        owners.set(j, i);
        return true;
      }
    }
    return false;
  }
  points.forEach((_, i) => visit(i, new Set()));
  return new Map([...owners].map(([box, point]) => [point, box]));
}

// What one search had after its first k close looks on a frame: tiles opened in order, cost, and the
// reviewer queue of its five highest-confidence marks.
export function searchAt(calls, looks) {
  const overview = calls.find(call => call.tile === -1);
  const closeLooks = calls.filter(call => call.tile >= 0).slice(0, looks);
  const marks = closeLooks.flatMap(call => call.points ?? []);
  const queue = marks.map((point, order) => ({ point, order }))
    .sort((a, b) => b.point[2] - a.point[2] || a.order - b.order)
    .slice(0, REVIEW_LIMIT)
    .map(entry => entry.point);
  const paid = closeLooks.reduce((sum, call) => sum + call.paid, overview ? overview.paid : 0);
  return {
    overview,
    opened: closeLooks.map(call => call.tile),
    unreadable: closeLooks.filter(call => call.points === null).map(call => call.tile),
    queue,
    paid,
  };
}

export function money(nanodollars) {
  return "$" + (nanodollars / 1e9).toFixed(4);
}

export function plural(count, word) {
  return count + " " + word + (count === 1 ? "" : "s");
}

function percent(value, scale) {
  return (100 * value / scale) + "%";
}

export function placeBox(element, [left, top, right, bottom], frame) {
  element.style.left = percent(left, frame.width);
  element.style.top = percent(top, frame.height);
  element.style.width = percent(right - left, frame.width);
  element.style.height = percent(bottom - top, frame.height);
}

export function placePoint(element, [x, y], frame) {
  element.style.left = percent(x, frame.width);
  element.style.top = percent(y, frame.height);
}

export function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
