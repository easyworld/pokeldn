from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEST = HERE / 'staged'
if DEST.exists():
    shutil.rmtree(DEST)
DEST.mkdir()
packages = ('pokeldn', 'bin', 'config', 'gui', 'docs', 'vendor/LDN/ldn')
result = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', *packages],
                        check=True, capture_output=True)
for filename in result.stdout.decode().split('\0'):
    if not filename:
        continue
    relative = Path(filename)
    if relative.name == 'prod.keys' or relative.suffix in ('.keys', '.pk3', '.ek3', '.sav', '.gba'):
        raise ValueError('Private input cannot be staged: ' + filename)
    target = DEST / (Path('ldn') / relative.relative_to('vendor/LDN/ldn')
                     if relative.is_relative_to('vendor/LDN/ldn') else relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, target)
# Chaquopy extracts packages to real files and runpy runs only real files: the launchers become one.
(DEST / 'bin' / '__init__.py').write_text('')
# The firmware images the release build writes (gui/board.py); absent from a fresh checkout.
for image in (ROOT / 'gui' / 'firmware').glob('*.bin'):
    (DEST / 'gui' / 'firmware').mkdir(parents=True, exist_ok=True)
    shutil.copy2(image, DEST / 'gui' / 'firmware' / image.name)
# Unicorn's Python binding; its library is built for Android by build_native.py.
import unicorn
binding = Path(unicorn.__file__).parent
shutil.copytree(binding, DEST / 'unicorn', ignore=shutil.ignore_patterns('lib', 'include', '__pycache__'))
for filename in ('test_esp32.py', 'test_host_end_to_end.py'):
    shutil.copy2(ROOT / 'tests' / filename, DEST / ('android_' + filename))
print('Staged tracked repository code and package data:', DEST)
