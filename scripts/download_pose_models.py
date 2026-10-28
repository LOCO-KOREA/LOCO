"""Download exact registered pose artifacts. No settings or user database are modified."""
import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.pose_contract import MODELS


def main():
    parser=argparse.ArgumentParser();parser.add_argument('models',nargs='*');args=parser.parse_args()
    for identity in args.models or ['mediapipe-heavy','mediapipe-full']:
        if identity not in MODELS:parser.error('Unknown pose model: '+identity)
        model=MODELS[identity];path=ROOT/model['model_path']
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==model['model_sha256']:
            print('Verified '+identity);continue
        data=urllib.request.urlopen(model['url'],timeout=90).read()
        if hashlib.sha256(data).hexdigest()!=model['model_sha256']:raise ValueError('Downloaded model hash differs: '+identity)
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);print('Downloaded '+identity)


if __name__=='__main__':main()
