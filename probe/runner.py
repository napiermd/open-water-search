"""One frozen paired pass. No scorer imports or access to scoring inputs."""
import argparse
import base64
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sqlite3
import time
import urllib.request
from PIL import Image

MODEL = "muse-ember-1.0"
ROOT = Path(__file__).resolve().parents[1]
OVERVIEW = "Rank all nine equal grid tiles by where to inspect for swimmers. Tiles are 0 through 8 in row-major order from top left. Return only JSON: {\"tiles\":[...]}."
INSPECT = "Mark each person swimming or floating in the water. Return only JSON: {\"points\":[[x,y,confidence],...]}. Coordinates are fractions of this crop from top left, confidence 0 to 1. Use [] if there are none."
LIMIT = 2000
NANO = 10**9
PROBE_CAP = 490_000_000
ARMS = ("grid", "chosen")
MANIFEST_SHA = "ed1f42267359251e092516c223d0a2101c2a7fdadb8ed319acf81afd322ef132"
# Each dataset folder holds inputs/, live/ and scoring-only/. The validation manifest was frozen on November 23.
DATASETS = {
    "probe": (ROOT, MANIFEST_SHA),
    "validation": (ROOT / "validation", "65c987f6fe7ee68d1fad51d3e5edcdf730b6b9e823e4e07a2a9c68085e318713"),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_inputs(root, manifest_sha=MANIFEST_SHA):
    raw = (root / "manifest.json").read_bytes()
    assert digest(raw) == manifest_sha
    frames = json.loads(raw)["frames"]
    assert len(frames) == len({f['sha256'] for f in frames}) == 30
    for i, f in enumerate(frames, 1):
        assert f["frame"] == f"frame-{i:02}" and f["image"] == f"images/frame-{i:02}.jpg"
        path = root / f["image"]
        assert digest(path.read_bytes()) == f["sha256"]
        with Image.open(path) as im:
            assert im.size == (f["width"], f["height"])
    return frames


def rectangle(w, h, tile):
    if tile == -1:
        return (0, 0, w, h)
    x, y = tile % 3, tile // 3
    return (w*x//3, h*y//3, w*(x+1)//3, h*(y+1)//3)


def prepare(path, rect):
    with Image.open(path) as im:
        crop = im.crop(rect).convert("RGB")
        crop.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
        stream = io.BytesIO()
        crop.save(stream, format="JPEG", quality=90)
        return stream.getvalue()


def parse(raw, tile, rect):
    obj = json.loads(raw)
    # Ember sometimes answers with the bare list instead of the requested object.
    if tile == -1:
        tiles = obj if isinstance(obj, list) else obj["tiles"]
        if not isinstance(tiles, list) or any(type(t) is not int or not 0 <= t < 9 for t in tiles):
            raise ValueError("invalid tile rank")
        rank = list(dict.fromkeys(tiles))
        if not rank:
            raise ValueError("empty rank")
        return {"tiles": rank}
    x, y, right, bottom = rect
    points = []
    found = obj if isinstance(obj, list) else obj["points"]
    if not isinstance(found, list):
        raise ValueError("invalid points")
    for u,v,confidence in found:
        if not all(type(n) in (int,float) and 0 <= n <= 1 for n in (u,v,confidence)):
            raise ValueError("invalid point")
        points.append([x+min(u*(right-x), math.nextafter(float(right),0)-x),
                       y+min(v*(bottom-y), math.nextafter(float(bottom),0)-y), confidence])
    return {"points": points}


def interpret(event, tile):
    """Read the saved raw reply, so resumed and sealed records use the current reader."""
    for key in ("points", "tiles", "failure"):
        event.pop(key, None)
    reply = event["response"]
    try:
        if reply.get("status") != "completed":
            raise ValueError("incomplete response")
        raw = "".join(c["text"] for item in reply["output"] for c in item.get("content", []) if c["type"] == "output_text")
        event.update(parse(raw, tile, event["rect"]))
    except (ValueError, TypeError, KeyError):
        event["failure"] = "unusable response"
    return event


def price(inp, cached, output):
    if any(type(n) is not int or n<0 for n in (inp,cached,output)) or cached>inp:
        raise ValueError("invalid usage")
    return ((inp-cached)*100 + cached*4 + output*500) * (3 if inp>200000 else 1)


def arm_cap(prior):
    """Each search gets half of what remains of the probe cap after earlier probe spend."""
    return (PROBE_CAP - prior) // 2


class Budget(Exception):
    pass


class Ledger:
    def __init__(self, path, prior, manifest_sha=MANIFEST_SHA):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK(id=1), prior INTEGER, policy TEXT);
          CREATE TABLE IF NOT EXISTS calls (seq INTEGER PRIMARY KEY, arm TEXT, frame TEXT, tile INTEGER,
            reserved INTEGER, paid INTEGER, evidence TEXT, UNIQUE(arm,frame,tile));
        """)
        policy = digest((Path(__file__).read_bytes()+manifest_sha.encode()))
        self.db.execute("INSERT OR IGNORE INTO config VALUES(1,?,?)",(prior,policy))
        if tuple(self.db.execute("SELECT prior,policy FROM config").fetchone()) != (prior,policy):
            raise RuntimeError("run settings changed")
        self.prior = prior

    def reserve(self,arm,frame,tile,amount):
        if arm not in ARMS or amount<=0:
            raise ValueError("invalid reservation")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM calls WHERE paid IS NULL").fetchone():
                raise RuntimeError("unreconciled reservation; no automated retry")
            total,own=self.db.execute("SELECT COALESCE(SUM(paid),0),COALESCE(SUM(CASE WHEN arm=? THEN paid ELSE 0 END),0) FROM calls",(arm,)).fetchone()
            if own+amount>arm_cap(self.prior) or self.prior+total+amount>PROBE_CAP or self.prior+total+amount>9*NANO:
                raise Budget()
            self.db.execute("INSERT INTO calls(arm,frame,tile,reserved) VALUES(?,?,?,?)",(arm,frame,tile,amount))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def settle(self,arm,frame,tile,paid,event):
        n=self.db.execute("UPDATE calls SET paid=?,evidence=? WHERE arm=? AND frame=? AND tile=? AND paid IS NULL AND reserved>=?",
                          (paid,json.dumps(event),arm,frame,tile,paid)).rowcount
        if n!=1:
            raise RuntimeError("usage exceeded reservation or invalid ledger state")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):
        raise RuntimeError("unexpected redirect")


class Meta:
    def __init__(self):
        self.key=os.environ["MODEL_API_KEY"]
        self.client=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())

    def post(self,route,payload):
        req=urllib.request.Request("https://api.meta.ai/v1/responses"+route,
            data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+self.key,"Content-Type":"application/json"})
        with self.client.open(req,timeout=90) as res:
            return json.load(res)

    def count(self,body):
        n=self.post("/input_tokens",{k:body[k] for k in ("model","input")})["input_tokens"]
        if type(n) is not int or not 0<n<=1048576-LIMIT:
            raise ValueError("invalid preflight token count")
        return n

    def generate(self,body):
        return self.post("",body)


def execute(root, frames, out, ledger, api, manifest_sha=MANIFEST_SHA):
    rows=list(ledger.db.execute("SELECT * FROM calls ORDER BY seq"))
    if any(r['paid'] is None for r in rows):
        raise RuntimeError("unresolved generation reservation; reconcile first")
    cached={(r['arm'],r['frame'],r['tile']):interpret(json.loads(r['evidence']),r['tile']) for r in rows}
    ranks={}
    closed=set()
    failures=0
    for turn in range(10):
        for arm in (ARMS if turn%2==0 else ARMS[::-1]):
            if arm in closed or (arm=='grid' and turn==9):
                continue
            for i,f in enumerate(frames):
                frame=f['frame']
                if arm=='grid':
                    tile=(turn+i)%9
                elif turn==0:
                    tile=-1
                elif frame in ranks and turn <= len(ranks[frame]):
                    tile=ranks[frame][turn-1]
                else:
                    continue
                ident=(arm,frame,tile)
                if ident in cached:
                    event=cached[ident]
                else:
                    rect=rectangle(f["width"],f["height"],tile)
                    image=prepare(root/f["image"],rect)
                    prompt=OVERVIEW if tile==-1 else INSPECT
                    body={"model":MODEL,"reasoning":{"effort":"minimal"},"max_output_tokens":LIMIT,
                          "input":[{"role":"user","content":[{"type":"input_text","text":prompt},
                            {"type":"input_image","image_url":"data:image/jpeg;base64,"+base64.b64encode(image).decode()}]}]}
                    count=api.count(body)
                    try:
                        ledger.reserve(*ident,price(count,0,LIMIT))
                    except Budget:
                        closed.add(arm)
                        break
                    # Any uncertain dispatch, billing, quota or transport error leaves the reservation intact.
                    start=time.time()
                    reply=api.generate(body)
                    finish=time.time()
                    usage=reply["usage"]
                    paid=price(usage["input_tokens"],usage["input_tokens_details"]["cached_tokens"],usage["output_tokens"])
                    event=dict(rect=rect,image_sha256=digest(image),prompt_sha256=digest(prompt.encode()),
                               response=reply,started=start,finished=finish)
                    interpret(event,tile)
                    if tile==-1:
                        (out/(frame+"-overview.jpg")).write_bytes(image)
                    ledger.settle(*ident,paid,event)
                if tile==-1 and 'tiles' in event:
                    ranks[frame]=event['tiles']
                failures=failures+1 if 'failure' in event else 0
                if failures>=10:
                    raise RuntimeError("10 consecutive failures; stop for Andrew")
    records=[{**dict(r),"evidence":interpret(json.loads(r["evidence"]),r["tile"])} for r in ledger.db.execute("SELECT * FROM calls ORDER BY seq")]
    data=json.dumps(records,sort_keys=True).encode()
    (out/"trace.json").write_bytes(data)
    pending = out / "seal.pending"
    pending.write_text(json.dumps(dict(sha256=digest(data),manifest=manifest_sha,model=MODEL,
        limit=LIMIT,reasoning="minimal",overview=OVERVIEW,inspect=INSPECT,arms_at_ceiling=sorted(closed))))
    pending.replace(out / "seal.json")


def live(prior, dataset):
    if not 0<=prior<=9*NANO:
        raise ValueError("invalid prior project spend")
    if not os.environ.get("MODEL_API_KEY"):
        raise SystemExit("Credited personal MODEL_API_KEY unavailable.")
    base, manifest_sha = DATASETS[dataset]
    out = base / "live"
    # Launcher installs OS read restrictions before this interpreter starts.
    try:
        with (base/"scoring-only/manifest.json").open("rb") as source:
            source.read(1)
    except PermissionError:
        pass
    else:
        raise SystemExit("Use the isolated launcher.")
    frames=load_inputs(base/"inputs",manifest_sha)
    out.mkdir(exist_ok=True)
    with (out/"run.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (out/"seal.json").exists() or (out/"stop.txt").exists():
            raise SystemExit("Run sealed or breaker latched.")
        ledger=Ledger(out/"ledger.sqlite",prior,manifest_sha)
        # Record the configured route and both prompts before any provider request.
        settings = out / "settings.json"
        if not settings.exists():
            pending = out / "settings.pending"
            pending.write_text(json.dumps({
                "dataset": dataset,
                "route": "https://api.meta.ai/v1/responses",
                "model": MODEL,
                "reasoning": "minimal",
                "max_output_tokens": LIMIT,
                "max_image_edge": 1000,
                "jpeg_quality": 90,
                "manifest_sha256": manifest_sha,
                "overview_prompt_sha256": digest(OVERVIEW.encode()),
                "close_look_prompt_sha256": digest(INSPECT.encode()),
                "per_arm_cap_nano": arm_cap(prior),
                "probe_cap_nano": PROBE_CAP,
            }, indent=2))
            pending.replace(settings)
        try:
            execute(base/"inputs",frames,out,ledger,Meta(),manifest_sha)
        except BaseException as e:
            (out/"stop.txt").write_text(type(e).__name__+"; reconcile before resuming\n")
            raise

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--prior-nanodollars",type=int,required=True,help="earlier spend that counts against this run's cap")
    parser.add_argument("--dataset",choices=sorted(DATASETS),default="probe")
    args=parser.parse_args()
    live(args.prior_nanodollars,args.dataset)
