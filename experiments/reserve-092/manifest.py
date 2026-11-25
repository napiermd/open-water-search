"""Prepare the six previously reserved clip segments and the local detector inputs."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RANK = HERE.parent/'lost-people/flight-ranking'
sys.path.insert(0,str(HERE.parents[1]/'probe'))
from flag_check import candidates


def load(path):
    return json.loads(path.read_bytes())


def write(name,value):
    (HERE/name).write_text(json.dumps(value,separators=(',',':'))+'\n')


def main():
    pilot=load(HERE.parent/'harder-pilot/pilot.json')
    blocks=load(RANK/'eligible-segments.json')
    videos={b['video'] for b in blocks} - {f['video'] for f in pilot}
    rows={(r['video'],r['second']):r for r in load(RANK/'inputs/manifest.json')['frames'] if r['video'] in videos}
    boxes={p['frame']:p for p in load(RANK/'flags-005/boxes.json')}
    frames=[]; detector=[]
    for b in sorted(blocks,key=lambda u:(u['video'],u['first_second'])):
        if b['video'] not in videos:continue
        for t in range(b['first_second'],b['last_second']+1):
            r=rows[b['video'],t];path=RANK/'inputs'/r['image']
            assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256']
            frames.append(dict(r,flags=candidates(boxes[r['frame']]),block=f"{r['video']}/{b['first_second']}"))
            detector.append(dict(frame=r['frame'],image='../lost-people/flight-ranking/inputs/'+r['image'],width=r['width'],height=r['height'],sha256=r['sha256']))
    assert (len(videos),len(frames),len({r['block'] for r in frames}),sum(len(r['flags']) for r in frames))==(6,267,43,1239)
    write('reserve.json',frames);write('detector-input.json',{'frames':detector})
    print('Frozen',len(frames),'seconds in',sorted(videos))


if __name__=='__main__':main()
