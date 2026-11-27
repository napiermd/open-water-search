"""Exercise the downloaded kit at the replay-to-audit seam approved in #55."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile


PUBLIC = Path(__file__).resolve().parents[2] / "pages" / "first-five"


class DownloadedAudit(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.directory = Path(folder.name)
        with ZipFile(PUBLIC / "audit.zip") as archive:
            archive.extractall(self.directory)
        self.replay = self.directory / "replay.json"

    def verify(self):
        return subprocess.run(
            [sys.executable, "-I", "verify.py"],
            cwd=self.directory, capture_output=True, text=True,
        )

    def test_download_verifies_public_replay_and_reproduces_sealed_result(self):
        self.assertEqual(self.replay.read_bytes(), (PUBLIC / "replay.json").read_bytes())
        completed = self.verify()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual((result["windows"], result["families"], result["openings"]), (129, 42, 838))
        self.assertEqual(result["paired_in_water"], {
            "both": 176, "ember_only": 23, "detector_only": 4, "neither": 26,
        })
        for arm, values in {"ember": (199, 121, 76, 2), "detector": (180, 185, 73, 2)}.items():
            self.assertEqual(result["arms"][arm], dict(zip(
                ("in_water_reached", "empty_openings", "repeat_openings", "identity_switches"),
                values,
            )))
        for name, published in {
            "reach_gain_pp": (+8.3, +3.6694450660102937, +13.274336283185841),
            "empty_reduction_pct": (34.6, 25.925505050505052, 44.09448818897638),
        }.items():
            metric = result["metrics"][name]
            self.assertAlmostEqual(metric["estimate"], published[0], places=1)
            for actual, expected in zip(metric["interval_95"], published[1:]):
                self.assertAlmostEqual(actual, expected, places=10)


    def test_flight_0014_preserves_gain_loss_and_shore_grade(self):
        windows = json.loads(self.replay.read_bytes())["windows"]
        case = next(window for window in windows
                    if window["video"] == "DJI_0804_0014_50m_2.mp4" and window["start"] == 0)
        self.assertEqual(case["settings"]["17"], "On shore")
        self.assertEqual([card["track"] for card in case["arms"]["ember"]], [None, 17, 6, 0, None])
        self.assertEqual([card["track"] for card in case["arms"]["detector"]], [None, None, 6, 17, 1])

    def test_wrong_pin_source_frame_clock_or_order_fails_with_same_totals(self):
        original = self.replay.read_bytes()
        mutations = {
            "pin": lambda cards: cards[0].update(x=cards[0]["x"] + 1),
            "source frame": lambda cards: cards[0].update(second=cards[0]["second"] + 1),
            "dispatch clock": lambda cards: cards[0].update(time=cards[0]["time"] + 0.000001),
            "order": lambda cards: cards.reverse(),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                data = json.loads(original)
                window = next(window for window in data["windows"] if len(window["arms"]["detector"]) >= 2)
                mutate(window["arms"]["detector"])
                self.replay.write_text(json.dumps(data), encoding="utf-8")
                completed = self.verify()
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn(f"Sealed opening mismatch: {window['video']} @ {window['start']}s / detector / slot 1",
                              completed.stderr)

    def test_recomputed_commitment_cannot_bless_a_different_pin(self):
        data = json.loads(self.replay.read_bytes())
        index = next(i for i, window in enumerate(data["windows"]) if window["arms"]["ember"])
        window = data["windows"][index]
        opening = window["arms"]["ember"][0]
        opening["x"] += 1
        self.replay.write_text(json.dumps(data), encoding="utf-8")
        values = [window["video"], window["start"], "ember", 1, opening["second"], opening["x"],
                  opening["y"], opening["time"], opening["identity"], opening["checked"], opening["track"],
                  opening["identity_switches"]]
        reference_path = self.directory / "sealed-reference.json"
        reference = json.loads(reference_path.read_bytes())
        encoded = json.dumps(values, separators=(",", ":")).encode()
        reference["windows"][index]["arms"]["ember"][0] = sha256(encoded).hexdigest()
        reference_path.write_text(json.dumps(reference, separators=(",", ":")) + "\n", encoding="utf-8")
        completed = self.verify()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Sealed reference checksum mismatch", completed.stderr)


if __name__ == "__main__":
    unittest.main()
