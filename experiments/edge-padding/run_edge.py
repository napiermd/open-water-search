"""Apply the existing black-padded encoder only inside this experiment's process."""
import argparse
import fcntl
import os
import sys
from pathlib import Path
from unittest.mock import patch

from edge import HERE, read, digest, pilot
sys.path.insert(0,str(HERE.parent/'tile-flag-check'))
import run as incremental

INPUT_SHA='6e2cf5c539c62765681a327a505185a90a8504fa86d6589e2816022bac4558cc'
CAP=50_000_000


def check(folder, rows, client):
    with patch.object(incremental,'CAP',CAP), patch.object(incremental,'INPUT_SHA',INPUT_SHA), \
         patch.object(pilot,'CAP',CAP), patch.object(pilot.fc,'crop',pilot.padded):
        incremental.check_all(folder,rows,client)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--key-file',type=Path,required=True);args=parser.parse_args()
    if digest(HERE/'inputs.json')!=INPUT_SHA: raise SystemExit('Frozen manifest changed')
    directory=os.open(HERE,os.O_RDONLY)
    try:
        fcntl.flock(directory,fcntl.LOCK_EX|fcntl.LOCK_NB)
        os.environ['MODEL_API_KEY']=args.key_file.expanduser().read_text().strip()
        check(HERE,read(HERE/'inputs.json'),pilot.Ember)
    finally:
        os.close(directory)
