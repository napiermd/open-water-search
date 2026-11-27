const arms = { ember: "Detector + Ember", detector: "Detector alone" };
const caseVideo = "DJI_0804_0014_50m_2.mp4";
const slotLimit = 5;
const windowPicker = document.querySelector("#window");
const previous = document.querySelector("#previous");
const next = document.querySelector("#next");
const queues = document.querySelector("#queues");
const loadStatus = document.querySelector("#load-status");

let windows;
let currentIndex;
let selected = null;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function clock(seconds) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function windowRange({ start }) {
  return `${clock(start)}–${clock(start + 24)}`;
}

function openingDetails(window, opening) {
  const list = node("dl", undefined, "opening-details");
  const fields = {
    "Source recording": window.video,
    "Native frame (zero-based)": opening.native_frame,
    "Sampled second": opening.second,
    "Scored JPEG SHA-256": opening.jpeg_sha256,
    "Pin (x, y in px)": `${opening.x}, ${opening.y}`,
    "Simulated opening": `${opening.time} s from window start`,
    "Queue identity": opening.identity,
    "Ember checked": opening.checked ? "Yes" : "No",
    "Reference match": opening.track === null
      ? "None"
      : `Track ${opening.track} · ${window.settings[opening.track]}`,
    "Identity switches": opening.identity_switches,
  };
  for (const [label, value] of Object.entries(fields)) {
    list.append(node("dt", label), node("dd", value));
  }
  return list;
}

function renderQueue(window, arm, requestedArm, requestedSlot) {
  const cards = window.arms[arm];
  const section = node("section", undefined, `queue queue-${arm}`);
  const heading = node("h3", arms[arm]);
  heading.id = `queue-${arm}`;
  section.setAttribute("aria-labelledby", heading.id);

  const reached = new Set(cards.map(card => card.track).filter(track => window.settings[track] === "In water"));
  const empty = cards.filter(card => card.track === null).length;
  const summary = node("p",
    `${cards.length} of ${slotLimit} slots opened · ${reached.size} in water · ${empty} empty`, "queue-summary");
  section.append(heading, summary);
  if (!cards.length) return section;

  const list = node("ol", undefined, "openings");
  const seen = new Set();
  cards.forEach((opening, index) => {
    const slot = index + 1;
    const grade = window.settings[opening.track];
    const match = opening.track === null
      ? "Empty opening"
      : `Track ${opening.track} · ${seen.has(opening.track) ? "Repeat" : grade}`;
    seen.add(opening.track);

    const item = node("li");
    const id = `opening-${arm}-${slot}`;
    const button = node("button", undefined, "opening");
    button.type = "button";
    button.setAttribute("aria-controls", id);
    button.setAttribute("aria-expanded", "false");
    button.append(
      node("span", `Slot ${slot}`, "slot"),
      node("span", match, "match"),
      node("span", `Frame ${opening.native_frame} · Sample ${clock(opening.second)} · Opened +${opening.time.toFixed(3)} s`, "time"),
    );
    const details = openingDetails(window, opening);
    details.id = id;
    details.hidden = true;
    button.addEventListener("click", () => {
      const alreadyOpen = selected?.details === details;
      selectOpening(alreadyOpen ? null : { button, details, arm, slot });
      loadStatus.hidden = true;
      writeAddress();
    });
    item.append(button, details);
    list.append(item);
    if (arm === requestedArm && slot === requestedSlot) {
      selectOpening({ button, details, arm, slot });
    }
  });
  section.append(list);
  return section;
}

function selectOpening(selection) {
  if (selected) {
    selected.details.hidden = true;
    selected.button.setAttribute("aria-expanded", "false");
  }
  selected = selection;
  if (selection) {
    selection.details.hidden = false;
    selection.button.setAttribute("aria-expanded", "true");
  }
}

