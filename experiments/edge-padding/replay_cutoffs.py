"""Offline sweep of inclusive Ember confidence thresholds on padded edge yeses only."""
import json
from edge import HERE, RESERVE, digest, read, select
from score_edge import score


def answers(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    for name, sha in read(HERE/'seal.json').items():
        assert digest(HERE/name) == sha, name
    seal = read(RESERVE/'seal.json')
    for name in ('reserve.json', 'verdicts.jsonl', 'exclusions.json'):
        assert digest(RESERVE/name) == seal['sha256'][name], name
    frames = read(RESERVE/'reserve.json')
    jobs = read(HERE/'inputs.json')
    assert jobs == select()
    indices = {r['frame']:r['original_indices'] for r in jobs}
    original = {(v['frame'].removeprefix('whole/'), v['i']):v for v in answers(RESERVE/'verdicts.jsonl') if v['frame'].startswith('whole/')}
    edge = {(v['frame'], indices[v['frame']][v['i']]):v for v in answers(HERE/'verdicts.jsonl')}
    assert len(original)==sum(len(r['flags']) for r in frames)
    assert set(edge)=={(name,i) for name, ids in indices.items() for i in ids}
    annotations = HERE.parents[3]/'data/mobdrone/annotations_person_coco_classes.json'
    assert digest(annotations) == seal['annotations_sha256']
    truth, _ = score.load_reserve_truth(frames, read(annotations), read(RESERVE/'exclusions.json'))
    old_marks, fixed, variable = [], [], []
    background = set()
    for f in frames:
        name = f['frame']
        for i in range(len(f['flags'])):
            key = name,i
            old = original[key]; v = edge.get(key,old)
            if key in edge:
                point=score.pilot.center(f['flags'][i])
                if not any(score.pilot.contains(point,box) for _,box,_ in truth[name]):
                    background.add(key)
            mark = dict(arm='current', frame=name, i=i, delivery_second=f['second'])
            if old['yes']:
                old_marks.append(dict(mark,confidence=old['confidence']))
            if v['yes']:
                (variable if key in edge else fixed).append(dict(mark,confidence=v['confidence']))
    base, _ = score.measure(frames,truth,old_marks)
    saved=read(HERE/'summary.json'); assert base==saved['current']
    target=saved['target']; key=target['frame'],target['original_i']; assert edge[key]==target['after']
    output=[]
    for cutoff in sorted({0,1}|{m['confidence'] for m in variable}):
        kept=[m for m in variable if m['confidence']>=cutoff]
        metrics,people = score.measure(frames,truth,fixed+kept)
        if cutoff==0: assert metrics==saved['padded_edge_replacements']
        swimmer=people.get(('DJI_0915_0015_50m.mp4',7),{})
        target_seen=any((m['frame'],m['i'])==key for m in swimmer.get('hits',[]))
        assert target_seen==(edge[key]['yes'] and edge[key]['confidence']>=cutoff)
        previously_false={key for key in background if original[key]['yes']}
        now_false={key for key in background if edge[key]['yes'] and edge[key]['confidence']>=cutoff}
        assert len(now_false)-len(previously_false)==metrics['false_marks']-base['false_marks']
        output.append(dict(false_marks_added=len(now_false-previously_false),false_marks_removed=len(previously_false-now_false),cutoff=cutoff,target_at_136=target_seen,target_seconds=swimmer.get('marked_seconds',[]),
                           edge_marks_kept=len(kept),tracks=metrics['found'],person_seconds=metrics['person_seconds'],
                           false_marks=metrics['false_marks'],false_mark_seconds=metrics['false_mark_seconds'],
                           episodes=metrics['false_episodes'],net_extra_episodes=metrics['false_episodes']-base['false_episodes']))
    (HERE/'cutoff-sweep.json').write_text(json.dumps(dict(original=base,cutoffs=output),indent=2)+'\n')
    for r in output: print(r['cutoff'],r['target_at_136'],r['target_seconds'],r['tracks'],r['person_seconds'],r['false_marks'],r['episodes'],r['net_extra_episodes'])


if __name__=='__main__': main()
