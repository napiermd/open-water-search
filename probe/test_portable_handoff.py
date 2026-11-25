"""The public crew packets must remain readable offline and point at the recorded sighting."""
import base64
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest

from export_handoff import data_uri

ROOT = Path(__file__).resolve().parents[1]


class Packet(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.images.append(dict(attrs)["src"])


class PortableHandoffTest(unittest.TestCase):
    def test_every_published_packet_embeds_its_actual_crop_and_full_frame(self):
        folder = ROOT / "pages/flight"
        cases = json.loads((folder / "record.json").read_text())["handoffs"]
        sealed = json.loads((ROOT / "runs/live-detector-check/search-record-redacted.json").read_text())
        self.assertEqual(len(cases), len(sealed["possible_people"]))
        for item, person in zip(cases, sealed["possible_people"], strict=True):
            self.assertEqual(item["pin"], [person["position"]["x"], person["position"]["y"]])
            self.assertEqual(item["handoff"], person["handoff_message"])
            packet = Packet()
            packet.feed((folder / item["packet"]).read_text())
            self.assertEqual(len(packet.images), 2)
            for url in packet.images:
                self.assertTrue(url.startswith("data:image/jpeg;base64,"))
            self.assertEqual(base64.b64decode(packet.images[1].split(",")[1]), (folder / item["crop"]).read_bytes())

    def test_packet_images_must_stay_inside_the_flight(self):
        with self.assertRaises(ValueError):
            data_uri(ROOT / "pages", "../README.md")

    def test_reported_first_five_reconcile_including_short_queues(self):
        result = json.loads((ROOT / "experiments/first-five/result.json").read_text())
        self.assertEqual(sum(c["labeled"] for c in result["primary"]), 7)
        for mode in ("ember", "detector"):
            for case in [*result["primary"], result["flight"]]:
                arm = case[mode]
                self.assertEqual(arm["opened"], min(arm["available"], 5))
                self.assertEqual(arm["opened"], sum(arm[k] for k in ("new","repeat","empty","unidentified")))
                self.assertEqual(arm["opened"], len(arm["outcomes"]))
            for key, total in result["totals"][mode].items():
                self.assertEqual(total, sum(case[mode][key] for case in result["primary"]))
