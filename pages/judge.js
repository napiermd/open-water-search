import {
  TILE_NAMES, center, contains, element, insideTile, loadRun, loadSwimmers, matching,
  placeBox, placePoint, plural, tileRect,
} from "./common.js";

const byId = id => document.getElementById(id);
const STEP_FOR_STAGE = { flag: "flag", crop: "flag", pin: "flag", pick: "pick", next: "pick", reveal: "reveal" };
const DECISIONS = { swimmer: "You marked a swimmer", dismiss: "You dismissed the flag", unsure: "You couldn’t tell" };

// A case qualifies when Ember's first close look flagged something and at least one labeled swimmer
// lies outside that tile, so the next reviewer still has someone to find. Cases follow manifest order.
function qualifyingCases(frames, labels) {
  const cases = [];
  frames.forEach((frame, index) => {
    const overview = frame.searches.chosen.find(call => call.tile === -1);
    const first = overview?.ranking?.[0];
    if (first === undefined) return;
    const firstLook = frame.searches.chosen.find(call => call.tile === first);
    const rect = tileRect(frame.width, frame.height, first);
    if (firstLook?.points?.length && labels[index].some(box => !insideTile(center(box), rect))) {
      cases.push({ frame, boxes: labels[index], ranking: overview.ranking, number: index + 1 });
    }
  });
  return cases;
}

function pointsFor(frame, tile) {
  return frame.searches.chosen.find(call => call.tile === tile)?.points ?? [];
}

