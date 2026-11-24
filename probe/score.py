"""Score verified, sealed predictions. Reads labels only after checking the seal."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CHECKPOINTS=[10_000_000,25_000_000,50_000_000,100_000_000,250_000_000]

def grid_points(record):
    """Recover a close look answered on Meta's documented 0-1000 image grid instead of fractions.

    Decided on November 23 before any label was opened, and applied identically to both searches.
    Muse models place (0,0) at the top left and (1000,1000) at the bottom right of the image they see."""
    evidence=record['evidence']
    if record['tile']<0 or 'failure' not in evidence or evidence['response'].get('status')!='completed':
        return None
    raw=''.join(c['text'] for item in evidence['response']['output'] for c in item.get('content',[]) if c['type']=='output_text')
    try:
        obj=json.loads(raw)
        found=obj if isinstance(obj,list) else obj['points']
        if not found or not all(len(p)==3 and all(type(n) in (int,float) for n in p) for p in found):
            return None
        if not all(0<=u<=1000 and 0<=v<=1000 and 0<=c<=1 for u,v,c in found) or all(u<=1 and v<=1 for u,v,c in found):
            return None
    except (ValueError,TypeError,KeyError):
        return None
    x,y,right,bottom=evidence['rect']
    return [[x+min(u/1000*(right-x),math.nextafter(float(right),0)-x),
             y+min(v/1000*(bottom-y),math.nextafter(float(bottom),0)-y),c] for u,v,c in found]

def with_grid_rule(trace):
    """Copy of the trace with 0-1000 grid close looks converted; every other record is unchanged."""
    result=[]
    for record in trace:
        points=grid_points(record)
        if points is None:
            result.append(record)
            continue
        evidence={k:v for k,v in record['evidence'].items() if k!='failure'}
        result.append({**record,'evidence':{**evidence,'points':points,'reader':'0-1000 grid converted'}})
    return result
def contains(p,b):
    return b[0]<=p[0]<=b[2] and b[1]<=p[1]<=b[3]

def matching(points,boxes):
    owners={}
    def visit(i,seen):
        for j,b in enumerate(boxes):
            if j in seen or not contains(points[i],b):
                continue
            seen.add(j)
            if j not in owners or visit(owners[j],seen):
                owners[j]=i
                return True
        return False
    for i in range(len(points)):
        visit(i,set())
    return {i:j for j,i in owners.items()}

def groundtruth(root,frames):
    manifest=json.loads((root/"manifest.json").read_text())["frames"]
    if [r["frame"] for r in manifest]!=[f["frame"] for f in frames]:
        raise ValueError("label manifest mismatch")
    result={}
    for row,f in zip(manifest,frames):
        raw=(root/row["label"]).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row["sha256"]:
            raise ValueError("label hash mismatch")
        boxes=[]
        for line in raw.decode().splitlines():
            c,u,v,w,h=map(float,line.split())
            boxes.append((int(c),[(u-w/2)*f['width'],(v-h/2)*f['height'],(u+w/2)*f['width'],(v+h/2)*f['height']]))
        result[f["frame"]]=boxes
    return result

def prefix(rows,cap,ceil=False):
    kept=[]
    paid=0
    for r in rows:
        if paid+r["paid"]>cap:
            if ceil and paid<cap:
                kept.append(r)
            break
        kept.append(r)
        paid+=r["paid"]
    return kept

def union_area(boxes):
    area=0
    edges=sorted({x for b in boxes for x in (b[0],b[2])})
    for l,r in zip(edges,edges[1:]):
        end=-math.inf
        for lo,hi in sorted((b[1],b[3]) for b in boxes if b[0]<r and b[2]>l):
            area+=(r-l)*max(0,hi-max(end,lo))
            end=max(end,hi)
    return area

def report(rows,frames,labels):
    totals=Counter(dict(found=0,missed=0,unmatched=0,appearances=0,close_frames=0,
                        unmatched_on_vessel_only_frames=0))
    groups={k:Counter() for k in ('no_vessel','near_vessel','vessel_elsewhere')}
    multi=Counter()
    detail={}
    for index,f in enumerate(frames):
        fid=f['frame']
        calls=[r for r in rows if r['frame']==fid]
        inspected=[r for r in calls if r['tile']>=0 and 'points' in r['evidence']]
        rects=[r['evidence']['rect'] for r in inspected]
        all_points=[p for r in inspected for p in r['evidence']['points']]
        points=sorted(all_points,key=lambda p:-p[2])[:5]
        people=[b for c,b in labels[fid] if c==0]
        others=[b for c,b in labels[fid] if c!=0]
        vessels=[b for c,b in labels[fid] if c in (1,2)]
        pairs=matching(points,people)
        unmatched=Counter()
        for i,p in enumerate(points):
            if i not in pairs:
                kind='duplicate' if any(contains(p,b) for b in people) else 'wrong_class' if any(contains(p,b) for b in others) else 'background'
                unmatched[kind]+=1
        found=len(pairs)
        totals.update(dict(found=found,appearances=len(people),missed=len(people)-found,unmatched=sum(unmatched.values()),
                           close_frames=int(bool(rects)),unmatched_on_vessel_only_frames=sum(unmatched.values()) if vessels and not people else 0))
        current=set()
        centers=[]
        for j,b in enumerate(people):
            x,y=(b[0]+b[2])/2,(b[1]+b[3])/2
            centers.append((x,y))
            distance=min((math.hypot(max(v[0]-x,x-v[2],0),max(v[1]-y,y-v[3],0)) for v in vessels),default=math.inf)
            group='no_vessel' if not vessels else 'near_vessel' if distance<=.1*math.hypot(f['width'],f['height']) else 'vessel_elsewhere'
            current.add(group)
            groups[group]['appearances']+=1
            if j in pairs.values():
                groups[group]['found']+=1
            else:
                inside=any(l<=x<r and t<=y<bot for l,t,r,bot in rects)
                groups[group]['missed_inside' if inside else 'missed_outside']+=1
        for g in current:
            groups[g]['frames']+=1
        if len(people)>=2:
            multi['all' if found==len(people) else 'some' if found else 'none']+=1
        coverage='complete' if len(rects)==9 else 'partial' if rects else 'unreadable' if any('failure' in r['evidence'] for r in calls) else 'uninspected'
        detail[fid]=dict(found=found,missed=len(people)-found,queue=points,matches=pairs,unmatched=dict(unmatched),
                         tiles=[r['tile'] for r in inspected],coverage=coverage,boxes=people)
        rank=next((r['evidence'].get('tiles',[]) for r in calls if r['tile']==-1),[])
        if any(r['arm']=='chosen' for r in rows):
            order=[(index+k)%9 for k in range(9)]
            def bounds(tile):
                col,row=tile%3,tile//3
                return (col*f['width']//3,row*f['height']//3,(col+1)*f['width']//3,(row+1)*f['height']//3)
            def vessel_area(tile):
                l,t,r,bot=bounds(tile)
                clipped=[(max(l,a),max(t,b),min(r,c),min(bot,d)) for a,b,c,d in vessels]
                return union_area([v for v in clipped if v[0]<v[2] and v[1]<v[3]])
            boats=max(order,key=vessel_area)
            def hits(tile):
                l,t,r,bot=bounds(tile)
                return any(l<=x<r and t<=y<bot for x,y in centers)
            detail[fid]['first_zoom']=dict(chosen=rank[0] if rank else None,boats_first=boats,
                                           chosen_hit=bool(rank and hits(rank[0])),boats_hit=hits(boats))
    return dict(**totals,paid_nano=sum(r['paid'] for r in rows),calls=len(rows),
                seconds=sum(r['evidence']['finished']-r['evidence']['started'] for r in rows),
                groups=groups,multi=multi,frames=detail)

def score(trace,frames,labels):
    arms={arm:[r for r in trace if r['arm']==arm] for arm in ('grid','chosen')}
    full={arm:report(rows,frames,labels) for arm,rows in arms.items()}
    cap=min(v['paid_nano'] for v in full.values())
    def at(amount,ceil_arm=None):
        return {arm:report(prefix(rows,amount,arm==ceil_arm),frames,labels) for arm,rows in arms.items()}
    comparisons={}
    verdict='inconclusive or tie'
    for contender,other in [('chosen','grid'),('grid','chosen')]:
        comparison=at(cap,other)
        a,b=comparison[contender],comparison[other]
        if (a['paid_nano']<=b['paid_nano'] and a['found']>b['found'] and a['unmatched']<=b['unmatched']
            and min(a['close_frames'],b['close_frames'])==len(frames)):
            verdict=contender
        comparisons[contender]=comparison
    return dict(verdict=verdict,common_nano=cap,matched=comparisons,full=full,
                checkpoints={c:at(c) for c in CHECKPOINTS})

def order_table(trace,frames,labels,looks=(1,2,3,9)):
    """Swimmers found when each tile order is applied to the same recorded answers, under the five-sighting limit.

    Prespecified as the main validation measure on November 23. A frame without a usable Ember ranking
    contributes no finds to the Ember order, as it would in the live search."""
    answers={(r['arm'],r['frame'],r['tile']):r['evidence'] for r in trace}
    rank={r['frame']:r['evidence']['tiles'] for r in trace if r['arm']=='chosen' and r['tile']==-1 and 'tiles' in r['evidence']}
    def order(policy,index,fid):
        grid=[(index+k)%9 for k in range(9)]
        if policy=='grid':
            return grid
        if policy=='center':
            return [4]+[t for t in grid if t!=4]
        ranked=rank.get(fid,[])
        return ranked+[t for t in grid if t not in ranked] if ranked else []
    finds={}
    for source in ('grid','chosen'):
        finds[source]={}
        for policy in ('ember','center','grid'):
            finds[source][policy]={}
            for k in looks:
                total=0
                for index,f in enumerate(frames):
                    fid=f['frame']
                    people=[b for c,b in labels[fid] if c==0]
                    points=[p for t in order(policy,index,fid)[:k] for p in answers.get((source,fid,t),{}).get('points',[])]
                    total+=len(matching(sorted(points,key=lambda p:-p[2])[:5],people))
                finds[source][policy][k]=total
    beats=lambda other:all(finds[s]['ember'][1]>finds[s][other][1] for s in finds)
    return dict(looks=list(looks),finds=finds,appearances=sum(c==0 for f in frames for c,_ in labels[f['frame']]),
                frames_without_rank=len(frames)-len(rank),
                unreadable_crops={s:sum(1 for f in frames for t in range(9) if 'points' not in answers.get((s,f['frame'],t),{})) for s in finds},
                ember_beats_center_at_one_look=beats('center'),ember_beats_grid_at_one_look=beats('grid'))

if __name__=='__main__':
    import sys
    base=ROOT/'validation' if sys.argv[1:]==['validation'] else ROOT
    live=base/'live'
    seal=json.loads((live/'seal.json').read_text())
    if (live/'trace.json').exists():
        raw=(live/'trace.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==seal['sha256']
    else:
        # Public copy: response IDs removed by redact.py, everything used for scoring unchanged.
        raw=(live/'trace-redacted.json').read_bytes()
        redaction=json.loads((live/'redaction.json').read_text())
        assert redaction['original_sha256']==seal['sha256']
        assert hashlib.sha256(raw).hexdigest()==redaction['redacted_sha256']
    manifest=(base/'inputs/manifest.json').read_bytes()
    assert hashlib.sha256(manifest).hexdigest()==seal['manifest']
    frames=json.loads(manifest)['frames']
    trace=json.loads(raw)
    labels=groundtruth(base/'scoring-only',frames)
    import os,tempfile
    converted=with_grid_rule(trace)
    for name,rows in (('score.json',converted),('score-strict.json',trace)):
        scores=score(rows,frames,labels)
        scores['grid_records_converted']=sum('reader' in r['evidence'] for r in rows)
        scores['order_table']=order_table(rows,frames,labels)
        data=json.dumps(scores,sort_keys=True).encode()
        if (live/name).exists():
            same=(live/name).read_bytes()==data
            print(f"{live.relative_to(ROOT)}/{name}: {'matches the published scorecard' if same else 'DIFFERS from the published scorecard'}")
            continue
        with tempfile.NamedTemporaryFile(dir=live,delete=False) as tmp:
            tmp.write(data)
        try:
            os.link(tmp.name,live/name)
        finally:
            os.unlink(tmp.name)
