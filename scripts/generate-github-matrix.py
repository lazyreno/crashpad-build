#!/usr/bin/env python3
import json, pathlib, sys
root = pathlib.Path(__file__).resolve().parents[1]
platforms = json.loads((root/'config/platform-matrix.json').read_text())['platforms']
allowed = {
    ('macos', 'arm64', 'release'), ('macos', 'x64', 'release'),
    ('windows', 'arm64', 'release'), ('windows', 'arm64', 'debug'),
    ('windows', 'x64', 'release'), ('windows', 'x64', 'debug'),
}
targets = [(p['os'], p['arch'], p.get('configuration')) for p in platforms]
if set(targets) != allowed or len(targets) != len(set(targets)):
    raise SystemExit('platform matrix must contain exactly the six supported configuration-qualified targets')
for p in platforms:
    if p['os'] == 'macos' and p['arch'] not in ('arm64','x64'): raise SystemExit('invalid macOS architecture')
    if p['os'] == 'windows' and p['arch'] not in ('arm64','x64'): raise SystemExit('invalid Windows architecture')
    if p.get('configuration') not in ('release', 'debug'): raise SystemExit('invalid SDK configuration')
    if p['os'] == 'macos' and p['configuration'] != 'release': raise SystemExit('macOS SDK supports release only')
out = json.dumps({'include': platforms}, separators=(',', ':'))
if len(sys.argv) == 3 and sys.argv[1] == '--github-output':
    with open(sys.argv[2], 'a') as f: f.write('matrix='+out+'\n')
else:
    print(out)
