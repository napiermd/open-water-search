"""Run only the committed current-check batches under the single reserve ceiling."""
import argparse
import fcntl
import os
from pathlib import Path
import sys
from manifest import HERE, load

sys.path.insert(0,str(HERE.parent/'tile-flag-check'))
import run as incremental
from prepare import digest

CAP = 150_000_000

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file',type=Path,required=True)
    args=parser.parse_args()
    lock=load(HERE/'lock.json')
    for name, checksum in lock.items():
        if digest(HERE/name)!=checksum:
            raise ValueError(f'Pre-call seal changed: {name}')
    jobs=load(HERE/'inputs.json')
    if len(jobs)!=534 or len({r['frame'] for r in jobs})!=534:
        raise ValueError('Reserve jobs differ from the paired protocol')
    incremental.INPUT_SHA=lock['inputs.json']
    incremental.CAP=CAP
    assert incremental.pilot.CAP==CAP
    directory=os.open(HERE,os.O_RDONLY)
    try:
        fcntl.flock(directory,fcntl.LOCK_EX|fcntl.LOCK_NB)
        os.environ['MODEL_API_KEY']=args.key_file.expanduser().read_text().strip()
        incremental.check_all(HERE,jobs,incremental.pilot.Ember)
    finally:
        os.close(directory)


if __name__=='__main__':main()
