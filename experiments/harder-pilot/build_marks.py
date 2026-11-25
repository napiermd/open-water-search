"""Replay the frozen pilot from verdicts, refusing incomplete or duplicate model inputs."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'lost-people/flight-ranking'))
from rank_flights import link


def build(frames, verdicts):
    calls = {}
    for row in verdicts:
        key = row['arm'], row['frame'], row['i']
        if key in calls or type(row['yes']) is not bool or type(row['nearby']) is not bool:
            raise ValueError(f'Duplicate or invalid verdict: {key}')
        calls[key] = row
    expected = set()
    marks = []
    blocks = defaultdict(list)
    for frame in frames:
        blocks[frame['block']].append(frame)

    def verdict(arm, flag):
        key = arm, flag['frame'], flag['i']
        expected.add(key)
        if key not in calls:
            raise ValueError(f'Missing required verdict: {key}')
        return calls[key]

    def mark(arm, flag, when, source, restored=False):
        marks.append(dict(arm=arm, frame=flag['frame'], i=flag['i'], delivery_second=when,
                          confidence=source.get('confidence', flag['confidence']), restored=restored))

    for block in blocks.values():
        block.sort(key=lambda r: r['second'])
        first, end = block[0]['second'], block[-1]['second']
        if len(block) != end - first + 1 or len({r['video'] for r in block}) != 1:
            raise ValueError('Temporal block crosses a gap or clip boundary')
        timeline = []
        for row in block:
            second = row['second']
            flags = []
            for i, (x1, y1, x2, y2, confidence, *_) in enumerate(row['flags']):
                f = dict(frame=row['frame'], second=second, i=i, x=(x1+x2)/2, y=(y1+y2)/2, confidence=confidence)
                current = verdict('current', f)
                padded = verdict('padded', f)
                f['padded'] = padded
                mark('detector', f, second, f)
                if current['yes']:
                    mark('current', f, second, current)
                if padded['yes'] or padded['nearby']:
                    for arm in ('padded', 'vote', 'three'):
                        mark(arm, f, second, padded)
                elif first < second < end:
                    triple = verdict('three', f)
                    if triple['yes']:
                        mark('three', f, second+1, triple, restored=True)
                flags.append(f)
            timeline.append((second, flags))
        for track in link(timeline, block[0]['width']):
            for f in track:
                second = f['second']
                neighborhood = [g for g in track if abs(second - g['second']) <= 3]
                if 2 * sum(g['padded']['yes'] for g in neighborhood) <= len(neighborhood):
                    continue
                delivery = min(second+3, end)
                mark('two_way', f, delivery, f['padded'])
                if not (f['padded']['yes'] or f['padded']['nearby']):
                    mark('vote', f, delivery, f['padded'], restored=True)
    if set(calls) != expected:
        raise ValueError(f'{len(set(calls) - expected)} out-of-plan verdict(s)')
    return marks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('verdicts', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.verdicts.read_text().splitlines() if line]
    result = build(json.loads((HERE/'pilot.json').read_text()), rows)
    args.output.write_text(json.dumps(result, separators=(',', ':')) + '\n')
