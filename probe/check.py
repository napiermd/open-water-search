"""Deterministic local checks. Never creates a Meta client or opens scoring-only."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image
from runner import DATASETS,Ledger,Budget,MODEL,ROOT,execute,load_inputs,parse,price,rectangle
from score import contains,matching,prefix,report,score

class Fixture:
    def __init__(self): self.calls=0
    def count(self,body):
        assert body["model"]==MODEL and body["reasoning"]["effort"]=="minimal"
        assert "shard_" not in json.dumps(body)
        return 100
    def generate(self,body):
        self.calls+=1
        prompt=body['input'][0]['content'][0]['text']
        result={"tiles":list(reversed(range(9)))} if "Rank" in prompt else {"points":[[0.5,0.5,0.8]]}
        return {"status":"completed","output":[{"content":[{"type":"output_text","text":json.dumps(result)}]}],
                "usage":{"input_tokens":100,"input_tokens_details":{"cached_tokens":10},"output_tokens":20}}

def run():
    frozen=load_inputs(DATASETS["probe"][0]/"inputs")
    assert len(frozen)==30
    assert parse('{"tiles":[2,2,1]}', -1, None) == {"tiles":[2,1]}
    assert parse('[4,0]', -1, None) == {"tiles":[4,0]}
    assert parse('[]', 8, (200,135,301,203)) == {"points":[]}
    assert rectangle(301,203,8)==(200,135,301,203)
    assert parse('{"points":[[0.5,0.5,1]]}',8,(200,135,301,203))['points'][0]==[250.5,169,1]
    two=[[0,0,4,4],[2,0,6,4]]
    points=[[3,2,1],[1,2,.9]]
    pairs=matching(points,two)
    assert pairs=={0:1,1:0} and not contains(points[1],two[pairs[0]])
    assert price(100,10,20)==19040
    assert [r['paid'] for r in prefix([{'paid':10},{'paid':8}],15,True)]==[10,8]
    assert [r['paid'] for r in prefix([{'paid':10},{'paid':8}],15)]==[10]
    with TemporaryDirectory() as tmp:
        folder=Path(tmp)
        ledger=Ledger(folder/'budget.db',0)
        ledger.reserve('grid','s',0,245_000_000)
        try: ledger.reserve('chosen','s',-1,1)
        except RuntimeError: pass
        else: raise AssertionError('concurrent/outstanding reservation accepted')
        ledger.settle('grid','s',0,245_000_000,{})
        try: ledger.reserve('grid','s',1,1)
        except Budget: pass
        else: raise AssertionError('arm cap')
        ledger.reserve('chosen','s',-1,245_000_000)
        ledger.settle('chosen','s',-1,245_000_000,{})
        try: ledger.reserve('chosen','s',1,1)
        except Budget: pass
        else: raise AssertionError('probe cap')
        project=Ledger(folder/'project.db',8_999_999_990)
        try: project.reserve('grid','s',0,11)
        except Budget: pass
        else: raise AssertionError('project cap')
        # Use synthetic photos and labels for the entire paired protocol.
        frames=[]
        for i in range(30):
            filename=f'synthetic-{i}.jpg'
            Image.new('RGB',(301,203),(0,i,1)).save(folder/filename)
            frames.append(dict(frame=f'f{i}',image=filename,width=301,height=203))
        ledger=Ledger(folder/'fixture.db',0)
        api=Fixture()
        execute(folder,frames,folder,ledger,api)
        assert api.calls==570
        trace=json.loads((folder/'trace.json').read_text())
        assert len(trace)==570 and len(set((r['arm'],r['frame'],r['tile']) for r in trace))==570
        execute(folder,frames,folder,ledger,api)
        assert api.calls==570
        labels={f['frame']:[] for f in frames}
        labels['f0']=[(0,[20,20,80,45]),(0,[200,135,290,202])]
        result=score(trace,frames,labels)
        assert set(result['matched'])=={'grid','chosen'}
        first=report(trace[:1],frames,labels)
        assert (first['appearances'],first['found'],first['missed'],first['close_frames'])==(2,1,1,1)
        assert first['groups']['no_vessel']['missed_outside']==1
        assert first['frames']['f1']['coverage']=='uninspected'
        assert all(len(row['queue'])<=5 for arm in result['full'].values() for row in arm['frames'].values())
    print(json.dumps(dict(status='offline checks passed',frozen_images_verified=30,synthetic_responses=570,
                          additional_on_resume=0,live_requests=0),indent=2))

if __name__=='__main__': run()
