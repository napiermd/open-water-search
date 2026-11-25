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
  let state = params.has("sighting") ? "handoff" : "sighting";
  select.value = selected.number;

  function show(next, focus = true) {
    state = next;
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
  element("load").hidden = true;
  element("desk").hidden = false;
  show(state, false);
}

const oldSections = new Set(["hero-title","live-check-title","record-title","gate-title","scale-title","story-title","checks-title","own-title","flight-title","compare-title","check-title","limits-title","run-title","how-title","detector-title"]);
if (params.has("run") || params.has("case")) {
  location.replace("judge.html" + location.search + location.hash);
} else if (oldSections.has(location.hash.slice(1))) {
  location.replace("index.html" + location.hash);
} else {
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
