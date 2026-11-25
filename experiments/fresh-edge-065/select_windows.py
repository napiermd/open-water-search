"""Apply the published fresh-window rule using only provenance, time and detector geometry."""
from collections import Counter,defaultdict
from itertools import groupby,zip_longest
from pathlib import Path
import json
import re
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RANK=HERE.parent/'lost-people/flight-ranking'
sys.path.insert(0,str(HERE.parent/'edge-padding'))
sys.path.insert(0,str(RANK))
from edge import centered_rect,read,digest,pilot
from rank_flights import used_frames,NEAR_FRAMES


def family(video):
    return re.sub(r'(?<=m)_\d+$','',Path(video).stem)


def write(name, data):
    (HERE/name).write_text(json.dumps(data,separators=(',',':'))+'\n')


def select():
    old=read(HERE.parent/'harder-pilot/pilot.json')+read(HERE.parent/'reserve-092/reserve.json')
    previous,live=used_frames()
    excluded={family(f['video']) for f in old}|{family(v) for v in live}
    seen={f['sha256'] for f in old}
    for path in ('mobdrone/inputs/manifest.json','runs/verify-mobdrone/inputs/manifest.json'):
        seen.update(f['sha256'] for f in read(ROOT/path)['frames'])
    rows=read(RANK/'inputs/manifest.json')['frames']
    seen.update(r['sha256'] for r in rows if r['video'] in live)
    counts=Counter(r['sha256'] for r in rows)
    seal=read(RANK/'flags-005/seal.json');assert digest(RANK/'flags-005/boxes.json')==seal['boxes_sha256']
    assert digest(RANK/'inputs/manifest.json')==seal['inputs_sha256']
    boxes={r['frame']:r for r in read(RANK/'flags-005/boxes.json')}
    eligible=defaultdict(list)
    for f in rows:
        v=f['video']
        if family(v) in excluded or f['sha256'] in seen or counts[f['sha256']]!=1:continue
        if any(abs(n-f['video_frame'])<=NEAR_FRAMES for n in previous.get(v,[])):continue
        flags=pilot.fc.candidates(boxes[f['frame']]); indices=[]
        for i,b in enumerate(flags):
            l,t,r,bottom=centered_rect(f['width'],f['height'],b)
            if l<0 or t<0 or r>f['width'] or bottom>f['height']:indices.append(i)
        eligible[v].append((dict(f,flags=flags),indices))
    best={}
    for v,seq in eligible.items():
        seq.sort(key=lambda item:item[0]['second'])
        for _,group in groupby(enumerate(seq),key=lambda x:x[1][0]['second']-x[0]):
            block=[item for _,item in group]
            for start in range(len(block)):
                window=block[start:start+12];edge_seconds=sum(bool(idx) for _,idx in window)
                if not edge_seconds:continue
                key=(-edge_seconds,-len(window),v,window[0][0]['second'])
                if family(v) not in best or key<best[family(v)][0]:best[family(v)]=(key,window)
    chosen=sorted(best.values(),key=lambda x:x[0])[:8]; assert chosen
    frames=[];edges=[];pairs=[]
    for _,window in chosen:
        group=[];first=window[0][0]['second']
        for row,indices in window:
            assert digest(RANK/'inputs'/row['image'])==row['sha256']
            f=dict(row,block=f"{row['video']}/{first}");e=dict(f,flags=[f['flags'][i] for i in indices],original_indices=indices)
            frames.append(f);edges.append(e);group.append([dict(j,frame=a+'/'+f['frame']) for a,j in [('whole',f),('edge',e)]])
        pairs.append(group)
    jobs=[j for batch in zip_longest(*pairs) for pair in batch if pair for j in pair];write('fresh.json',frames);write('edges.json',edges);write('inputs.json',jobs)
    print([(g[0],len(g[1])) for g in chosen]);print('selected frames',len(frames),'whole flags',sum(len(f['flags']) for f in frames),'edge flags',sum(len(e['flags']) for e in edges),'batches',sum(bool(j['flags']) for j in jobs))


if __name__=='__main__':select()
