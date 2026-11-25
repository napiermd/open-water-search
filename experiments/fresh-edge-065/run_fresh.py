"""Dispatch frozen baseline and centered edge requests against a single five-cent ledger."""
import argparse
import fcntl
import os
import sys
from pathlib import Path
from unittest.mock import patch
from select_windows import HERE, digest, read, pilot

sys.path.insert(0,str(HERE.parent/'tile-flag-check'))
import run as incremental

CAP=50_000_000
INPUT_SHA='7be38ddf6fe0233e93fb52b7638d77db2c514408a964baad9cbe6735c4a42c46'
original_request=pilot.request


def request(arm,rows,index,images):
    row,=rows
    if row['frame'].startswith('whole/'):
        return original_request(arm,rows,index,images)
    if not row['frame'].startswith('edge/') or arm!='current':raise ValueError('Unplanned arm')
    image=pilot.photo(row,images)
    body=pilot.fc.request_body(image,[])
    content=body['input'][0]['content']
    for n,box in enumerate(row['flags'],1):
        content.extend([{'type':'input_text','text':f'Crop {n}:'},
                        {'type':'input_image','image_url':pilot.padded(image,box)}])
    return body


def check(folder,rows,factory):
    with patch.object(incremental,'CAP',CAP),patch.object(incremental,'INPUT_SHA',INPUT_SHA), \
         patch.object(pilot,'CAP',CAP),patch.object(pilot,'request',request):
        incremental.check_all(folder,rows,factory)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--key-file',type=Path,required=True);args=parser.parse_args()
    lock=read(HERE/'lock.json')
    if lock['inputs.json']!=INPUT_SHA or any(digest(HERE/n)!=h for n,h in lock.items()):raise SystemExit('Pre-call seal changed')
    descriptor=os.open(HERE,os.O_RDONLY)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        os.environ['MODEL_API_KEY']=args.key_file.expanduser().read_text().strip()
        check(HERE,read(HERE/'inputs.json'),pilot.Ember)
    finally:os.close(descriptor)
