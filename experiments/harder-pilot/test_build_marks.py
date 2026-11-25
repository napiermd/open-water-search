import unittest

from build_marks import build


class Replay(unittest.TestCase):
    def setUp(self):
        self.frames = [dict(frame=str(i), video='v', second=i, block='v/0' if i < 3 else 'v/3',
                            width=100, flags=[[8, 8, 12, 12, .9]]) for i in range(4)]
        self.calls = [dict(arm=arm, frame=str(i), i=0, nearby=False, yes=i in (0, 2))
                      for arm in ('current', 'padded') for i in range(4)]
        self.calls.append(dict(arm='three', frame='1', i=0, nearby=False, yes=True))

    def test_restoration_and_boundaries(self):
        restored = [(m['arm'], m['frame'], m['delivery_second']) for m in build(self.frames, self.calls) if m['restored']]
        self.assertCountEqual(restored, [('three', '1', 2), ('vote', '1', 2)])

    def test_missing_followup(self):
        with self.assertRaises(ValueError):
            build(self.frames, self.calls[:-1])

    def test_nearby_cannot_restore_neighbor(self):
        self.calls[4].update(yes=False, nearby=True)
        self.assertFalse(any(m['arm']=='vote' and m['restored'] for m in build(self.frames, self.calls)))


if __name__ == '__main__':
    unittest.main()
