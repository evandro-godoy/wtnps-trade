import joblib, glob, json, os
from pprint import pprint

for f in glob.glob('newapp/models/*params.joblib'):
    print('===', f)
    params = joblib.load(f)
    for k,v in params.items():
        if isinstance(v,(list,tuple)):
            print(f'{k}: list(len={len(v)}) sample={v[:5]}')
        else:
            print(f'{k}: {type(v)} -> {v}')
