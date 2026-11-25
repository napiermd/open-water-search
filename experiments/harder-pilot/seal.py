"""Seal completed pilot decisions, request charges and a report without source pictures."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

from build_marks import build
from score_pilot import HERE, PILOT_SHA256, ROOT, load_truth, score


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    pilot = HERE/'pilot.json'
    if digest(pilot) != PILOT_SHA256:
        raise ValueError('Pilot manifest mismatch')
    frames = json.loads(pilot.read_bytes())
    verdicts = [json.loads(line) for line in (HERE/'verdicts.jsonl').read_text().splitlines()]
    marks = build(frames, verdicts)
    path = ROOT / '../../data/mobdrone/annotations_person_coco_classes.json'
    truth, audit = load_truth(frames, json.loads(path.read_bytes()), json.loads((HERE/'exclusions.json').read_bytes()))
    db = sqlite3.connect((HERE/'ledger.sqlite').resolve().as_uri()+'?mode=ro', uri=True)
    try:
        manifest, stopped = db.execute('select manifest,stop from settings').fetchone()
        if stopped or manifest != PILOT_SHA256:
            raise ValueError('Ledger stopped or attached to different manifest')
        calls = []
        cost = Counter()
        restored_rows = []
        for arm, frame, index, reserved, paid, rows in db.execute('select * from calls order by arm,frame,i'):
            if paid is None or not 0 <= paid <= reserved or rows is None:
                raise ValueError('Unsettled charge or incomplete response')
            restored_rows.extend(json.loads(rows))
            calls.append(dict(arm=arm, frame=frame, i=index, reserved_nanodollars=reserved, paid_nanodollars=paid))
            cost[arm] += paid
        order = lambda r: (r['arm'],r['frame'],r['i'])
        if sorted(verdicts,key=order) != sorted(restored_rows,key=order) or sum(cost.values()) > 150_000_000:
            raise ValueError('Ledger and exported verdicts disagree, or pilot exceeded ceiling')
    finally:
        db.close()
    result = score(frames, truth, marks, complete=True)
    summary = dict(model='muse-ember-1.0', route='Meta Model API', track_audit=audit,
                   calls_by_arm=dict(Counter(c['arm'] for c in calls)), cost_nanodollars=dict(cost),
                   total_nanodollars=sum(cost.values()), verdicts_by_arm=dict(Counter(v['arm'] for v in verdicts)),
                   decision=result['decision'])
    for subset in ('all','full_window'):
        row = result[subset]
        summary[subset] = dict(seconds=row['seconds'], arms={})
        for arm, metrics in row['arms'].items():
            compact = {k:v for k,v in metrics.items() if k not in ('people','by_clip')}
            compact['by_clip'] = {clip:{k:v for k,v in m.items() if k!='blocks'} for clip,m in metrics['by_clip'].items()}
            compact['person_records'] = [dict(video=p['video'], track_id=p['track_id'], visible=len(p['visible_seconds']),
                                             marked=len(p['marked_seconds']), first_alert_delay=p['first_alert_delay'])
                                         for p in metrics['people']]
            summary[subset]['arms'][arm] = compact
        summary[subset]['comparisons'] = {arm:{control:{change:[dict(video=p['video'],track_id=p['track_id'],hits=p['hits'])
                                                                  for p in people] for change,people in diff.items()}
                                              for control,diff in comparisons.items()} for arm,comparisons in row['comparisons'].items()}
    save('charges.json',calls)
    save('summary.json',summary)
    names=('PLAN.md','pilot.json','audit.md','exclusions.json','verdicts.jsonl','charges.json','summary.json',
           'run_pilot.py','build_marks.py','score_pilot.py','seal.py')
    save('seal.json',dict(sha256={name:digest(HERE/name) for name in names},annotations_sha256=digest(path)))
    print(summary['decision'], summary['total_nanodollars'])


if __name__ == '__main__':
    main()
