"""Package and run the Chinese pack against an upstream checkout with isolated settings."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "scripts/zh_hans_upstream.patch"


def prepare(upstream, data):
    """Apply the reviewed display-only patch, without overwriting unrelated local edits."""
    command = ["git", "apply", "--check", str(PATCH)]
    if subprocess.run(command, cwd=upstream, capture_output=True).returncode == 0:
        subprocess.run(["git", "apply", str(PATCH)], cwd=upstream, check=True)
    elif subprocess.run(["git", "apply", "--reverse", "--check", str(PATCH)],
                        cwd=upstream, capture_output=True).returncode != 0:
        raise SystemExit("The display patch does not fit this checkout. Review its changes before proceeding.")
    version = tomllib.loads((ROOT / "examples/plugins/zh_hans/plugin.toml").read_text(encoding="utf-8"))["version"]
    output = ROOT / f"dist/easyworld-zh-hans-{version}.pokeplugin"
    env = {**os.environ, "POKELDN_DATA": str(data), "POKELDN_PLUGINS": "", "PYTHONIOENCODING": "utf-8"}
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "scripts/pack_plugin.py", str(ROOT / "examples/plugins/zh_hans"),
                    "-o", str(output)], cwd=upstream, env=env, check=True)
    code = '''import sys
from pokeldn.app import plugin_store, settings
package = plugin_store.read(sys.argv[1])
plugin_store.install(package)
chosen = settings.load()
chosen.app_language = package.id
chosen.plugins = list(dict.fromkeys([*chosen.plugins, package.id]))
chosen.save()
print('Installed:', package.id, package.version)
'''
    subprocess.run([sys.executable, "-c", code, str(output)], cwd=upstream, env=env, check=True)
    return env


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--data", type=Path, default=ROOT / "build/language-preview-data")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    env = prepare(upstream, args.data.resolve())
    if not args.prepare_only:
        raise SystemExit(subprocess.call([sys.executable, "gui/main.py"], cwd=upstream, env=env))
