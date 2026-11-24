import {
  SEARCH_NAMES, TILE_NAMES, center, element, insideTile, loadRun, loadSwimmers, matching, money,
  placeBox, placePoint, plural, searchAt, tileRect,
} from "./common.js";

const byId = id => document.getElementById(id);
const runs = {};
const swimmers = {};

async function runData(name) {
  runs[name] ??= await loadRun(name);
  return runs[name];
}

// Labels for every frame of a run, or null if any file is missing.
async function runSwimmers(name) {
  if (!(name in swimmers)) {
    const all = await Promise.all(runs[name].frames.map(loadSwimmers));
    swimmers[name] = all.some(boxes => boxes === null) ? null : all;
  }
  return swimmers[name];
}

function score(search, boxes) {
  const pairs = matching(search.queue, boxes);
  return { pairs, found: pairs.size, falseMarks: search.queue.length - pairs.size };
}

function drawPanel(arm, frame, search, boxes) {
  const layer = byId(arm + "-layer");
  layer.replaceChildren();
  for (let tile = 0; tile < 9; tile++) {
    const node = element("div", "tile");
    placeBox(node, tileRect(frame.width, frame.height, tile), frame);
    const order = search.opened.indexOf(tile);
    if (order === -1) {
      node.classList.add("unchecked");
    } else {
      node.classList.add("opened", arm);
      node.append(element("span", "order", String(order + 1)));
      if (search.unreadable.includes(tile)) node.append(element("span", "caption", "Answer unreadable"));
    }
    layer.append(node);
  }
  const result = boxes ? score(search, boxes) : null;
  if (boxes) {
    const found = new Set(result.pairs.values());
    const openedRects = search.opened.map(tile => tileRect(frame.width, frame.height, tile));
    boxes.forEach((box, index) => {
      const node = element("div", "box" + (found.has(index) ? "" : " missed"));
      placeBox(node, box, frame);
      if (!found.has(index)) {
        const checked = openedRects.some(rect => insideTile(center(box), rect));
        node.append(element("span", "note", checked ? "Checked, missed" : "Never checked"));
      }
      layer.append(node);
    });
  }
  search.queue.forEach((point, index) => {
    const node = element("div", "mark" + (result && !result.pairs.has(index) ? " false" : ""));
    placePoint(node, point, frame);
    layer.append(node);
  });
  const looks = plural(search.opened.length, "close look");
  const spend = (search.overview ? "Overview + " + looks : looks) + " · " + money(search.paid);
  const queue = result
    ? "Found " + result.found + " of " + boxes.length + " · " + plural(result.falseMarks, "mark") + " with no swimmer"
    : plural(search.queue.length, "mark") + " in the reviewer queue";
  byId(arm + "-stats").textContent = spend + " · " + queue;
  const image = byId(arm + "-image");
  image.src = frame.image;
  image.alt = SEARCH_NAMES[arm] + " on " + frame.frame + ": " + (search.opened.length
    ? "opened the " + search.opened.map(tile => TILE_NAMES[tile]).join(", then ") + " tile" + (search.opened.length > 1 ? "s" : "")
    : "no close looks");
}

async function start() {
  const params = new URLSearchParams(location.search);
  const state = {
    run: params.get("run") === "probe" ? "probe" : "validation",
    frame: Number(params.get("frame")) || 1,
    looks: Math.min(Math.max(Number(params.get("looks")) || 2, 1), 9),
    reveal: params.get("reveal") === "1",
  };
  const looksControl = byId("looks");
  for (let looks = 1; looks <= 9; looks++) {
    const label = element("label");
    const input = element("input");
    input.type = "radio";
    input.name = "looks";
    input.value = String(looks);
    label.append(input, String(looks));
    looksControl.append(label);
  }
  const select = byId("frame-select");
  let latestRender = 0;

  // Each change starts a new render. After every wait, a render stops if a newer one has started, so a slow
  // download can't paint over a choice the viewer has already changed. The controls update as soon as the
  // run data is in, and the panels once the labels are.
  async function render() {
    const ticket = ++latestRender;
    byId("view").setAttribute("aria-busy", "true");
    const { run, reveal } = state;
    const data = await runData(run);
    if (ticket !== latestRender) return;
    const frames = data.frames;
    state.frame = Math.min(Math.max(state.frame, 1), frames.length);
    if (select.dataset.run !== run) {
      select.replaceChildren(...frames.map((frame, index) => {
        const option = element("option", "", "Frame " + (index + 1) + " of " + frames.length);
        option.value = String(index + 1);
        return option;
      }));
      select.dataset.run = run;
    }
    for (const input of document.querySelectorAll("input[name=run]")) input.checked = input.value === run;
    for (const input of document.querySelectorAll("input[name=looks]")) input.checked = Number(input.value) === state.looks;
    byId("reveal").checked = reveal;
    select.value = String(state.frame);
    byId("previous").disabled = state.frame === 1;
    byId("next").disabled = state.frame === frames.length;
    history.replaceState(null, "", "?run=" + run + "&frame=" + state.frame + "&looks=" + state.looks + (reveal ? "&reveal=1" : ""));

    const labels = reveal ? await runSwimmers(run) : null;
    if (ticket !== latestRender) return;
    byId("label-note").textContent = reveal && !labels
      ? "Swimmer labels aren’t downloaded yet. Run python probe/fetch_frames.py, then reload."
      : "";
    document.body.classList.toggle("revealed", Boolean(labels));

    const frame = frames[state.frame - 1];
    for (const arm of ["chosen", "grid"]) {
      drawPanel(arm, frame, searchAt(frame.searches[arm], state.looks), labels && labels[state.frame - 1]);
    }

    byId("totals-title").textContent = "All 30 frames at " + plural(state.looks, "close look") + " per frame · " + data.title;
    byId("totals-body").replaceChildren(...["chosen", "grid"].map(arm => {
      const searches = frames.map(item => searchAt(item.searches[arm], state.looks));
      const spent = searches.reduce((sum, search) => sum + search.paid, 0);
      let found = "Reveal labels";
      let falseMarks = "Reveal labels";
      if (labels) {
        const results = searches.map((search, index) => score(search, labels[index]));
        const total = labels.reduce((sum, boxes) => sum + boxes.length, 0);
        found = results.reduce((sum, item) => sum + item.found, 0) + " of " + total;
        falseMarks = String(results.reduce((sum, item) => sum + item.falseMarks, 0));
      }
      const row = element("tr");
      row.append(element("td", "", SEARCH_NAMES[arm]), element("td", "", money(spent)), element("td", "", found), element("td", "", falseMarks));
      return row;
    }));
    byId("view").setAttribute("aria-busy", "false");
  }

  document.addEventListener("change", event => {
    const target = event.target;
    if (target.name === "run") { state.run = target.value; state.frame = 1; }
    if (target.name === "looks") state.looks = Number(target.value);
    if (target.id === "reveal") state.reveal = target.checked;
    if (target.id === "frame-select") state.frame = Number(target.value);
    render();
  });
  byId("previous").addEventListener("click", () => { state.frame -= 1; render(); });
  byId("next").addEventListener("click", () => { state.frame += 1; render(); });

  await render();
  byId("view").hidden = false;
  byId("loading").hidden = true;
}

start().catch(() => {
  byId("loading").hidden = true;
  byId("error").hidden = false;
});
