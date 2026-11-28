const element = id => document.getElementById(id);
const time = second => Math.floor(second / 60) + ":" + String(second % 60).padStart(2, "0");
const base = new URL("flight/", location.href);
const params = new URLSearchParams(location.search);

function placeRect(node, [left, top, right, bottom], item) {
  Object.assign(node.style, {
    left: 100 * left / item.width + "%", top: 100 * top / item.height + "%",
    width: 100 * (right - left) / item.width + "%", height: 100 * (bottom - top) / item.height + "%"
  });
}

function control(parent, label, click) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", click);
  parent.append(button);
  return button;
}

async function openFlight() {
  const response = await fetch(new URL("record.json", base));
  if (!response.ok) throw Error("Flight unavailable");
  const record = await response.json();
  const select = element("choice");
  for (const item of record.handoffs) {
    select.add(new Option(item.number + " of " + record.handoffs.length + " · " + time(item.second), item.number));
  }
  let selected = record.handoffs.find(item => String(item.number) === params.get("sighting")) || record.handoffs[0];
  const unknownSighting = params.has("sighting") && String(selected.number) !== params.get("sighting");
  let state = params.has("sighting") ? "handoff" : "sighting";
  select.value = selected.number;

  // The explorer's views. The current one is mirrored on the desk as data-view.
  const views = ["sighting", "handoff", "fins", "ripples", "dismissal", "label"];
  function show(next, focus = true) {
    if (!views.includes(next)) throw Error("Unknown flight explorer view: " + next);
    state = next;
    element("desk").dataset.view = next;
    const reviewing = next === "dismissal" || next === "label";
    const paired = next === "fins" || next === "ripples";
    const item = paired ? record.pair[next === "fins" ? 0 : 1] : reviewing ? record.missed : selected;
    const notes = element("notes");
    const actions = element("note-actions");
    const tools = element("tools");
    const title = element("detail-title");
    select.disabled = reviewing || paired;
    element("sighting-label").hidden = reviewing || paired;
    element("earlier").hidden = !reviewing && !paired;
    element("earlier").textContent = paired ? "Two detector flags · 0:36" : "Earlier flag · 0:12";
    element("overview").src = new URL(item.photo, base);
    element("overview").alt = "Full frame at " + time(item.second) + ", with the detector pin and inspected crop outlined";
    element("detail").src = new URL(item.crop, base);
    element("clock").textContent = time(item.second) + " / 2:00";
    element("crop-time").textContent = time(item.second);
    title.textContent = paired ? (next === "fins" ? "Flag 1 of 2 · kept" : "Flag 2 of 2 · dismissed") : reviewing ? "Dismissed flag" : "Possible person " + selected.number;
    element("verdict").textContent = ((reviewing || next === "ripples") ? "Ember dismissed this as " : "Ember kept this as ") + "“" + item.description + "”.";
    placeRect(element("region"), item.rect, item);
    Object.assign(element("pin").style, { left: 100*item.pin[0]/item.width+"%", top: 100*item.pin[1]/item.height+"%" });
    element("truth-box").hidden = next !== "label" && !paired;
    element("camera-note").textContent = next === "label" || paired ? "Dashed yellow box · labeled swimmer" : "White pin · inspected crop outlined";
    actions.replaceChildren();
    tools.replaceChildren();
    notes.hidden = next === "sighting" || next === "dismissal";

    if (next === "sighting") {
      const button = control(tools, "Open crew handoff", () => show("handoff"));
      if (focus) button.focus();
    } else if (next === "handoff") {
      element("note-title").textContent = "What the next crew gets";
      element("note").textContent = selected.handoff;
      const download = document.createElement("a");
      download.href = new URL(selected.packet, base);
      download.download = selected.packet;
      download.textContent = "Download this handoff";
      tools.append(download);
      control(actions, "Compare two flags at 0:36", () => show("fins"));
      control(actions, "Inspect the 0:12 dismissal", () => show("dismissal"));
      if (focus) element("note-title").focus();
    } else if (paired) {
      placeRect(element("truth-box"), record.pair[0].label, item);
      element("note-title").textContent = "Two flags. One labeled swimmer.";
      element("note").textContent = "At 0:36 the detector flagged a swimmer on the right and ripples at the left edge. Ember kept the swimmer and removed the empty alert. The dashed yellow box shows the dataset label.";
      const toggle = next === "fins" ? control(tools, "Inspect flag 2 · ripples", () => show("ripples")) : control(tools, "Inspect flag 1 · swimmer", () => show("fins"));
      control(actions, "Inspect the 0:12 dismissal", () => show("dismissal"));
      control(actions, "Return to handoff " + selected.number, () => show("handoff"));
      if (focus) toggle.focus();
    } else if (next === "dismissal") {
      const button = control(tools, "Reveal the flight label", () => show("label"));
      control(tools, "Back to handoff", () => show("handoff"));
      if (focus) button.focus();
    } else {
      placeRect(element("truth-box"), item.label, item);
      element("note-title").textContent = "The “duck” was a swimmer.";
      element("note").textContent = "At 0:12 the detector pin falls inside MOBDrone’s labeled swimmer. The same track appears in handoff 1 at 0:22. Ember dropped a real sighting ten seconds earlier. This flight carries no GPS coordinates for the swimmer.";
      control(actions, "Return to handoff " + selected.number, () => show("handoff"));
      if (focus) element("note-title").focus();
    }
  }
  select.addEventListener("change", () => {
    selected = record.handoffs.find(item => String(item.number) === select.value);
    show(state === "sighting" ? "sighting" : "handoff", false);
  });
  element("load").hidden = !unknownSighting;
  if (unknownSighting) element("load").textContent = "Sighting " + params.get("sighting") + " isn’t on this flight. Showing sighting 1 of " + record.handoffs.length + ".";
  element("desk").hidden = false;
  const showMiss = params.get("view") === "miss";
  show(showMiss ? "label" : state, false);
  if (showMiss || params.has("sighting")) element("desk").scrollIntoView();
}

