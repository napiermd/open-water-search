import unittest

import score_pilot as s


VIDEO, OTHER = sorted(s.VIDEOS)[:2]


def frame(second, block="b", video=VIDEO, flags=None):
    return dict(video=video, second=second, video_frame=second * 30, width=100, height=100,
                frame=f"{video}-{second}", block=block,
                flags=flags if flags is not None else [[0, 0, 2, 2, .5], [60, 60, 62, 62, .3]])


def mark(f, i, arm="current", delay=0, **extra):
    return dict(arm=arm, frame=f["frame"], i=i, delivery_second=f["second"] + delay, **extra)


def score_arm(frames, truth, marks):
    return s.score_arm(frames, truth, s.index_marks(frames, marks), "current")


class PilotScorerTests(unittest.TestCase):
    def test_coco_join_ignores_reserve_and_keeps_zero_id(self):
        f = frame(1)
        image = dict(file_name=VIDEO[:-4] + "_000030.PNG", id=9, width=100, height=100)
        box = dict(image_id=9, category_id=1, bbox=[2, 3, 4, 5])
        coco = dict(images=[image, dict(file_name="reserve", id=8)],
                    annotations=[dict(image_id=8), dict(box, attributes={"track_id": 0}), box])
        exclusion = dict(video=VIDEO, second=1, track_id=0)
        truth, audit = s.load_truth([f], coco, [exclusion])
        self.assertEqual([(0, (2, 3, 6, 8), True), (None, (2, 3, 6, 8), True)], truth[f["frame"]])
        self.assertEqual((1, 1), (audit["missing_track_boxes"], audit["land_boxes"]))
        with self.assertRaisesRegex(ValueError, "Unmatched"):
            s.load_truth([f], coco, [dict(exclusion, second=2)])
        coco["annotations"].append(dict(box, attributes={"track_id": 0}))
        with self.assertRaisesRegex(ValueError, "duplicate track"):
            s.load_truth([f], coco, [])

    def test_identity_scope_overlap_duplicate_hits_and_delivery(self):
        a, b, c = frame(1), frame(2), frame(1, video=OTHER)
        a["flags"].append(a["flags"][0])
        labels = [(4, (0, 0, 10, 10), False), (3, (0, 0, 2, 2), False)]
        truth = {a["frame"]: labels, b["frame"]: [labels[1]], c["frame"]: [labels[1]]}
        report = score_arm([a, b, c], truth, [mark(a, 0, delay=3), mark(a, 2, delay=3), mark(b, 0)])
        self.assertEqual((3, 1, 0), (report["identities"], report["found"], report["false_marks"]))
        self.assertAlmostEqual(1/3, report["mean_coverage"])
        self.assertEqual(1, report["median_first_alert_delay"])
        self.assertEqual([1, 2], next(p["marked_seconds"] for p in report["people"] if p["hits"]))

    def test_separate_episode_and_false_second_counts_and_rates(self):
        frames = [frame(0), frame(1), frame(2), frame(4, "next"), frame(0, video=OTHER)]
        truth = {f["frame"]: [] for f in frames}
        a, _, c, d, e = frames
        marks = [mark(a, 0), mark(a, 1), mark(c, 0, delay=2), mark(d, 0), mark(e, 0)]
        r = score_arm(frames, truth, marks)
        self.assertEqual((5, 4, 4), (r["false_marks"], r["false_mark_seconds"], r["false_episodes"]))
        self.assertEqual(45, r["by_clip"][VIDEO]["false_episodes_per_minute"])
        self.assertEqual(2, r["by_clip"][VIDEO]["blocks"]["b"]["false_episodes"])

    def test_legacy_uses_mark_confidence_and_independent_five_cap(self):
        f = frame(0, flags=[[0, 0, 2, 2, .9]] * 5 + [[60, 60, 62, 62, .1]])
        truth = {f["frame"]: [(0, (60, 60, 62, 62), False), (None, (0, 0, 2, 2), True)]}
        marks = [mark(f, i, confidence=1 if i == 5 else .5) for i in range(6)]
        r = score_arm([f], truth, marks)
        self.assertEqual((1, 5, 0), (r["found"], r["ignored_marks"], r["false_marks"]))
        self.assertEqual(dict(appearances=2, found=2, missed=0, unmatched=3), r["legacy_five"])

    def test_full_window_does_not_cross_blocks(self):
        frames = [frame(i, block="first" if i < 8 else "next") for i in range(12)]
        self.assertEqual([3, 4], [f["second"] for f in s.full_window(frames)])

    def test_incomplete_and_invalid_marks(self):
        f = frame(0)
        truth = {f["frame"]: []}
        self.assertIsNone(s.score([f], truth, [])["decision"]["numerical_selection"])
        with self.assertRaisesRegex(ValueError, "missing detector"):
            s.score([f], truth, [], complete=True)
        for bad in ([mark(f, -1)], [mark(f, 0, delay=-1)], [mark(f, 0)] * 2):
            with self.assertRaises(ValueError):
                s.index_marks([f], bad)

    def test_union_controls_false_gate_precedence_and_secondary(self):
        frames = [frame(i) for i in range(2)]
        truth = {f["frame"]: [(0, (0, 0, 2, 2), False), (1, (60, 60, 62, 62), False)] for f in frames}
        a, b = frames
        marks = [mark(f, i, "detector") for f in frames for i in (0, 1)]
        marks.extend(mark(a, 0, arm) for arm in ("current", "padded", "vote", "three"))
        marks.extend([mark(b, 0, "vote"), mark(b, 1, "three"), mark(b, 1, "two_way")])
        r = s.score(frames, truth, marks, complete=True)
        self.assertEqual("three", r["decision"]["numerical_selection"])
        self.assertTrue(r["decision"]["arms"]["vote"]["passes"])
        self.assertEqual(1, r["decision"]["arms"]["three"]["genuinely_new_ids"])
        r = s.score(frames, truth, marks + [mark(a, 1, "current")], complete=True)
        self.assertFalse(r["decision"]["arms"]["vote"]["gates"]["retained_control_union"])
        self.assertFalse(r["decision"]["arms"]["three"]["passes"])
        self.assertEqual("current", r["decision"]["numerical_selection"])
        self.assertEqual([1], [p["track_id"] for p in r["all"]["comparisons"]["vote"]["current"]["lost"]])
        b["flags"].append([90, 90, 92, 92, .5])
        r = s.score(frames, truth, marks + [mark(b, 2, "three"), mark(b, 2, "detector")], complete=True)
        self.assertEqual("vote", r["decision"]["numerical_selection"])
        self.assertEqual({VIDEO: {"false_mark_seconds": 1, "false_episodes": 1}},
                         r["decision"]["arms"]["three"]["false_increases"])

    def test_exact_five_percent_and_complementary_controls(self):
        frames = [frame(i) for i in range(10)]
        truth = {f["frame"]: [(0, (0, 0, 2, 2), False), (1, (60, 60, 62, 62), False)] for f in frames}
        a, b = frames[:2]
        marks = [mark(f, i, "detector") for f in frames for i in (0, 1)]
        marks += [mark(a, 0, "padded"), mark(a, 1, "current"), mark(a, 0, "vote"),
                  mark(b, 1, "vote"), mark(a, 0, "three"), mark(b, 1, "three")]
        r = s.score(frames, truth, marks, complete=True)["decision"]
        self.assertTrue(r["arms"]["vote"]["passes"])
        self.assertEqual(1, r["arms"]["three"]["count_above_best_single"])
        self.assertEqual(0, r["arms"]["three"]["genuinely_new_ids"])


if __name__ == "__main__":
    unittest.main()
