// Run against a local site with Playwright installed:
// node probe/test_0014_browser.cjs http://127.0.0.1:8757
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const { mkdtemp, readFile, rm } = require("node:fs/promises");
const { tmpdir } = require("node:os");
const { join } = require("node:path");
const { pathToFileURL } = require("node:url");
const { chromium } = require("playwright");

const origin = process.argv[2] ?? "http://127.0.0.1:8757";
const caseUrl = new URL("/pages/0014.html", origin).href;
const auditWindow = "first-five.html?video=DJI_0804_0014_50m_2.mp4&start=0";

async function inspectCases(page) {
  assert.match(await page.locator("blockquote").innerText(), /Honestly, we didn’t know if the boats knew/);
  assert.match(await page.getByRole("main").innerText(), /2 in-water tracks.*3 labeled tracks.*2 empty openings/s);
  assert.match(await page.getByRole("main").innerText(), /track 6 in water.*Track 17 was graded on shore/is);

  const cases = [
    ["Who did Ember bring forward?", /Track 0.*Detector \+ Ember/s, /Card 4.*0:02.*3\.097 s/s, /Source frame 74.*775\.37, 902\.865/s, "ember", 4, 0, 74],
    ["Who did it leave out?", /Track 1.*Detector alone/s, /Card 5.*0:16.*17\.097 s/s, /Source frame 494.*1850\.5, 345\.4/s, "detector", 5, 1, 494],
  ];
  for (const [question, identity, opening, geometry, arm, slot, track, nativeFrame] of cases) {
    const toggle = page.getByText(question, { exact: true });
    await toggle.click();
    const evidence = toggle.locator("xpath=ancestor::details").getByRole("group", { name: "Recorded opening" });
    assert.ok(await evidence.isVisible());
    for (const expected of [identity, opening, geometry]) assert.match(await evidence.innerText(), expected);
    const slotLink = evidence.getByRole("link", { name: new RegExp(`slot ${slot} in the audit`, "i") });
    assert.equal(await slotLink.count(), 1, `Slot ${slot} audit link`);
    const offline = page.url().startsWith("file:");
    const auditBase = offline ? "https://open-water-search.vercel.app/pages/" : "";
    assert.equal(await slotLink.getAttribute("href"), `${auditBase}${auditWindow}&arm=${arm}&slot=${slot}`);
    const images = await evidence.getByRole("img").all();
    assert.equal(images.length, 2);
    for (const image of images) {
      await image.scrollIntoViewIfNeeded();
      await image.evaluate(node => node.decode());
    }
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    if (!offline) {
      await slotLink.click();
      const selection = page.locator("#opening-" + arm + "-" + slot);
      await selection.waitFor();
      const native = selection.getByText("Native frame (zero-based)", { exact: true }).locator("+ dd");
      assert.equal(await native.textContent(), String(nativeFrame));
      assert.match(await selection.innerText(), new RegExp(`Reference match.*Track ${track} · In water`, "s"));
      await page.goBack();
      assert.equal(page.url(), caseUrl);
    }
    if (await evidence.isVisible()) await toggle.click();
  }
}

async function placeCrewPin(page, matches) {
  await page.getByRole("button", { name: "I need another cue" }).click();
  const receipt = page.getByRole("list", { name: "Messages in order" });
  assert.match(await receipt.innerText(), /Boat crew → drone operator.*I need another cue/s);
  await page.getByRole("button", { name: "Send cue to boat crew" }).click();
  await page.getByRole("button", { name: "I see them" }).click();
  const frame = page.getByRole("group", { name: "Place your pin on the full frame" });
  const dimensions = await frame.boundingBox();
  const position = matches
    ? { x: dimensions.width * 0.6912, y: dimensions.height * 0.2557 }
    : { x: dimensions.width / 2, y: dimensions.height / 2 };
  if (await page.evaluate(() => navigator.maxTouchPoints > 0)) await frame.tap({ position });
  else await frame.click({ position });
  await page.getByRole("button", { name: "Send reply and pin" }).click();
  return receipt;
}

