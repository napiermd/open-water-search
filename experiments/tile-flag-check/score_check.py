"""Replay the incremental check from public verdicts and the seven-clip scorer."""
import json
from collections import Counter
import sys

from prepare import HERE, PILOT, read, digest, select
sys.path.insert(0, str(PILOT))
from score_pilot import found, index_marks, load_truth, score_arm


def verdicts(path, frames, old=False):
    result = {}
    by_name = {r['frame']:r for r in frames}
    for line in path.read_text().splitlines():
        v = json.loads(line)
        if old and v['arm'] != 'current':
            continue
        key = v['frame'], v['i']
        assert v['arm']=='current' and key not in result and type(v['yes']) is bool
        assert v['frame'] in by_name and 0 <= v['i'] < len(by_name[v['frame']]['flags'])
        result[key] = v
    return result


def report(frames, marks, truth):
    scored = score_arm(frames, truth, index_marks(frames,marks), 'current')
    keys = ('identities','found','false_marks','false_mark_seconds','false_episodes','mean_coverage')
    summary = {k:scored[k] for k in keys}
    summary.update(kept=len(marks),true_marks=len(marks)-scored['false_marks']-scored['ignored_marks'],
                   person_seconds=sum(len(p['marked_seconds']) for p in scored['people']))
    return summary, found(scored), scored['by_clip']


def main():
    frames = read(PILOT/'pilot.json'); new = read(HERE/'inputs.json')
    assert new == select()
    pilot_seal = read(PILOT/'seal.json')
    for filename in ('summary.json','verdicts.jsonl','exclusions.json'):
        assert digest(PILOT/filename)==pilot_seal['sha256'][filename]
    annotations = HERE.parents[3]/'data/mobdrone/annotations_person_coco_classes.json'
    assert digest(annotations)==pilot_seal['annotations_sha256']
    truth,_ = load_truth(frames,read(annotations),read(PILOT/'exclusions.json'))
    old = verdicts(PILOT/'verdicts.jsonl',frames,old=True)
    extra = verdicts(HERE/'verdicts.jsonl',new)
    assert len(old) == sum(len(f['flags']) for f in frames)
    charges = read(HERE/'charges.json'); charge_by_frame={c['frame']:c for c in charges}
    assert len(charges)==len(charge_by_frame)
    expected={f['frame'] for f in new if f['flags']}
    assert set(charge_by_frame) <= expected
    for f in new:
        charge=charge_by_frame.get(f['frame'])
        usable=charge and charge['status']=='usable'
        assert sum((f['frame'],i) in extra for i in range(len(f['flags']))) == (len(f['flags']) if usable else 0)
    combined=[]; baseline=[]; add=[]; stacked=[]
    for before, more in zip(frames,new,strict=True):
        frame=before['frame']; assert frame==more['frame'];offset=len(before['flags'])
        stacked.append(dict(before,flags=before['flags']+more['flags']))
        for source,flags,shift,group in ((old,before['flags'],0,baseline),(extra,more['flags'],offset,add)):
            for i in range(len(flags)):
                v=source.get((frame,i))
                if v and v['yes']:
                    mark=dict(arm='current',frame=frame,i=i,delivery_second=before['second'],confidence=v['confidence'])
                    group.append(mark);combined.append(dict(mark,i=i+shift))
    base,base_people,bclip=report(frames,baseline,truth)
    inc,_,_=report(new,add,truth)
    merged,people,mclip=report(stacked,combined,truth)
    saved=read(PILOT/'summary.json')['all']['arms']['current']
    assert all(base[k]==saved[k] for k in ('found','false_marks','false_mark_seconds','false_episodes','mean_coverage'))
    assert {k for k in base_people} <= set(people) and merged['false_marks']-base['false_marks']==inc['false_marks']
    target=next(f for f in new if f['frame']=='DJI_0804_0012_50m_3-second-00037')
    idx=target['tile_indices'].index(3)
    target_result=extra.get((target['frame'],idx)); target_id=(target['video'],8)
    assert (target_result is not None and target_result['yes']) == (target_id in people)
    result=dict(model='muse-ember-1.0',route='Meta Model API',generation_requests=len(charges),eligible_frames=len(expected),
                eligible_flags=sum(len(r['flags']) for r in new),decided_flags=len(extra),
                usable_requests=sum(c['status']=='usable' for c in charges),nanodollars=sum(c['paid_nanodollars'] for c in charges),
                target=target_result,new_ids=sorted(set(people)-set(base_people)),baseline=base,new_flags_only=inc,combined=merged,
                by_clip={v:{k:mclip[v][k]-r[k] for k in ('found','false_marks','false_mark_seconds','false_episodes')} for v,r in bclip.items()})
    assert result['nanodollars'] <= 100_000_000
    (HERE/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='by_clip'},indent=2))


if __name__ == '__main__':
    main()
