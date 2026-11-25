"""Select new swimmer boxes from the sealed tiled run, without reading labels."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / 'harder-pilot'
TILES = HERE.parent / 'seven-clip-tiles'
sys.path.insert(0, str(HERE.parents[1] / 'probe'))
from flag_check import candidates


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iou(a, b):
    width = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = width * height
    return intersection / ((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection)


def select():
    assert digest(PILOT/'pilot.json') == '6b584a523df6c298a38bb8fa147aaeedffcc58d974eb3e8cd51d4239c305fe22'
    assert digest(TILES/'boxes.json') == '86415f08d20912fd9c4c43193f12e7567972d9d0d895d8795a427718d5e40051'
    frames = []
    for f, tile in zip(read(PILOT/'pilot.json'), read(TILES/'boxes.json'), strict=True):
        assert f['frame'] == tile['frame']
        ranked = candidates(tile)
        indices = [i for i, box in enumerate(ranked) if all(iou(box, old) < .5 for old in f['flags'])]
        frames.append(dict(f, flags=[ranked[i] for i in indices], tile_indices=indices))
    return frames


if __name__ == '__main__':
    frames = select()
    (HERE/'inputs.json').write_text(json.dumps(frames, separators=(',', ':'))+'\n')
    print(len(frames), sum(bool(r['flags']) for r in frames), sum(len(r['flags']) for r in frames), digest(HERE/'inputs.json'))
    print(next(r['tile_indices'] for r in frames if r['frame']=='DJI_0804_0012_50m_3-second-00037'))
