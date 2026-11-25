"""Freeze the approved seven MOBDrone clips' eligible seconds and verify their pictures."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RANK = ROOT / 'experiments/lost-people/flight-ranking'
sys.path.insert(0, str(ROOT / 'probe'))
from flag_check import candidates

VIDEOS = {f'DJI_{name}.mp4' for name in (
    '0804_0009_40m', '0804_0010_60m', '0804_0012_50m_3', '0804_0017_40m',
    '0804_0018_40m', '0915_0003_50m', '0915_0018_60m')}


def main():
    rows = {(r['video'], r['second']): r for r in json.loads((RANK / 'inputs/manifest.json').read_text())['frames'] if r['video'] in VIDEOS}
    boxes = {r['frame']: r for r in json.loads((RANK / 'flags-005/boxes.json').read_text()) if r['frame'].split('-second-')[0] + '.mp4' in VIDEOS}
    pilot = []
    for block in json.loads((RANK / 'eligible-segments.json').read_text()):
        video = block['video']
        if video not in VIDEOS:
            continue
        start = block['first_second']
        for second in range(start, block['last_second'] + 1):
            row = rows[video, second]
            path = RANK / 'inputs' / row['image']
            if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError(f'Changed source frame: {path}')
            pilot.append(dict(row, block=f'{video}/{start}', flags=candidates(boxes[row['frame']])))
    pilot.sort(key=lambda r: (r['video'], r['second']))
    assert len(pilot) == 254 and len({r['block'] for r in pilot}) == 50
    assert sum(len(r['flags']) for r in pilot) == 603
    (HERE / 'pilot.json').write_text(json.dumps(pilot, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
