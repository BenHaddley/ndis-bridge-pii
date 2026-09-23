#!/usr/bin/env python3
"""Extract repository QEMU tools locally on this Manjaro/Arch host; no sudo/install.

Downloads are checked against SHA-256 metadata in the host's existing pacman
sync databases. Does not refresh those databases or run package install hooks.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent / 'runtime'


def main():
    packages = ROOT / 'packages'
    tools = ROOT / 'tools'
    packages.mkdir(parents=True, exist_ok=True)
    tools.mkdir(parents=True, exist_ok=True)
    rows = subprocess.check_output(['pacman', '-Sp', '--print-format', '%n %l',
                                    'qemu-system-x86', 'qemu-img', 'libisoburn'], text=True).splitlines()
    metadata = {}
    for db in Path('/var/lib/pacman/sync').glob('*.db'):
        with tarfile.open(db) as archive:
            for member in archive:
                if not member.name.endswith('/desc'):
                    continue
                text = archive.extractfile(member).read().decode()
                fields = {}
                for block in text.split('\n\n'):
                    lines = block.strip().splitlines()
                    if len(lines) >= 2:
                        fields[lines[0]] = lines[1]
                if '%FILENAME%' in fields:
                    metadata[fields['%FILENAME%']] = fields

    def fetch(row):
        name, url = row.split(maxsplit=1)
        filename = unquote(Path(urlparse(url).path).name)
        expected = metadata[filename]['%SHA256SUM%']
        path = packages / filename
        if not path.exists():
            partial = path.with_name(path.name + '.part')
            subprocess.run(['curl', '--fail', '--location', '--retry', '2', '--max-time', '180',
                            '--silent', '--show-error', url, '-o', str(partial)], check=True)
            partial.replace(path)
        actual = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
        if actual != expected:
            raise RuntimeError(f'Package checksum mismatch: {path}')
        print(f'Verified {name}', flush=True)
        return {'name': name, 'url': url, 'sha256': actual, 'file': filename}

    with ThreadPoolExecutor(max_workers=4) as pool:
        verified = list(pool.map(fetch, rows))
    for item in verified:
        subprocess.run(['bsdtar', '-xf', str(packages / item['file']), '-C', str(tools),
                        '--no-same-owner', '--no-same-permissions', 'usr'], check=True)
    (ROOT / 'tools-manifest.json').write_text(json.dumps(verified, indent=2) + '\n')
    print(f'Local tools extracted to {tools}')


if __name__ == '__main__':
    main()
