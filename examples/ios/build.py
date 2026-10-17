"""Builds the iOS app without an Xcode project: BeeWare's Python for iOS, the repository's code, the
pure-Python packages, the C libraries the radio needs, then the bundle, an unsigned .ipa for
AltStore or SideStore to sign, or an install on a booted simulator. Run from the repository root:

    ./.venv/bin/python examples/ios/build.py [--device] [--install]
"""
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = HERE / 'build'
SUPPORT = HERE / 'support'
PYTHON_RELEASE = '3.13-b16'   # beeware/Python-Apple-support
PYTHON_ASSET = 'Python-3.13-iOS-support.b16.tar.gz'
BUNDLE_ID = 'io.pokeldn.app'
MIN_IOS = '15.0'
# Pure-Python packages, pinned as examples/android/build.gradle pins them; fastapi (pydantic-core)
# has no iOS build and examples/android/src/python/fastapi stands in for it.
PACKAGES = ('trio==0.33.0', 'attrs==26.1.0', 'outcome==1.3.0.post0', 'sortedcontainers==2.4.0',
            'sniffio==1.3.1', 'idna==3.20', 'pyserial==3.5', 'websockets==17.1', 'certifi==2026.7.22',
            'flet==1.0.2', 'flet-web==1.0.2', 'repath==0.9.0', 'six==1.17.0', 'oauthlib==4.0.0',
            'httpx==0.28.1', 'httpcore==1.0.9', 'anyio==4.15.1', 'typing_extensions==4.16.0',
            'starlette==1.7.0', 'uvicorn==0.54.0', 'h11==0.16.0', 'click==8.5.0', 'packaging==25.0')
NATIVE = ('pycryptodome==3.23.0', 'zstandard==0.25.0')
PRIVATE = ('.keys', '.pk3', '.ek3', '.sav', '.gba')


def run(*cmd, **kw):
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def support() -> Path:
    framework = SUPPORT / 'Python.xcframework'
    if not framework.is_dir():
        SUPPORT.mkdir(exist_ok=True)
        run('gh', 'release', 'download', PYTHON_RELEASE, '-R', 'beeware/Python-Apple-support',
            '-p', PYTHON_ASSET, '--clobber', cwd=SUPPORT)
        run('tar', 'xzf', PYTHON_ASSET, cwd=SUPPORT)
    return framework


class Target:
    def __init__(self, device: bool):
        self.device = device
        self.sdk = 'iphoneos' if device else 'iphonesimulator'
        self.slice = 'ios-arm64' if device else 'ios-arm64_x86_64-simulator'
        self.triple = f'arm64-apple-ios{MIN_IOS}' + ('' if device else '-simulator')
        self.platform = 'iPhoneOS' if device else 'iPhoneSimulator'
        self.soabi = 'iphoneos' if device else 'iphonesimulator'
        self.wheel_platform = f'ios_13_0_arm64_{self.soabi}'

    def clang(self, *args):
        run('xcrun', '-sdk', self.sdk, 'clang', '-target', self.triple, *args)