async function inspectUnavailableOpening(page) {
  const auditUrl = new URL(auditWindow, caseUrl);
  for (const query of ["arm=ember&slot=6", "arm=unknown&slot=4", "arm=ember", "slot=4"]) {
    await page.goto(`${auditUrl}&${query}`);
    const status = page.getByRole("status").filter({ hasText: "That opening is unavailable" });
    await status.waitFor({ timeout: 3000 });
    assert.match(await page.getByLabel("Recording and window").locator("option:checked").innerText(), /DJI_0804_0014_50m_2/);
    assert.equal(await page.locator("#queues button[aria-expanded=true]").count(), 0);
    const opening = page.getByRole("region", { name: "Detector + Ember", exact: true })
      .getByRole("button", { name: /^Slot 4/ });
    await opening.click();
    assert.equal(await opening.getAttribute("aria-expanded"), "true");
    assert.equal(await status.isVisible(), false);
    assert.equal(new URL(page.url()).searchParams.get("slot"), "4");
  }
}

async function openCrew(page) {
  assert.match(await page.getByRole("main").innerText(), /Simulated crew exchange · Separate recorded flight.*DJI_0915_0007_40/s);
  await page.getByRole("link", { name: "Open the 0:36 crew handoff" }).click();
  await page.getByRole("heading", { name: "You’re on the boat crew" }).waitFor();
  const crop = page.getByRole("img").nth(1);
  await crop.evaluate(node => node.decode());
  assert.match(await page.locator("footer").innerText(), /Simulated crew exchange/);
}

async function saveDownload(page, control, directory) {
  const [download] = await Promise.all([page.waitForEvent("download"), control.click()]);
  const filename = join(directory, download.suggestedFilename());
  await download.saveAs(filename);
  return filename;
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_BIN });
  const directory = await mkdtemp(join(tmpdir(), "open-water-0014-"));
  try {
    for (const [width, height, hasTouch] of [[1360, 920, false], [390, 844, true]]) {
      const context = await browser.newContext({ viewport: { width, height }, hasTouch });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.goto(caseUrl);
      await inspectCases(page);
      assert.equal(await page.getByRole("link", { name: "Open the 129-window audit" }).getAttribute("href"), "first-five.html");
      await inspectUnavailableOpening(page);
      await page.goto(caseUrl);

      const zip = await saveDownload(page, page.getByRole("link", { name: "Download offline handoff ZIP" }), directory);
      const extracted = join(directory, String(width));
      execFileSync("unzip", ["-q", zip, "-d", extracted]);
      assert.deepEqual(
        await readFile(join(extracted, "flight/crew-reply.html")),
        await readFile(join(__dirname, "../pages/flight/crew-reply.html"))
      );

      await openCrew(page);
      const confirmed = await placeCrewPin(page, true);
      assert.ok(await page.getByRole("heading", { name: "What the drone operator gets back" }).isVisible());
      assert.match(await confirmed.innerText(), /I see them.*Inside the labeled swimmer’s box/s);
      assert.match(await page.getByText("White ring: original sighting", { exact: false }).innerText(), /Amber diamond: attempt 1/);

      const offline = await browser.newContext({ offline: true, viewport: { width, height }, hasTouch });
      const packet = await offline.newPage();
      const network = [];
      packet.on("request", request => {
        if (/^https?:/.test(request.url())) network.push(request.url());
      });
      packet.on("pageerror", error => errors.push(error.message));
      await packet.goto(pathToFileURL(join(extracted, "0014.html")).href);
      await inspectCases(packet);
      await openCrew(packet);
      const unresolved = await placeCrewPin(packet, false);
      await packet.getByRole("button", { name: "Send correction" }).click();
      await packet.getByRole("button", { name: "I still don’t see them" }).click();
      assert.match(await unresolved.innerText(), /Outside the labeled swimmer’s box.*I still don’t see them/s);
      const status = packet.getByText("Sighting unresolved.", { exact: false });
      assert.ok(await status.isVisible());
      const savedReply = await saveDownload(packet, packet.getByRole("button", { name: "Download operator copy" }), extracted);
      await packet.goto(pathToFileURL(savedReply).href);
      assert.ok(await packet.getByText("Sighting unresolved.", { exact: false }).isVisible());
      assert.match(await packet.getByRole("list", { name: "Messages in order" }).innerText(), /I need another cue.*I still don’t see them/s);
      assert.deepEqual(network, []);
      assert.deepEqual(errors, []);
      await offline.close();
      await context.close();
      console.log(width + " px: recorded gain/loss, pin, unresolved reply, operator copy, and offline ZIP passed");
    }
  } finally {
    await browser.close();
    await rm(directory, { recursive: true, force: true });
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
