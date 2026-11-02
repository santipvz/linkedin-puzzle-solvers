from __future__ import annotations

import json
from pathlib import Path
import struct
import zipfile

import pytest
from PIL import Image

from scripts.package_extension import RUNTIME_FILES, build


@pytest.mark.parametrize('browser', ('chrome', 'firefox'))
def test_repository_extension_builds_with_real_installation_assets(tmp_path: Path, browser: str) -> None:
    package = build(tmp_path / f'{browser}.zip')
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        for size in (16, 32, 48, 128):
            with archive.open(manifest['icons'][str(size)]) as file:
                with Image.open(file) as icon:
                    assert icon.format == 'PNG'
                    assert icon.size == (size, size)
                    icon.verify()
        for filename in RUNTIME_FILES:
            assert archive.read(filename)


def sources(tmp_path: Path) -> Path:
    source = tmp_path / 'extension'
    (source / 'assets').mkdir(parents=True)
    manifest = json.loads(Path('extension/manifest.json').read_text())
    manifest['icons'] = {}
    for size in (16, 32, 48, 128):
        filename = f'assets/icon{size}.png'
        manifest['icons'][str(size)] = filename
        # Header validation fixture; actual publication assets are rendered PNGs.
        (source / filename).write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + struct.pack('>II', size, size))
    (source / 'manifest.json').write_text(json.dumps(manifest))
    for name in RUNTIME_FILES:
        (source / name).write_text('// runtime fixture')
    (source / 'assets' / 'README.md').write_text('Asset provenance')
    (source / '.env').write_text('must-not-ship')
    (source / 'tests').mkdir()
    (source / 'tests' / 'debug.js').write_text('must-not-ship')
    return source


def test_chrome_package_excludes_development_files_and_firefox_config(tmp_path: Path) -> None:
    source = sources(tmp_path)
    package = build(tmp_path / 'chrome.zip', source=source)
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['background'] == {'service_worker': 'background.js'}
        assert 'browser_specific_settings' not in manifest
        assert '<all_urls>' in manifest['host_permissions']  # First-use capture from the in-page button.
        assert 'tabs' not in manifest['permissions']
        assert '.env' not in archive.namelist()
        assert not any(name.startswith('tests/') for name in archive.namelist())
        assert 'ASSET_NOTICES.md' in archive.namelist()


def test_firefox_package_preserves_background_scripts(tmp_path: Path) -> None:
    package = build(tmp_path / 'firefox.zip', browser='firefox', source=sources(tmp_path))
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert 'service_worker' not in manifest['background']
        assert manifest['background']['scripts']
        assert manifest['browser_specific_settings']['gecko']['id']


def test_missing_publication_icons_block_an_incomplete_store_package(tmp_path: Path) -> None:
    source = sources(tmp_path)
    (source / 'assets' / 'icon128.png').unlink()
    with pytest.raises(FileNotFoundError):
        build(tmp_path / 'invalid.zip', source=source)
    assert not (tmp_path / 'invalid.zip').exists()