def stage_code(app: Path) -> None:
    """The repository's tracked and untracked code and package data (examples/android/stage.py)."""
    packages = ('pokeldn', 'bin', 'config', 'gui', 'docs', 'vendor/LDN/ldn')
    listed = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others',
                             '--exclude-standard', '--', *packages], check=True, capture_output=True)
    for name in listed.stdout.decode().split('\0'):
        if not name:
            continue
        relative = Path(name)
        if relative.name == 'prod.keys' or relative.suffix in PRIVATE:
            raise ValueError('Private input cannot be staged: ' + name)
        if not (ROOT / relative).is_file():
            continue
        target = app / (Path('ldn') / relative.relative_to('vendor/LDN/ldn')
                        if relative.is_relative_to('vendor/LDN/ldn') else relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    shutil.copytree(ROOT / 'examples/android/src/python/fastapi', app / 'fastapi',
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(HERE / 'src/python/ios_gui.py', app / 'ios_gui.py')


# msgpack without its C extension, built from its sdist as examples/android/build.py builds it.
LOCAL = (('msgpack==1.2.3', {'MSGPACK_PUREPYTHON': '1'}),)


def pure_packages(target: Target, packages: Path) -> None:
    wheels = BUILD / 'wheels'
    wheels.mkdir(parents=True, exist_ok=True)
    for spec, extra in LOCAL:
        name = spec.split('==')[0]
        if not list(wheels.glob(f'{name}-*.whl')):
            run(sys.executable, '-m', 'pip', 'wheel', '--quiet', '--no-deps', '--no-binary', ':all:',
                '-w', wheels, spec, env={**os.environ, **extra})
        run(sys.executable, '-m', 'pip', 'install', '--quiet', '--no-deps', '--no-compile', '--target',
            packages, next(wheels.glob(f'{name}-*.whl')))
    run(sys.executable, '-m', 'pip', 'install', '--quiet', '--no-deps', '--no-compile', '--only-binary', ':all:',
        '--platform', target.wheel_platform, '--platform', 'any', '--python-version', '3.13',
        '--implementation', 'cp', '--target', packages, *PACKAGES)


def crypto_extensions(setup_py: Path):
    """(module, sources, include dirs, macros) for each Extension(...) pycryptodome's setup.py lists
    with literal arguments; the file itself runs setup() and probes the host's compiler."""
    import ast
    for node in ast.walk(ast.parse(setup_py.read_text())):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'Extension':
            try:
                name = ast.literal_eval(node.args[0])
                kw = {k.arg: ast.literal_eval(k.value) for k in node.keywords
                      if k.arg in ('sources', 'include_dirs', 'define_macros')}
            except ValueError:
                continue
            yield name, kw.get('sources', []), kw.get('include_dirs', []), kw.get('define_macros', [])


def native_packages(target: Target, framework: Path, packages: Path, work: Path) -> None:
    """pycryptodome's ctypes libraries and zstandard's extension, compiled for the target; neither
    has an iOS wheel on PyPI."""
    sources = work / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    for spec in NATIVE:
        name = spec.split('==')[0]
        if not list(sources.glob(f'{name}-*')):
            run(sys.executable, '-m', 'pip', 'download', '--quiet', '--no-deps', '--no-binary', ':all:',
                '-d', sources, spec)
            archive = next(sources.glob(f'{name}-*.tar.gz'))
            run('tar', 'xzf', archive, '-C', sources)
    include = framework / target.slice / 'include' / 'python3.13'
    cflags = ['-O2', '-fPIC', '-dynamiclib', '-undefined', 'dynamic_lookup']

    crypto_src = next(p for p in sources.glob('pycryptodome-*') if p.is_dir())
    shutil.copytree(crypto_src / 'lib' / 'Crypto', packages / 'Crypto', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('*.c', '*.h', 'SelfTest'))
    for name, sources_, includes, macros in crypto_extensions(crypto_src / 'setup.py'):
        if any(x in name for x in ('aesni', 'clmul')):   # x86 only
            continue
        out = packages / (name.replace('.', '/') + f'.cpython-313-{target.soabi}.so')
        out.parent.mkdir(parents=True, exist_ok=True)
        flags = [f'-D{k}' + ('' if v is None else f'={v}') for k, v in macros]
        flags += [f'-I{crypto_src / d}' for d in includes]
        target.clang(*cflags, *flags, '-DHAVE_STDINT_H', '-DPYCRYPTO_LITTLE_ENDIAN', '-DSYS_BITS=64',
                     '-DHAVE_UINT128', '-DHAVE_POSIX_MEMALIGN', '-I', include, '-o', out, *[crypto_src / f for f in sources_])

    zstd_src = next(p for p in sources.glob('zstandard-*') if p.is_dir())
    shutil.copytree(zstd_src / 'zstandard', packages / 'zstandard', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('*.c', '*.h'))
    # setup_zstd.py: the bundled zstd compiled into backend_c.c as one file.
    target.clang(*cflags, '-DZSTD_SINGLE_FILE', '-DZSTDLIB_VISIBLE=', '-DZDICTLIB_VISIBLE=',
                 '-DZSTDERRORLIB_VISIBLE=', '-fvisibility=hidden', '-I', include, '-I', zstd_src / 'zstd',
                 '-I', zstd_src / 'c-ext', '-o',
                 packages / 'zstandard' / f'backend_c.cpython-313-{target.soabi}.so',
                 zstd_src / 'c-ext' / 'backend_c.c')


def frameworks(app_root: Path, base: Path) -> None:
    """Every .so under `base` becomes Frameworks/<module>.framework with a .fwork file in its place,
    as Python.xcframework/build/utils.sh does; iOS loads code only from frameworks."""
    template = SUPPORT / 'Python.xcframework' / 'build' / 'iOS-dylib-Info-template.plist'
    for so in sorted(base.rglob('*.so')):
        module = '.'.join(so.relative_to(base).with_suffix('').parts).split('.cpython')[0]
        module = module.split('.abi3')[0]
        folder = app_root / 'Frameworks' / f'{module}.framework'
        folder.mkdir(parents=True, exist_ok=True)
        info = plistlib.loads(template.read_bytes())
        info.update(CFBundleExecutable=module, CFBundleIdentifier=f'{BUNDLE_ID}.{module}'.replace('_', '-'))
        (folder / 'Info.plist').write_bytes(plistlib.dumps(info))
        shutil.move(so, folder / module)
        relative = folder.relative_to(app_root) / module
        so.with_suffix('.fwork').write_text(str(relative))
        (folder / f'{module}.origin').write_text(str(so.with_suffix('.fwork').relative_to(app_root)))


def info_plist(target: Target) -> dict:
    import re
    version = re.search(r'__version__ = "([^"]+)"', (ROOT / 'pokeldn' / '__init__.py').read_text())[1]
    return {
        'CFBundleIdentifier': BUNDLE_ID, 'CFBundleName': 'pokeldn', 'CFBundleDisplayName': 'pokeldn',
        'CFBundleExecutable': 'pokeldn', 'CFBundlePackageType': 'APPL', 'CFBundleVersion': version,
        'CFBundleShortVersionString': version, 'CFBundleSupportedPlatforms': [target.platform],
        'MinimumOSVersion': MIN_IOS, 'UIDeviceFamily': [1, 2], 'UILaunchScreen': {},
        'UIRequiredDeviceCapabilities': ['arm64'], 'LSRequiresIPhoneOS': True,
        'NSBluetoothAlwaysUsageDescription': 'pokeldn talks to its radio board over Bluetooth.',
        'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
        'CFBundleIcons': {'CFBundlePrimaryIcon': {'CFBundleIconFiles': ['AppIcon60x60', 'AppIcon76x76'],
                                                  'CFBundleIconName': 'AppIcon'}},
        'UIFileSharingEnabled': True, 'LSSupportsOpeningDocumentsInPlace': True,
        'UISupportedInterfaceOrientations': ['UIInterfaceOrientationPortrait',
                                             'UIInterfaceOrientationLandscapeLeft',
                                             'UIInterfaceOrientationLandscapeRight'],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--device', action='store_true', help='build for iPhone and write an unsigned .ipa')
    parser.add_argument('--install', action='store_true', help='install and launch on the booted simulator')
    args = parser.parse_args()
    target = Target(args.device)
    framework = support()
    work = BUILD / target.sdk
    bundle = work / 'pokeldn.app'
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)

    target.clang('-fobjc-arc', '-O2', '-F', framework / target.slice, '-framework', 'Python',
                 '-framework', 'UIKit', '-framework', 'CoreGraphics', '-framework', 'WebKit', '-framework', 'CoreBluetooth', '-framework', 'UniformTypeIdentifiers',
                 '-Xlinker', '-rpath', '-Xlinker', '@executable_path/Frameworks',
                 '-o', bundle / 'pokeldn', HERE / 'src' / 'main.m')
    (bundle / 'Info.plist').write_bytes(plistlib.dumps(info_plist(target)))
    for name, size in (('AppIcon60x60@2x.png', 120), ('AppIcon60x60@3x.png', 180), ('AppIcon76x76@2x~ipad.png', 152)):
        run('sips', '-z', size, size, ROOT / 'gui' / 'assets' / 'icon.png', '--out', bundle / name,
            stdout=subprocess.DEVNULL)
    shutil.copytree(framework / target.slice / 'Python.framework', bundle / 'Frameworks' / 'Python.framework',
                    symlinks=True)
    lib = bundle / 'python' / 'lib'
    shutil.copytree(framework / 'lib', lib, ignore=shutil.ignore_patterns('libpython*.dylib'))
    shutil.copytree(framework / target.slice / 'lib-arm64', lib, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('libpython*.dylib'))
    stage_code(bundle / 'app')
    packages = bundle / 'app_packages'
    pure_packages(target, packages)
    native_packages(target, framework, packages, work)
    for base in (lib / 'python3.13' / 'lib-dynload', packages):
        frameworks(bundle, base)

    if not args.device:
        for fw in sorted((bundle / 'Frameworks').iterdir()):
            run('codesign', '--force', '--sign', '-', '--timestamp=none', fw)
        run('codesign', '--force', '--sign', '-', '--timestamp=none', bundle)
    print('App:', bundle)
    if args.device:
        ipa = BUILD / 'pokeldn-ios.ipa'
        with zipfile.ZipFile(ipa, 'w', zipfile.ZIP_DEFLATED) as z:
            for path in sorted(bundle.rglob('*')):
                if path.is_symlink() or path.is_file():
                    z.write(path, Path('Payload') / path.relative_to(work))
        print('IPA (unsigned):', ipa)
    if args.install:
        run('xcrun', 'simctl', 'install', 'booted', bundle)
        run('xcrun', 'simctl', 'launch', 'booted', BUNDLE_ID)
    return 0


if __name__ == '__main__':
    sys.exit(main())
