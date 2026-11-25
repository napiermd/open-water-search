"""Apply the prior tile deduplication rule; pair the current and additional jobs."""
from collections import defaultdict
from itertools import zip_longest
import sys
from manifest import HERE, load, write, candidates

sys.path.insert(0,str(HERE.parent/'tile-flag-check'))
from prepare import digest, iou


def main():
    seal=load(HERE/'tiled/seal.json')
    assert digest(HERE/'tiled/boxes.json')==seal['boxes_sha256']
    assert digest(HERE/'detector-input.json')==seal['inputs_sha256']
    older=load(HERE.parent/'seven-clip-tiles/seal.json')
    assert seal['model']==older['model'] and seal['tiles']==older['tiles']
    by_clip=defaultdict(list); extra=[]
    for whole,tile in zip(load(HERE/'reserve.json'),load(HERE/'tiled/boxes.json'),strict=True):
        assert whole['frame']==tile['frame']
        flags=candidates(tile)
        indices=[i for i,box in enumerate(flags) if all(iou(box,old)<0.50 for old in whole['flags'])]
        more=dict(whole,flags=[flags[i] for i in indices],tile_indices=indices)
        extra.append(more)
        by_clip[whole['video']].append([dict(r,frame=arm+'/'+r['frame']) for arm,r in [('whole',whole),('tile',more)]])
    jobs=[job for batch in zip_longest(*by_clip.values()) for pair in batch if pair for job in pair]
    write('additions.json',extra);write('inputs.json',jobs)
    for arm in ('whole','tile'):
        subset=[r for r in jobs if r['frame'].startswith(arm+'/') and r['flags']]; print(arm,len(subset),'requests,',sum(len(r['flags']) for r in subset),'flags')


if __name__=='__main__':main()
