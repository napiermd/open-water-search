import tempfile
import unittest
from pathlib import Path

from replay_flight import replay


class SealedFlightReplay(unittest.TestCase):
    def test_rejects_a_different_clip_before_generating_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            clip = Path(directory) / "clip.mp4"
            clip.write_bytes(b"different flight")
            out = Path(directory) / "results"

            with self.assertRaisesRegex(SystemExit, "clip SHA-256 does not match"):
                replay(clip, out)

            self.assertFalse(out.exists())
