#!/usr/bin/env python3
import json, pathlib, sys
root = pathlib.Path(__file__).resolve().parents[1]
platforms = json.loads((root/'config/platform-matrix.json').read_text())['platforms']
allowed = {'macos-arm64','macos-x86_64','windows-arm64','windows-x86_64'}
keys = [p['key'] for p in platforms]
if set(keys) != allowed or len(keys) != len(set(keys)):
    raise SystemExit('platform matrix must contain exactly the four supported platforms')
for p in platforms:
    if p['os'] == 'macos' and p['arch'] not in ('arm64','x86_64'): raise SystemExit('invalid macOS architecture')
    if p['os'] == 'windows' and p['arch'] not in ('arm64','x86_64'): raise SystemExit('invalid Windows architecture')
out = json.dumps({'include': platforms}, separators=(',', ':'))
if len(sys.argv) == 3 and sys.argv[1] == '--github-output':
    with open(sys.argv[2], 'a') as f: f.write('matrix='+out+'\n')
else:
    print(out)
