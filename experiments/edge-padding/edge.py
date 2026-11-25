"""Select whole-frame flags whose integer crop would extend beyond the source JPEG."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RESERVE = HERE.parent / 'reserve-092'
sys.path.insert(0, str(HERE.parent/'harder-pilot'))
import run_pilot as pilot


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def centered_rect(width, height, box):
    x1, y1, x2, y2 = box[:4]
    side = min(width, height, max(pilot.fc.MIN_CROP, pilot.fc.CROP_SCALE * max(x2-x1,y2-y1)))
    x, y = (x1+x2)/2, (y1+y2)/2
    return tuple(round(v) for v in (x-side/2, y-side/2, x+side/2, y+side/2))


def select():
    assert digest(RESERVE/'reserve.json') == 'bb5432ee3a7cab1d8fbf218158fbb9b65971fbe2facebd6084fee99f1bee2fbc'
    jobs=[]
    for row in read(RESERVE/'reserve.json'):
        width,height=row['width'],row['height']; selected=[]
        for i,box in enumerate(row['flags']):
            l,t,r,b=centered_rect(width,height,box)
            if l<0 or t<0 or r>width or b>height:
                selected.append(i)
        if selected:
            jobs.append(dict(row,flags=[row['flags'][i] for i in selected],original_indices=selected))
    return jobs


if __name__=='__main__':
    jobs=select();(HERE/'inputs.json').write_text(json.dumps(jobs,separators=(',',':'))+'\n')
    print(len(jobs),'frame batches;',sum(len(r['flags']) for r in jobs),'edge flags;',len({r['video'] for r in jobs}),'clips')
    row=next(r for r in jobs if r['video']=='DJI_0915_0015_50m.mp4' and r['second']==136)
    for i,box in zip(row['original_indices'],row['flags']):print(i,box[:4],centered_rect(row['width'],row['height'],box))
