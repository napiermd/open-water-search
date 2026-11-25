"""Score saved tile predictions and cross-check the original seven-clip detector score."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / 'harder-pilot'
ROOT = HERE.parents[1]
sys.path.insert(0, str(PILOT))
sys.path.insert(0, str(ROOT / 'probe'))
from flag_check import candidates
from score_pilot import PILOT_SHA256, found, index_marks, load_truth, score_arm


def read(path):
    return json.loads(path.read_bytes())


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score_flags(frames, truth):
    marks = [dict(arm='detector', frame=r['frame'], i=i, delivery_second=r['second'])
             for r in frames for i in range(len(r['flags']))]
    return score_arm(frames, truth, index_marks(frames, marks), 'detector')


def main():
    seal = read(HERE/'seal.json')
    assert checksum(PILOT/'pilot.json') == PILOT_SHA256
    assert checksum(HERE/'boxes.json') == seal['boxes_sha256'] and checksum(HERE/'inputs.json') == seal['inputs_sha256']
    pilot = read(PILOT/'pilot.json')
    boxes = read(HERE/'boxes.json')
    assert [r['frame'] for r in boxes] == [r['frame'] for r in pilot]
    source = ROOT/'../../data/mobdrone/annotations_person_coco_classes.json'
    assert checksum(source) == read(PILOT/'seal.json')['annotations_sha256']
    truth, _ = load_truth(pilot, read(source), read(PILOT/'exclusions.json'))
    tiled = [dict(r, flags=candidates(b)) for r,b in zip(pilot,boxes)]
    all_boxes = [dict(r, flags=sorted((b for b in photo['boxes'] if b[5]==0), key=lambda b:-b[4]))
                 for r,photo in zip(pilot,boxes)]
    whole = score_flags(pilot,truth)
    zoom = score_flags(tiled,truth)
    uncapped = score_flags(all_boxes,truth)
    metrics = ('identities','found','missed','mean_coverage','false_marks','false_mark_seconds','false_episodes')
    original = read(PILOT/'summary.json')['all']['arms']['detector']
    assert all(whole[k] == original[k] for k in metrics)
    assert {(p['video'],p['track_id']) for p in original['person_records'] if p['marked']} == set(found(whole))
    targets = [(p['video'],p['track_id']) for p in whole['people'] if not p['hits']]
    target_rows = []
    for v,t in targets:
        row = next(p for p in zoom['people'] if (p['video'],p['track_id'])==(v,t))
        target_rows.append(dict(video=v,track=t,visible=row['visible_seconds'],tiled_hits=row['hits'],
                                uncapped_hits=found(uncapped).get((v,t),{}).get('hits',[])))
    def compact(r, frames):
        return {k:r[k] for k in metrics} | dict(flags=sum(len(f['flags']) for f in frames),
                  person_seconds=sum(len(p['marked_seconds']) for p in r['people']))
    result=dict(photos=len(pilot),tiles=9*len(pilot),dollars=0,whole=compact(whole,pilot),tiled=compact(zoom,tiled),
                gained=sorted(found(zoom).keys()-found(whole).keys()),lost=sorted(found(whole).keys()-found(zoom).keys()),
                missed_targets=target_rows, by_clip={v:{name:{k:r['by_clip'][v][k] for k in metrics} for name,r in
                                                        [('whole',whole),('tiled',zoom)]} for v in whole['by_clip']})
    (HERE/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='by_clip'},indent=2))


if __name__ == '__main__':
    main()
