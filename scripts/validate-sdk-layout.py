#!/usr/bin/env python3
import argparse, pathlib, sys
p=argparse.ArgumentParser(); p.add_argument('root'); p.add_argument('--platform',required=True); a=p.parse_args(); r=pathlib.Path(a.root)
required=['bin','include','lib','cmake','licenses','manifest.json']
missing=[x for x in required if not (r/x).exists()]
handler='crashpad_handler.exe' if a.platform.startswith('windows') else 'crashpad_handler'
if not (r/'bin'/handler).exists(): missing.append('bin/'+handler)
if missing: print('missing: '+', '.join(missing), file=sys.stderr); sys.exit(1)
print('SDK layout valid:', a.platform)
