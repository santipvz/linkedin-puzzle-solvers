#!/usr/bin/env python3
"""Build a minimal Chrome/Firefox ZIP from the checked-out extension sources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = (
    'api_config.js', 'background.js', 'content.js', 'popup.css', 'popup.html',
    'popup.js', 'puzzle_registry.js', 'wend_paths.js',
)


def build(output: Path, browser: str = 'chrome', source: Path = ROOT / 'extension') -> Path:
    manifest = json.loads((source / 'manifest.json').read_text())
    if browser == 'chrome':
        manifest.pop('browser_specific_settings', None)
        manifest['background'].pop('scripts', None)
    elif browser == 'firefox':
        manifest['background'].pop('service_worker', None)
    else:
        raise ValueError('Choose chrome or firefox.')
    if 'tabs' in manifest.get('permissions', ()):
        raise ValueError('Broad browsing-history access is not needed by this extension.')
    if len(manifest.get('description', '')) > 132:
        raise ValueError('The manifest description exceeds 132 characters.')
    for size in (16, 32, 48, 128):
        filename = manifest.get('icons', {}).get(str(size))
        if not filename:
            raise ValueError(f'Missing {size}px installation icon.')
        data = (source / filename).read_bytes()
        if data[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', data[16:24]) != (size, size):
            raise ValueError(f'Invalid {size}px PNG icon: {filename}')
    files = [source / name for name in RUNTIME_FILES]
    files += sorted(p for p in (source / 'assets').rglob('*') if p.is_file() and p.suffix in {'.svg', '.png'})
    for file in files:
        if not file.is_file():
            raise ValueError(f'Missing runtime file: {file.name}')
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(manifest, indent=2) + '\n')
        for file in files:
            archive.write(file, file.relative_to(source).as_posix())
        archive.write(ROOT / 'LICENSE', 'LICENSE.txt')
        archive.write(source / 'assets' / 'README.md', 'ASSET_NOTICES.md')
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', choices=('chrome', 'firefox'), default='chrome')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    version = json.loads((ROOT / 'extension' / 'manifest.json').read_text())['version']
    output = args.output or ROOT / 'dist' / f'puzzle-solver-{args.browser}-{version}.zip'
    print(build(output, args.browser))


if __name__ == '__main__':
    main()
