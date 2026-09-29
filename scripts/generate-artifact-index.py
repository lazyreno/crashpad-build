#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release-assets', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--release-tag', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sdk = json.loads((root / 'config/sdk-version.json').read_text())
    source_lock = json.loads((root / 'config/source-lock.json').read_text())
    matrix = json.loads((root / 'config/platform-matrix.json').read_text())['platforms']
    artifacts = []
    for platform in matrix:
        name = f"crashpad-sdk-{platform['os']}-{platform['arch']}.zip"
        archive = args.release_assets / name
        checksum = args.release_assets / f'{name}.sha256'
        if not archive.exists() or not checksum.exists():
            raise SystemExit(f'Missing SDK asset: {name}')
        actual = sha256(archive)
        expected = checksum.read_text().split()[0]
        if actual != expected:
            raise SystemExit(f'Checksum mismatch for {name}')
        artifacts.append({
            'os': platform['os'], 'arch': platform['arch'],
            'minimumSystemVersion': platform['minimumSystemVersion'],
            'archiveExt': platform['archiveExt'], 'file': name,
            'url': f"{args.base_url.rstrip('/')}/{name}", 'sha256': actual,
            'size': archive.stat().st_size,
        })
    index = {
        'schemaVersion': 2, 'name': 'crashpad-build',
        'sdkVersion': sdk['sdkVersion'], 'releaseTag': args.release_tag,
        'licenseMode': sdk['licenseMode'], 'crashpadRevision': source_lock['crashpadRevision'],
        'artifacts': artifacts,
    }
    args.output.write_text(json.dumps(index, indent=2, sort_keys=True) + '\n')

if __name__ == '__main__':
    main()
