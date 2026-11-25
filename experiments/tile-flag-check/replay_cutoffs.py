"""Replay incremental tile yes answers at every distinct saved Ember confidence."""
import json

from score_check import HERE, PILOT, digest, load_truth, read, report, verdicts


def main():
    for folder in (HERE, PILOT):
        seal = read(folder/'seal.json')
        for name, expected in seal.get('sha256', seal).items():
            assert digest(folder/name) == expected, name
    frames = read(PILOT/'pilot.json')
    new = read(HERE/'inputs.json')
    old_votes = verdicts(PILOT/'verdicts.jsonl', frames, old=True)
    more_votes = verdicts(HERE/'verdicts.jsonl', new)
    annotations = HERE.parents[3]/'data/mobdrone/annotations_person_coco_classes.json'
    assert digest(annotations) == read(PILOT/'seal.json')['annotations_sha256']
    truth, _ = load_truth(frames, read(annotations), read(PILOT/'exclusions.json'))
    original = read(HERE/'summary.json')
    target = original['target']
    stacked, baseline, additions = [], [], []
    target_mark = None
    for old, tile in zip(frames, new, strict=True):
        name = old['frame']
        assert name == tile['frame']
        offset = len(old['flags'])
        stacked.append(dict(old, flags=old['flags'] + tile['flags']))
        for votes, row, start, dest in ((old_votes,old,0,baseline), (more_votes,tile,offset,additions)):
            for i in range(len(row['flags'])):
                v = votes[name,i]
                if v['yes']:
                    mark = dict(arm='current', frame=name, i=start+i, confidence=v['confidence'], delivery_second=old['second'])
                    dest.append(mark)
                    if dest is additions and (name,i)==(target['frame'],target['i']):
                        target_mark = mark
    assert target_mark is not None and target_mark['confidence']==target['confidence']
    base, _, _ = report(stacked,baseline,truth)
    assert base==original['baseline']
    thresholds = {0, 1} | {m['confidence'] for m in additions}
    rows=[]
    for cutoff in sorted(thresholds):
        kept=[m for m in additions if m['confidence']>=cutoff]
        summary, _, _ = report(stacked,baseline+kept,truth)
        if cutoff==0:
            assert summary==original['combined']
        rows.append(dict(cutoff=cutoff, paddler=target_mark in kept, tile_marks=len(kept),
                         tracks=summary['found'], false_episodes=summary['false_episodes'],
                         extra_episodes=summary['false_episodes']-base['false_episodes'],
                         extra_false_marks=summary['false_marks']-base['false_marks'],
                         added_person_seconds=summary['person_seconds']-base['person_seconds']))
    (HERE/'cutoff-sweep.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('cutoff  paddler  tile-marks  tracks  total-episodes  extra-episodes  extra-false-marks  extra-person-seconds')
    for row in rows:
        print(*row.values())


if __name__=='__main__':
    main()
