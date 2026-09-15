#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--release-assets', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--base-url', required=True)
    p.add_argument('--release-tag', required=True)
    a = p.parse_args()
    sdk = json.loads(Path('config/sdk-version.json').read_text())
    matrix = json.loads(Path('config/platform-matrix.json').read_text())['platforms']
    artifacts = []
    for platform in matrix:
        name = f"crashpad-sdk-{platform['key']}.zip"
        archive = a.release_assets / name
        checksum = a.release_assets / f'{name}.sha256'
        if not archive.exists() or not checksum.exists():
            raise SystemExit(f'Missing SDK asset: {name}')
        actual = sha256(archive)
        expected = checksum.read_text().split()[0]
        if actual != expected:
            raise SystemExit(f'Checksum mismatch for {name}')
        artifacts.append({
            'platform': platform['key'], 'os': platform['os'], 'arch': platform['arch'],
            'archiveExt': platform['archiveExt'], 'file': name,
            'url': f"{a.base_url.rstrip('/')}/{name}", 'sha256': actual,
            'size': archive.stat().st_size,
        })
    index = {
        'schemaVersion': 2, 'name': 'crashpad-build',
        'sdkVersion': sdk['sdkVersion'], 'releaseTag': a.release_tag,
        'licenseMode': sdk['licenseMode'], 'crashpadRevision': sdk['crashpadRevision'],
        'artifacts': artifacts,
    }
    a.output.write_text(json.dumps(index, indent=2, sort_keys=True) + '\n')

if __name__ == '__main__':
    main()
