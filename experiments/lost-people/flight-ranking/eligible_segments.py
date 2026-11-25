"""Print eligible consecutive seconds for the hard-flight test, without reading labels."""
import json
from itertools import groupby

from rank_flights import HERE, NEAR_FRAMES, candidates, used_frames


def inventory():
    videos = json.loads((HERE / 'ranking.json').read_text())['shortlist']['videos']
    rows = json.loads((HERE / 'inputs/manifest.json').read_text())['frames']
    boxes = {row['frame']: row for row in json.loads((HERE / 'flags-005/boxes.json').read_text())}
    earlier, live = used_frames()
    segments = []
    for video in videos:
        eligible = []
        for row in rows:
            if row['video'] != video:
                continue
            frame = row['video_frame']
            if any(abs(frame - old) <= NEAR_FRAMES for old in earlier.get(video, [])):
                continue
            if video in live:
                start, end = live[video]
                if start - NEAR_FRAMES <= frame <= end + NEAR_FRAMES:
                    continue
            eligible.append((row['second'], len(candidates(boxes[row['frame']]))))
        for _, group in groupby(enumerate(sorted(eligible)), key=lambda item: item[1][0] - item[0]):
            seconds = [item for _, item in group]
            segments.append(dict(video=video, first_second=seconds[0][0], last_second=seconds[-1][0],
                                 flags=sum(n for _, n in seconds), full_window_flags=sum(n for _, n in seconds[3:-3])))
    return segments


if __name__ == '__main__':
    print(json.dumps(inventory(), indent=2))