async function start() {
  const params = new URLSearchParams(location.search);
  const run = params.get("run") === "probe" ? "probe" : "validation";
  const data = await loadRun(run);
  const labels = await Promise.all(data.frames.map(loadSwimmers));
  if (labels.some(boxes => boxes === null)) {
    throw new Error("Swimmer labels aren’t downloaded yet. Run python probe/fetch_frames.py, then reload.");
  }
  const cases = qualifyingCases(data.frames, labels);
  let caseIndex = Math.min(Math.max(Number(params.get("case")) || 1, 1), cases.length) - 1;
  let state;
  let current;

  const image = byId("full");
  const layer = byId("layer");
  const cropCanvas = byId("crop");
  const cropLayer = byId("crop-layer");
  const tileButtons = byId("tile-buttons");
  const pinArea = byId("pin-area");

  function frameRect(tile) {
    return tileRect(current.frame.width, current.frame.height, tile);
  }

  function drawCrop(tile, caption) {
    const [left, top, right, bottom] = frameRect(tile);
    cropCanvas.width = right - left;
    cropCanvas.height = bottom - top;
    cropCanvas.getContext("2d").drawImage(image, left, top, right - left, bottom - top, 0, 0, right - left, bottom - top);
    cropCanvas.setAttribute("aria-label", "Close look at the " + TILE_NAMES[tile] + " tile");
    cropLayer.replaceChildren(...pointsFor(current.frame, tile).map(([x, y]) => {
      const mark = element("div", "mark");
      mark.style.left = (100 * (x - left) / (right - left)) + "%";
      mark.style.top = (100 * (y - top) / (bottom - top)) + "%";
      return mark;
    }));
    byId("crop-caption").textContent = caption;
    byId("crop-figure").hidden = false;
  }

  function opened() {
    return [current.first, ...(state.pick !== null && ["next", "reveal"].includes(state.stage) ? [state.pick] : [])];
  }

  function drawFrame() {
    layer.replaceChildren();
    const frame = current.frame;
    const reviewed = state.stage !== "flag";
    for (let tile = 0; tile < 9; tile++) {
      const node = element("div", "tile");
      placeBox(node, frameRect(tile), frame);
      if (tile === current.first) {
        node.classList.add("opened", "chosen");
        if (reviewed) node.classList.add("reviewed");
        node.append(element("span", "caption", reviewed ? "Ember checked · you reviewed" : "Ember checked"));
      } else if (tile === state.pick && ["next", "reveal"].includes(state.stage)) {
        node.classList.add("pick", "reviewed");
        node.append(element("span", "caption", "Your next look"));
      } else {
        node.classList.add("unchecked");
      }
      layer.append(node);
    }
    const marks = opened().flatMap(tile => pointsFor(frame, tile));
    if (state.stage === "reveal") {
      const found = new Set(matching(marks, current.boxes).values());
      const rects = opened().map(frameRect);
      current.boxes.forEach((box, index) => {
        const node = element("div", "box" + (found.has(index) ? "" : " missed"));
        placeBox(node, box, frame);
        if (!found.has(index)) {
          node.append(element("span", "note", rects.some(rect => insideTile(center(box), rect)) ? "Checked, not marked" : "Never checked"));
        }
        layer.append(node);
      });
    }
    for (const point of marks) {
      const node = element("div", "mark" + (state.stage === "reveal" && !current.boxes.some(box => contains(point, box)) ? " false" : ""));
      placePoint(node, point, frame);
      layer.append(node);
    }
    if (state.pin) {
      const pin = element("div", "mark person");
      placePoint(pin, state.pin, frame);
      layer.append(pin);
    }
    byId("pin-key").hidden = !state.pin;
    document.body.classList.toggle("revealed", state.stage === "reveal");
  }

  function setActions(buttons) {
    byId("actions").replaceChildren(...buttons.map(([label, kind, handler, disabled]) => {
      const button = element("button", kind, label);
      button.type = "button";
      button.disabled = Boolean(disabled);
      button.addEventListener("click", handler);
      return button;
    }));
  }

  function go(stage) {
    state.stage = stage;
    byId("status").textContent = "";
    render();
    byId("task-title").focus({ preventScroll: true });
    // On narrow screens the frame sits above the task panel; bring it back when the next step happens on it.
    const photo = byId("frame-photo").getBoundingClientRect();
    if ((stage === "pin" || stage === "pick") && (photo.top < 0 || photo.bottom > innerHeight)) {
      byId("frame-photo").scrollIntoView({ block: "start" });
    }
  }

  function results() {
    const frame = current.frame;
    const flagPoints = pointsFor(frame, current.first);
    const top = [...flagPoints].sort((a, b) => b[2] - a[2])[0];
    const flagBox = current.boxes.find(box => contains(top, box));
    const pickRect = frameRect(state.pick);
    const inPick = current.boxes.filter(box => insideTile(center(box), pickRect));
    const pickFound = matching(pointsFor(frame, state.pick), inPick).size;
    const secondRect = frameRect(current.ranking[1]);
    const inSecond = current.boxes.filter(box => insideTile(center(box), secondRect)).length;
    const rects = opened().map(frameRect);
    const unchecked = current.boxes.filter(box => !rects.some(rect => insideTile(center(box), rect))).length;
    let call = DECISIONS[state.decision] + ".";
    if (state.decision === "swimmer") {
      const pinBox = current.boxes.find(box => contains(state.pin, box));
      call += pinBox ? (pinBox === flagBox ? " Your pin is on the same swimmer Ember marked." : " Your pin is on a labeled swimmer, a different one from Ember’s top mark.") : " Your pin isn’t inside a labeled swimmer box.";
    }
    const rows = [
      ["Ember’s flag", flagBox ? "Ember’s top mark in the " + TILE_NAMES[current.first] + " tile is on a labeled swimmer." : "Ember’s top mark in the " + TILE_NAMES[current.first] + " tile has no swimmer under it."],
      ["Your call", call],
      ["Your next look", "The " + TILE_NAMES[state.pick] + " tile held " + plural(inPick.length, "labeled swimmer") + ". Ember’s recorded close look there marked " + pickFound + "."],
      ["Ember’s own next pick", "Ember ranked the " + TILE_NAMES[current.ranking[1]] + " tile second" + (current.ranking[1] === state.pick ? ", the same tile you picked." : ". It held " + plural(inSecond, "labeled swimmer") + ".")],
      ["Still unchecked", unchecked ? plural(unchecked, "swimmer") + (unchecked === 1 ? " remains" : " remain") + " in tiles nobody has looked at closely yet." : "Every labeled swimmer is in a tile someone has now checked."],
    ];
    byId("results").replaceChildren(...rows.map(([term, text]) => {
      const row = element("div");
      row.append(element("dt", "", term), element("dd", "", text));
      return row;
    }));
  }

  function render() {
    const stage = state.stage;
    for (const step of byId("steps").children) {
      if (step.dataset.step === STEP_FOR_STAGE[stage]) step.setAttribute("aria-current", "step");
      else step.removeAttribute("aria-current");
    }
    pinArea.hidden = stage !== "pin";
    tileButtons.hidden = stage !== "pick";
    byId("results").hidden = stage !== "reveal";
    byId("crop-figure").hidden = !["crop", "pin", "next"].includes(stage);
    for (const button of tileButtons.children) button.setAttribute("aria-pressed", String(Number(button.dataset.tile) === state.pick));
    const where = TILE_NAMES[current.first];
    const copy = {
      flag: ["Ember flagged something", "Ember’s first close look went to the " + where + " tile. Open it and decide what you see."],
      crop: ["Is this a swimmer?", "This is the close look Ember received, with its mark. Every choice keeps the search going."],
      pin: ["Place your pin", "Click the swimmer on the full frame so the next person knows exactly which one you mean."],
      pick: ["Where would you look next?", "Ember has checked one tile. Pick any other tile for the next close look."],
      next: ["Your next look", "This is Ember’s recorded close look at the tile you picked."],
      reveal: ["What was there", "Labeled swimmers are now drawn on the frame."],
    }[stage];
    byId("task-title").textContent = copy[0];
    byId("task-text").textContent = copy[1];
    if (stage === "crop" || stage === "pin") drawCrop(current.first, "Ember’s close look at the " + where + " tile");
    if (stage === "next") drawCrop(state.pick, "Ember’s recorded close look at the " + TILE_NAMES[state.pick] + " tile · " + plural(pointsFor(current.frame, state.pick).length, "mark"));
    if (stage === "reveal") results();
    const decide = decision => () => {
      state.decision = decision;
      state.pin = null;
      go(decision === "swimmer" ? "pin" : "pick");
    };
    setActions({
      flag: [["Open Ember’s close look", "primary", () => go("crop")]],
      crop: [["Mark a swimmer", "primary", decide("swimmer")], ["Dismiss the flag", "secondary", decide("dismiss")], ["Can’t tell", "secondary", decide("unsure")]],
      pin: [["Lock my pin", "primary", () => go("pick"), !state.pin], ["Back", "secondary", () => go("crop")]],
      pick: [["Open this tile", "primary", () => go("next"), state.pick === null]],
      next: [["Reveal the labels", "primary", () => go("reveal")]],
      reveal: [["Try another search", "primary", () => load((caseIndex + 1) % cases.length)], ["Start this one over", "secondary", () => load(caseIndex)]],
    }[stage]);
    drawFrame();
    history.replaceState(null, "", "?run=" + run + "&case=" + (caseIndex + 1));
  }

  async function load(index) {
    caseIndex = index;
    const first = cases[index].ranking[0];
    current = { ...cases[index], first };
    state = { stage: "flag", decision: null, pin: null, pick: null };
    if (image.getAttribute("src") !== current.frame.image) {
      image.src = current.frame.image;
      await image.decode();
    }
    image.alt = "Wide drone frame " + current.number + " of the " + (run === "validation" ? "validation" : "first") + " run";
    byId("frame-meta").textContent = "Search " + (index + 1) + " of " + cases.length + " · frame " + current.number + " of 30";
    tileButtons.replaceChildren(...Array.from({ length: 9 }, (_, tile) => {
      const button = element("button");
      button.type = "button";
      button.dataset.tile = String(tile);
      button.disabled = tile === first;
      button.setAttribute("aria-label", TILE_NAMES[tile] + (tile === first ? ", Ember checked" : ", not checked"));
      placeBox(button, frameRect(tile), current.frame);
      button.addEventListener("click", () => {
        state.pick = tile;
        byId("status").textContent = TILE_NAMES[tile] + " tile selected.";
        render();
      });
      return button;
    }));
    byId("status").textContent = "";
    render();
  }

  function placePin(x, y) {
    const frame = current.frame;
    state.pin = [Math.max(0, Math.min(x, frame.width - 1)), Math.max(0, Math.min(y, frame.height - 1))];
    byId("status").textContent = "Pin placed. Move it or lock it.";
    render();
  }
  pinArea.addEventListener("click", event => {
    const box = pinArea.getBoundingClientRect();
    if (event.detail === 0) {
      placePin(...(state.pin ?? [current.frame.width / 2, current.frame.height / 2]));
      return;
    }
    placePin((event.clientX - box.left) * current.frame.width / box.width, (event.clientY - box.top) * current.frame.height / box.height);
  });
  const arrows = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
  pinArea.addEventListener("keydown", event => {
    const move = arrows[event.key];
    if (!move) return;
    event.preventDefault();
    const [x, y] = state.pin ?? [current.frame.width / 2, current.frame.height / 2];
    const step = (event.shiftKey ? 0.04 : 0.01) * current.frame.width;
    placePin(x + move[0] * step, y + move[1] * step);
  });

  await load(caseIndex);
  byId("workspace").hidden = false;
  byId("loading").hidden = true;
}

start().catch(error => {
  byId("loading").hidden = true;
  byId("error").textContent = error.message.startsWith("Swimmer labels") ? error.message : "The recorded search couldn’t load. Serve this folder over HTTP and reload.";
  byId("error").hidden = false;
});
