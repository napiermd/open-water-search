"""Verify the completed local ledger and export per-request charges without credentials."""
import json
import sqlite3
from contextlib import closing

from prepare import HERE, digest, read
import score_check


def main():
    uri=(HERE/'ledger.sqlite').resolve().as_uri()+'?mode=ro'
    with closing(sqlite3.connect(uri,uri=True)) as db:
        manifest, stop=db.execute('select manifest,stop from settings').fetchone()
        if stop or manifest != digest(HERE/'inputs.json'):
            raise ValueError('Ledger stopped or input changed')
        charges=[]; rows=[]
        for arm,frame,i,reserved,paid,result in db.execute('select * from calls order by frame'):
            assert arm=='current' and i==-1 and paid is not None and 0<=paid<=reserved
            if result is not None:
                rows.extend(json.loads(result))
            charges.append(dict(frame=frame,paid_nanodollars=paid,reserved_nanodollars=reserved,status='usable' if result is not None else 'unusable'))
    key=lambda r:(r['frame'],r['i'])
    saved=[json.loads(line) for line in (HERE/'verdicts.jsonl').read_text().splitlines()]
    assert sorted(rows,key=key)==sorted(saved,key=key)
    assert len(charges)==sum(bool(f['flags']) for f in read(HERE/'inputs.json'))
    assert sum(c['paid_nanodollars'] for c in charges)<=100_000_000
    (HERE/'charges.json').write_text(json.dumps(charges,indent=2)+'\n')
    score_check.main()
    names=['PLAN.md','inputs.json','prepare.py','run.py','score_check.py','seal.py','charges.json','verdicts.jsonl','summary.json']
    (HERE/'seal.json').write_text(json.dumps({n:digest(HERE/n) for n in names},indent=2)+'\n')


if __name__=='__main__':
    main()
