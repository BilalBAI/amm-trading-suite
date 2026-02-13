import json
from datetime import datetime

# simple regime based on last stored IV or price

def load():
    try:
        with open('/home/bilal/.openclaw/workspace/live-monitoring/state.json') as f:
            return json.load(f)
    except Exception:
        return {}


def regime():
    s = load()
    iv = None
    if 'iv' in s and isinstance(s['iv'], dict):
        iv = s['iv'].get('result', {}).get('mark_iv')
    # crude heuristic
    if iv and iv > 60:
        return 'HIGH'
    return 'NORMAL'


def analyze():
    r = regime()
    return {'regime': r}

if __name__=='__main__':
    print(json.dumps(analyze(), indent=2))
