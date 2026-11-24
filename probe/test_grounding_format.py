"""#4: close looks can use Meta's grounding format, with structured output forcing marks into a JSON schema.

    python3 -m unittest discover -s probe
"""
import base64
import hashlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from runner import LIMIT, NANO, ROOT, price
from simulated_ember import INPUT_TOKENS, SimulatedEmber, run_command, write_flight


def marks(*points):
    """A schema-shaped close-look answer: points on the 0-1,000 grid of the image Ember received."""
    return json.dumps({"points": [dict(x=x, y=y, confidence=confidence) for x, y, confidence in points]})


def prompt_and_image(request):
    """The prompt's SHA-256 and the size of the image in one request body."""
    content = request["input"][0]["content"]
    prompt = next(part["text"] for part in content if part["type"] == "input_text")
    url = next(part["image_url"] for part in content if part["type"] == "input_image")
    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as image:
        return hashlib.sha256(prompt.encode()).hexdigest(), image.size


class GroundingFormat(unittest.TestCase):
    """One frame per test. Its overview ranks a single tile, which then gets the one close look."""

    def search(self, size, tile, close_look, *options):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        flight = write_flight(Path(folder.name) / "flight", [size])
        out = Path(folder.name) / "results"
        ember = SimulatedEmber({("frame-01", -1): json.dumps({"tiles": [tile]}), ("frame-01", tile): close_look})
        status, _ = run_command([str(flight), "--out", str(out), "--looks", "1", *options], ember)
        self.assertEqual(status, 0)
        return json.loads((out / "search-record.json").read_text()), ember.requests

    def test_a_close_look_asks_for_schema_shaped_marks_and_stores_them_in_frame_pixels(self):
        # Tile 4 of a 300 x 200 frame spans x 100-200 and y 66-133.
        record, requests = self.search((300, 200), 4, marks((250, 750, 0.8)), "--format", "grounding")
        self.assertEqual(requests[1]["text"]["format"]["type"], "json_schema")
        sighting = record["sightings"][0]
        self.assertEqual((sighting["tile"], sighting["x"], sighting["y"], sighting["confidence"]), (4, 125, 116.25, 0.8))
        self.assertEqual(record["settings"]["format"], "grounding")

    def test_points_just_outside_the_grid_are_clamped_to_the_edge_of_the_tile(self):
        # Tile 8 of a 300 x 200 frame spans x 200-300 and y 133-200. A point on the far edge stays inside the frame.
        record, _ = self.search((300, 200), 8, marks((1003, -2, 0.6)), "--format", "grounding")
        sighting = record["sightings"][0]
        self.assertEqual(sighting["y"], 133)
        self.assertAlmostEqual(sighting["x"], 300)
        self.assertLess(sighting["x"], 300)

    def test_points_map_back_to_original_frame_pixels_through_the_resize_ember_received(self):
        # Tile 4 of a 3840 x 2160 frame spans x 1280-2560 and y 720-1440, and reaches Ember shrunk to 1000 x 563.
        record, requests = self.search((3840, 2160), 4, marks((500, 250, 0.7)), "--format", "grounding")
        self.assertEqual(prompt_and_image(requests[1])[1], (1000, 563))
        sighting = record["sightings"][0]
        self.assertEqual((sighting["x"], sighting["y"]), (1920, 900))

    def test_an_answer_that_does_not_match_the_schema_leaves_the_tile_unreadable(self):
        for answer in ['{"points":[[0.5,0.5,0.9]]}', marks((500, 500, 1.4)), "[]"]:
            with self.subTest(answer=answer):
                record, _ = self.search((300, 200), 4, answer, "--format", "grounding")
                self.assertEqual(record["coverage_timeline"][0]["tiles"][4]["status"], "unreadable")
                self.assertEqual(record["sightings"], [])

    def test_the_grounding_format_is_the_default(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        flight = write_flight(Path(folder.name) / "flight", [(300, 200)])
        out = Path(folder.name) / "results"
        ember = SimulatedEmber({("frame-01", -1): json.dumps({"tiles": [4]}), ("frame-01", 4): marks((500, 500, 0.9))})
        status, _ = run_command([str(flight), "--out", str(out), "--looks", "1"], ember, as_given=True)
        self.assertEqual(status, 0)
        record = json.loads((out / "search-record.json").read_text())
        self.assertEqual(record["settings"]["format"], "grounding")
        self.assertEqual(ember.requests[1]["text"]["format"]["type"], "json_schema")

    def test_the_frozen_format_sends_only_the_sealed_frozen_prompts_without_a_schema(self):
        sealed = json.loads((ROOT / "live" / "settings.json").read_text())
        record, requests = self.search((300, 200), 4, '{"points":[[0.5,0.5,0.9]]}', "--format", "frozen")
        self.assertEqual([prompt_and_image(request)[0] for request in requests],
                         [sealed["overview_prompt_sha256"], sealed["close_look_prompt_sha256"]])
        self.assertFalse(any("text" in request for request in requests))
        self.assertEqual(record["settings"]["format"], "frozen")
        sighting = record["sightings"][0]
        self.assertEqual((sighting["x"], sighting["y"]), (150, 99.5))

    def test_the_grounding_format_keeps_the_frozen_overview(self):
        sealed = json.loads((ROOT / "live" / "settings.json").read_text())
        _, requests = self.search((300, 200), 4, marks(), "--format", "grounding")
        self.assertEqual(prompt_and_image(requests[0])[0], sealed["overview_prompt_sha256"])
        self.assertNotIn("text", requests[0])


    def test_the_spending_cap_counts_the_schema_that_metas_token_count_leaves_out(self):
        # A budget with room for exactly one frozen close look after the overview has no room for the schema too.
        frozen, _ = self.search((300, 200), 4, '{"points":[[0.5,0.5,0.9]]}')
        overview = frozen["calls"][0]["paid_nanodollars"]
        room = overview + price(INPUT_TOKENS, 0, LIMIT)
        budget = f"{room / NANO:.9f}"
        self.assertEqual(round(float(budget) * NANO), room)
        within, _ = self.search((300, 200), 4, '{"points":[[0.5,0.5,0.9]]}', "--budget", budget)
        self.assertEqual(within["ending"]["outcome"], "finished")
        grounded, requests = self.search((300, 200), 4, marks((500, 500, 0.9)), "--format", "grounding", "--budget", budget)
        self.assertEqual(grounded["ending"]["outcome"], "spending cap")
        self.assertEqual(len(requests), 1)


if __name__ == "__main__":
    unittest.main()
