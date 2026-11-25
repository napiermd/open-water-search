import os
from pathlib import Path
import unittest

from replay_off_center import load_reference, score_replacements


def pin(x, description="swimmer off centre", kept=False):
    return dict(box=[x, 10, x + 4, 14], detector_confidence=0.8,
                kept=kept, description=description)


def frame(clip, second, *flags):
    return dict(frame=f"{clip}-{second}", video=f"{clip}.mp4", video_frame=second * 30,
                second=second, width=100, height=100, flags=flags)


def annotations(frames, labels):
    images = [
        dict(id=i, file_name=f"{Path(row['video']).stem}_{row['video_frame']:06}.PNG",
             width=row["width"], height=row["height"])
        for i, row in enumerate(frames)
    ]
    return dict(images=images, annotations=[
        dict(image_id=i, category_id=1, bbox=[x, 10, 4, 4], attributes={"track_id": track})
        for i, row in enumerate(frames) for x, track in labels.get(row["frame"], ())
    ])


@unittest.skipUnless(os.environ.get("OWS_RESEARCH_REPO"), "requires the pinned research checkout")
class ReplacementReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer, predicate = load_reference(Path(os.environ["OWS_RESEARCH_REPO"]).resolve())
        cls.restore = staticmethod(predicate)

    def replay(self, positive):
        empty = [frame("empty", 14, pin(60, "rock", kept=True))]
        labels = {"positive-20": [(10, 7), (30, 8), (50, None)]}
        return score_replacements({"empty": empty, "positive": positive},
                                  annotations(empty + positive, labels), self.scorer, self.restore)

    def test_a_correct_restoration_passes_with_an_existing_false_pin_and_a_set_aside_pin(self):
        result = self.replay([
            frame("positive", 20, pin(10, kept=True), pin(30), pin(50),
                  pin(70, "possible swimmer off centre"))
        ])
        self.assertEqual(result["selection"], "restore_off_center")
        self.assertEqual(result["gate"], dict(correctly_restored_pins=1, added_false_pins=0, passes=True))
        positive = result["clips"]["positive"]
        self.assertEqual(positive["restored_pins"], [
            dict(clip_second=0, flag_index=1, disposition="correct", track_id=8),
            dict(clip_second=0, flag_index=2, disposition="set_aside"),
        ])
        self.assertEqual(positive["new_tracks"], [8])
        self.assertEqual(result["combined"]["restore_off_center"]["false_episodes"], 1)

    def test_two_false_restorations_in_one_episode_block_a_correct_restoration(self):
        result = self.replay([
            frame("positive", 20, pin(10, kept=True), pin(30)),
            frame("positive", 21, pin(30)),
            frame("positive", 22, pin(30)),
        ])
        self.assertEqual(result["selection"], "current")
        self.assertEqual(result["gate"], dict(correctly_restored_pins=1, added_false_pins=2, passes=False))
        positive = result["clips"]["positive"]
        self.assertEqual(positive["restored_pins"], [
            dict(clip_second=0, flag_index=1, disposition="correct", track_id=8),
            dict(clip_second=1, flag_index=0, disposition="false"),
            dict(clip_second=2, flag_index=0, disposition="false"),
        ])
        self.assertEqual(positive["restore_off_center"]["false_episodes"], 1)


if __name__ == "__main__":
    unittest.main()
