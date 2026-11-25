"""Run the frozen incremental single-image check through personal Meta Ember."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import argparse
import fcntl
import json
import os
import sys
import threading

from prepare import HERE, PILOT, digest, read
sys.path.insert(0, str(PILOT))
import run_pilot as pilot

CAP = 100_000_000  # nanodollars, across this run including unresolved reservations
INPUT_SHA = 'cbab57fd0277f7d2d0fc37fe01b8fc29515e4b63d89e51951b35bdbf88fed71c'


def check_all(folder, frames, factory):
    # The shared pilot ledger uses a process-wide ceiling. Narrow it before opening the ledger.
    pilot.CAP = min(CAP, pilot.CAP)
    ledger = pilot.Ledger(folder, INPUT_SHA)
    clients = threading.local()

    def check(row):
        key = 'current', row['frame'], -1
        with ledger.gate:
            if ledger.stop or key in ledger.known:
                return
        try:
            body = pilot.request('current', [row], -1, pilot.IMAGES)
            if not hasattr(clients, 'api'):
                clients.api = factory()
            api = clients.api
            count = ledger.provider_call(key, 'count', api.count, body)
            extra = {k:v for k,v in body.items() if k not in ('input','model')}
            bound = count + len(json.dumps(extra).encode()) + 256
            worst = pilot.price(bound, 0, body['max_output_tokens'])
            if not ledger.reserve(key, worst):
                return
            reply = ledger.provider_call(key, 'generate', api.generate, body)
            usage = reply['usage']
            paid = pilot.price(usage['input_tokens'], usage.get('input_tokens_details',{}).get('cached_tokens',0), usage['output_tokens'])
            if paid > worst or usage['input_tokens'] > bound or usage['output_tokens'] > body['max_output_tokens']:
                raise ValueError('Provider usage exceeds reservation')
            try:
                records = pilot.verdicts(reply,'current',row['frame'],range(len(row['flags'])))
            except (ValueError, KeyError, TypeError, AttributeError):
                records = None
            ledger.finish(key, paid, records)
        except BaseException as error:
            with ledger.gate:
                ledger.latch(f'{row["frame"]}: {type(error).__name__}')
                ledger.gate.notify_all()
            raise

    with closing(ledger.db), ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(check, (r for r in frames if r['flags'])))
        if ledger.stop:
            raise pilot.Stopped(ledger.stop)
        total, usable, paid = ledger.db.execute('SELECT count(*),count(result),sum(paid) FROM calls').fetchone()
        print(f'{total} requests, {usable} usable batches, {paid} nanodollars')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file', required=True, type=pilot.Path)
    args = parser.parse_args()
    if digest(HERE/'inputs.json') != INPUT_SHA:
        raise SystemExit('Manifest changed since registration')
    os.environ['MODEL_API_KEY'] = args.key_file.expanduser().read_text().strip()
    directory = os.open(HERE, os.O_RDONLY)
    try:
        fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
        check_all(HERE, read(HERE/'inputs.json'), pilot.Ember)
    finally:
        os.close(directory)