const oldSections = new Set(["hero-title","live-check-title","record-title","gate-title","scale-title","story-title","checks-title","own-title","flight-title","compare-title","check-title","limits-title","run-title","how-title","detector-title"]);

// The crew reply is its own self-contained page, so its downloads stay identical. Size it to its content.
function fitCrewFrame() {
  const frame = element("crew-frame");
  if (!frame) return;
  const attach = () => {
    const page = frame.contentDocument;
    if (!page || page.URL === "about:blank") return;
    const fit = () => { frame.style.height = page.documentElement.scrollHeight + "px"; };
    new ResizeObserver(fit).observe(page.body);
    fit();
  };
  frame.addEventListener("load", attach);
  if (frame.contentDocument?.readyState === "complete") attach();
}

// The two moments shared with the video. Without motion, everything is already in its settled place.
const smooth = "cubic-bezier(0.42, 0, 0.58, 1)";
function onceInView(node, play) {
  if (!node || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const watcher = new IntersectionObserver(entries => {
    if (!entries.some(entry => entry.isIntersecting)) return;
    watcher.disconnect();
    play();
  }, { threshold: 0.45 });
  watcher.observe(node);
}

function liftFlags() {
  const board = document.querySelector(".flag-board");
  const rects = [...document.querySelectorAll(".flag-board .flag-rect")];
  onceInView(board, () => {
    for (const card of board.querySelectorAll(".flag-card")) {
      const from = rects[Number(card.dataset.from)].getBoundingClientRect();
      const to = card.getBoundingClientRect();
      const scale = from.width / to.width;
      const dx = from.left - to.left;
      const dy = from.top - to.top;
      card.animate([
        { transform: `translate(${dx}px, ${dy}px) scale(${scale})`, transformOrigin: "top left", filter: "brightness(.63)" },
        { transform: `translate(${dx / 2}px, ${dy / 2 - 33}px) scale(${(1 + scale) / 2})`, transformOrigin: "top left", offset: 0.5 },
        { transform: "none", transformOrigin: "top left", filter: "brightness(1)" },
      ], { duration: 1100, easing: smooth });
    }
  });
}

function turnSlotFive() {
  const section = document.querySelector(".queues");
  onceInView(section, () => {
    section.querySelectorAll(".slot-row").forEach(row => {
      [...row.children].forEach((slot, index) => slot.animate(
        [{ transform: "perspective(600px) rotateX(-90deg)", filter: "brightness(.63)" }, { transform: "none", filter: "brightness(1)" }],
        { duration: 380, delay: index * 45, easing: smooth, fill: "backwards" }));
    });
    section.querySelectorAll(".slot-crop").forEach((crop, index) => crop.animate(
      [{ transform: "perspective(900px) rotateX(-90deg)", filter: "brightness(.63)" }, { transform: "none", filter: "brightness(1)" }],
      { duration: 500, delay: 300 + index * 300, easing: smooth, fill: "backwards" }));
  });
}

// Anything focused or targeted mid-animation shows its settled state at once.
function settleOnFocus(selector) {
  const node = document.querySelector(selector);
  if (!node) return;
  const settle = () => node.getAnimations({ subtree: true }).forEach(animation => animation.finish());
  node.addEventListener("focusin", settle);
  node.addEventListener("click", settle);
}

// The crew panel starts on the pin screen. Links to it scroll the panel itself into view and give it focus.
// For a moment afterwards, a second click of a double click neither drops a pin nor selects the page.
function guardCrewLinks() {
  const frame = element("crew-frame");
  if (!frame) return;
  let guarded = false;
  document.addEventListener("mousedown", event => { if (guarded && event.detail > 1) event.preventDefault(); });
  for (const link of document.querySelectorAll('a[href="#crew"]')) {
    link.addEventListener("click", event => {
      event.preventDefault();
      guarded = true;
      frame.style.pointerEvents = "none";
      setTimeout(() => { frame.style.pointerEvents = ""; guarded = false; getSelection()?.removeAllRanges(); }, 600);
      const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
      frame.scrollIntoView({ block: "start", behavior: still ? "auto" : "smooth" });
      history.replaceState(null, "", "#crew");
      frame.focus({ preventScroll: true });
    });
  }
}

if (params.has("run") || params.has("case")) {
  location.replace("judge.html" + location.search + location.hash);
} else if (oldSections.has(location.hash.slice(1))) {
  location.replace("index.html" + location.hash);
} else {
  fitCrewFrame();
  liftFlags();
  turnSlotFive();
  settleOnFocus(".flag-board");
  settleOnFocus(".queues");
  guardCrewLinks();
  openFlight().catch(() => {
    element("desk").hidden = true;
    element("load").hidden = false;
    element("load").textContent = "The recorded flight could not load. ";
    const link = document.createElement("a");
    link.href = "flight/handoff-1.html";
    link.textContent = "Open the first offline handoff";
    element("load").append(link);
  });
}