function renderSettings(window) {
  const matches = Object.fromEntries(Object.entries(window.arms).map(([arm, cards]) =>
    [arm, new Set(cards.map(card => card.track))]));
  const tracks = Object.entries(window.settings);
  const rows = document.querySelector("#settings-rows");
  document.querySelector("#settings-summary").textContent = `Reference tracks (${tracks.length})`;
  rows.closest("table").hidden = tracks.length === 0;
  document.querySelector("#no-tracks").hidden = tracks.length !== 0;
  rows.replaceChildren(...tracks.map(([track, grade]) => {
    const row = node("tr");
    const ember = matches.ember.has(Number(track));
    const detector = matches.detector.has(Number(track));
    let outcome = "Neither";
    if (ember && detector) outcome = "Both";
    else if (ember) outcome = "With Ember only";
    else if (detector) outcome = "Detector only";
    row.append(node("th", track), node("td", grade), node("td", outcome));
    row.firstElementChild.scope = "row";
    return row;
  }));
}

function renderWindow(index, requestedArm, requestedSlot) {
  currentIndex = index;
  const window = windows[index];
  windowPicker.value = String(index);
  previous.disabled = index === 0;
  next.disabled = index === windows.length - 1;
  document.querySelector("#window-context").textContent =
    `Window ${index + 1} of ${windows.length} · ${windowRange(window)} · Family ${window.family}`;
  selectOpening(null);
  queues.replaceChildren(...Object.keys(arms).map(arm =>
    renderQueue(window, arm, requestedArm, requestedSlot)));
  document.querySelector("#setting-grades").open = false;
  renderSettings(window);
}

function writeAddress() {
  const { video, start } = windows[currentIndex];
  const url = new URL(location.href);
  url.searchParams.set("video", video);
  url.searchParams.set("start", start);
  url.searchParams.delete("arm");
  url.searchParams.delete("slot");
  if (selected) {
    url.searchParams.set("arm", selected.arm);
    url.searchParams.set("slot", selected.slot);
  }
  history.replaceState(null, "", url);
}

function readAddress() {
  const params = new URLSearchParams(location.search);
  const video = params.get("video") ?? caseVideo;
  const start = Number(params.get("start") ?? 0);
  const index = windows.findIndex(window => window.video === video && window.start === start);
  const arm = params.get("arm");
  const slot = params.get("slot");
  let message = "";
  if (index < 0) {
    renderWindow(0);
    message = "That window is outside the archive. Showing the first recorded window.";
  } else {
    renderWindow(index, arm, Number(slot));
    if ((arm !== null || slot !== null) && !selected) {
      message = "That opening is unavailable. Choose another slot or window.";
    }
  }
  loadStatus.textContent = message;
  loadStatus.hidden = !message;
}

function moveTo(index) {
  loadStatus.hidden = true;
  renderWindow(index);
  writeAddress();
}

async function load() {
  loadStatus.textContent = "Loading the opening records…";
  loadStatus.hidden = false;
  const response = await fetch(new URL("./first-five/replay.json", import.meta.url));
  if (!response.ok) throw new Error(`Replay request failed (${response.status})`);
  const data = await response.json();
  if (data.schema !== 2 || !data.windows.length) throw new Error("Invalid opening records");
  windows = data.windows;
  windowPicker.replaceChildren(...windows.map((window, index) =>
    new Option(`${window.video.replace(/\.mp4$/, "")} · ${windowRange(window)}`, index)));
  readAddress();
  windowPicker.addEventListener("change", () => moveTo(Number(windowPicker.value)));
  previous.addEventListener("click", () => moveTo(currentIndex - 1));
  next.addEventListener("click", () => moveTo(currentIndex + 1));
  window.addEventListener("popstate", readAddress);
  document.querySelector("#replay").hidden = false;
  selected?.button.scrollIntoView({ block: "start" });
}

load().catch(() => {
  loadStatus.hidden = false;
  loadStatus.textContent = "The opening records could not load. Reload the page or download the offline audit above.";
});
