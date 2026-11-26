const get = id => document.getElementById(id);
const time = second => Math.floor(second / 60) + ":" + String(second % 60).padStart(2, "0");
const key = card => card.method + "-" + card.rank;

function placeBox(id, [left, top, right, bottom]) {
  Object.assign(get(id).style, {
    left: left / 3840 * 100 + "%", top: top / 2160 * 100 + "%",
    width: (right - left) / 3840 * 100 + "%", height: (bottom - top) / 2160 * 100 + "%"
  });
}

async function openReplay() {
  const response = await fetch("cyprus/cards.json");
  if (!response.ok) throw Error("Missing handoffs");
  const cards = await response.json();
  for (const card of cards.filter(card => card.method === "detector")) {
    const link = document.createElement("a");
    link.textContent = String(card.rank);
    link.href = "#" + key(card);
    link.dataset.key = key(card);
    link.setAttribute("aria-label", "Detector rank " + card.rank);
    link.addEventListener("click", () => {
      if (get("wide").getBoundingClientRect().top < 0) {
        get("wide").scrollIntoView({block: "start"});
      }
    });
    get("ranks").append(link);
  }
  function select() {
    const card = cards.find(card => key(card) === location.hash.slice(1)) ||
      cards.find(card => key(card) === "detector-8");
    for (const link of document.querySelectorAll("[data-key]")) {
      if (link.dataset.key === key(card)) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    }
    get("wide").src = "cyprus/" + card.frame;
    get("crop").src = "cyprus/" + card.crop;
    placeBox("region", card.region);
    placeBox("target", card.target);
    get("point").style.left = card.pin[0] / 3840 * 100 + "%";
    get("point").style.top = card.pin[1] / 2160 * 100 + "%";
    const method = card.method === "ember" ? "With Ember" : "Detector";
    get("selection").textContent = method + " · rank " + card.rank + " · " + time(card.second);
    get("match").textContent = card.hit ? "The pin lands on the labeled swimmer." : "The pin falls outside the swimmer’s reference box.";
    get("reply").textContent = "Ember " + (card.kept ? "kept" : "dismissed") + " this crop. “" + card.words + "”";
  }
  select();
  window.addEventListener("hashchange", select);
  get("inspection").hidden = false;
  get("load").hidden = true;
}
openReplay().catch(() => { get("load").textContent = "The recorded cards could not load. Reload the page to try again."; });
