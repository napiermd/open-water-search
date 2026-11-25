"""Rebuild both whole-frame search records with paired replacements and verify the charges."""
from collections import Counter
from contextlib import closing
import json
import sqlite3
import sys
from edge import HERE,RESERVE,read,digest,select
sys.path.insert(0,str(RESERVE))
import score_reserve as score


def save(name,value):
    (HERE/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def main():
    frozen=read(RESERVE/'seal.json')
    for name in ('summary.json','reserve.json','verdicts.jsonl','exclusions.json'):
        assert digest(RESERVE/name)==frozen['sha256'][name]
    annotations=HERE.parents[3]/'data/mobdrone/annotations_person_coco_classes.json'
    assert digest(annotations)==frozen['annotations_sha256']
    frames=read(RESERVE/'reserve.json');jobs=read(HERE/'inputs.json')
    assert jobs==select() and len(jobs)==85
    truth,_=score.load_reserve_truth(frames,read(annotations),read(RESERVE/'exclusions.json'))
    original={}
    for line in (RESERVE/'verdicts.jsonl').read_text().splitlines():
        v=json.loads(line);name=v['frame']
        if name.startswith('whole/'):
            original[name[6:],v['i']]=v
    assert len(original)==sum(len(f['flags']) for f in frames)
    new={};charges=[];rows=[];packed={f['frame']:f for f in jobs}
    with closing(sqlite3.connect((HERE/'ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        assert db.execute('select manifest,stop from settings').fetchall()==[(digest(HERE/'inputs.json'),None)]
        for arm,name,idx,reserved,paid,result in db.execute('select * from calls order by frame'):
            assert arm=='current' and name in packed and idx==-1 and paid is not None and 0<=paid<=reserved
            charge=dict(frame=name,paid_nanodollars=paid,reserved_nanodollars=reserved,usable=result is not None)
            charges.append(charge)
            if result is None:continue
            vv=json.loads(result);f=packed[name];assert sorted(v['i'] for v in vv)==list(range(len(f['flags'])))
            for v in vv:
                assert v['frame']==name and type(v['yes']) is bool
                rows.append(v);new[name,f['original_indices'][v['i']]]=v
    key=lambda v:(v['frame'],v['i']); log=[json.loads(l) for l in (HERE/'verdicts.jsonl').read_text().splitlines()];assert sorted(rows,key=key)==sorted(log,key=key)
    assert sorted(c['frame'] for c in charges)==sorted(packed)
    paid=sum(c['paid_nanodollars'] for c in charges);assert paid<=50_000_000
    baseline=[];replaced=[];flips=[]
    for f in frames:
        name=f['frame']
        for i,box in enumerate(f['flags']):
            old=original[name,i];edge=new.get((name,i));v=edge or old
            for dest,record in ((baseline,old),(replaced,v)):
                if record['yes']:dest.append(dict(arm='current',frame=name,i=i,confidence=record['confidence'],delivery_second=f['second']))
            if old['yes']==v['yes']:continue
            x,y=score.pilot.center(box);holders=[(id,b) for id,b,ignored in truth[name] if not ignored and score.pilot.contains((x,y),b)]
            flips.append(dict(frame=name,original_i=i,yes=v['yes'],on_label=bool(holders),labels=[id for id,b in holders],old_words=old['what'],new_words=v['what']))
    base,old_ids=score.measure(frames,truth,baseline);after,new_ids=score.measure(frames,truth,replaced)
    assert base==read(RESERVE/'summary.json')['totals']['all']['baseline']
    target=('DJI_0915_0015_50m-second-00136',1);target_row=next(f for f in frames if f['frame']==target[0]); point=score.pilot.center(target_row['flags'][1]); assert any(id==7 and score.pilot.contains(point,b) for id,b,_ in truth[target[0]])
    tally=Counter(('true' if r['on_label'] else 'false')+('_added' if r['yes'] else '_removed') for r in flips)
    assert after['false_marks']-base['false_marks']==tally['false_added']-tally['false_removed']
    result=dict(model='muse-ember-1.0',route='personal Meta Model API',paid_nanodollars=paid,selected=sum(len(f['flags']) for f in jobs),answered=len(new),frames_requested=len(jobs),unusable_frames=[c['frame'] for c in charges if not c['usable']],
                current=base,padded_edge_replacements=after,gained_ids=sorted(new_ids.keys()-old_ids.keys()),lost_ids=sorted(old_ids.keys()-new_ids.keys()),target=dict(frame=target[0],original_i=1,track_id=7,before=original[target],after=new.get(target)),
                recovered_track_marks=new_ids.get((target_row['video'],7),{}).get('hits',[]),transitions=dict(tally),changes=flips)
    save('charges.json',charges);save('summary.json',result);save('seal.json',{n:digest(HERE/n) for n in ('PLAN.md','inputs.json','run_edge.py','edge.py','score_edge.py','charges.json','summary.json','verdicts.jsonl')}); print(json.dumps({k:v for k,v in result.items() if k!='changes'},indent=1))


if __name__=='__main__':main()
