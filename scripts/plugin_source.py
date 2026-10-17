"""Writes a plugin source listing (docs/plugins.md, Sources) from .pokeplugin packages, checking each
one as the app would.

    python scripts/plugin_source.py dist/*.pokeplugin -o pokeldn-source.json --name "My plugins" \\
        --download "https://github.com/OWNER/REPO/releases/download/{id}-{version}/{file}"

A package already listed at a lower version is replaced; other entries in the output are kept.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pokeldn import plugins  # noqa: E402
from pokeldn.app import plugin_sources, plugin_store  # noqa: E402


def entry(path: str, download: str, icon: str) -> dict:
    package = plugin_store.read(path)
    with open(path, "rb") as source:
        data = source.read()
    fill = {"id": package.id, "version": package.version, "file": os.path.basename(path)}
    out = {"id": package.id, "name": package.name, "version": package.version,
           "description": package.description, "author": package.author,
           "api": plugins.api_text(package.api), "download": download.format(**fill),
           "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    if package.homepage:
        out["homepage"] = package.homepage
    if icon and package.icon:
        out["icon"] = icon.format(**fill)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("packages", nargs="+", help=".pokeplugin files")
    parser.add_argument("-o", "--output", default=plugin_sources.FILE)
    parser.add_argument("--name", help="the source's name; default: the one already in the output")
    parser.add_argument("--homepage", help="the source's page")
    parser.add_argument("--download", required=True,
                        help="each package's address; {id}, {version} and {file} are filled in")
    parser.add_argument("--icon", default="", help="each plugin's icon address, used when the package has one")
    args = parser.parse_args(argv)
    try:
        with open(args.output, encoding="utf-8") as existing:
            listing = json.load(existing)
    except FileNotFoundError:
        listing = {}
    listing = {"schema": plugin_sources.SCHEMA, "name": args.name or listing.get("name", ""),
               "homepage": args.homepage or listing.get("homepage", ""), "plugins": listing.get("plugins", [])}
    for path in args.packages:
        try:
            item = entry(path, args.download, args.icon)
        except plugin_store.PackageError as error:
            parser.exit(1, f"{path}: not installable: {error}\n")
        if not plugin_sources.allowed(item["download"]):
            parser.exit(1, f"{item['download']} is not an HTTPS address\n")
        old = next((p for p in listing["plugins"] if p.get("id") == item["id"]), None)
        if old is not None and plugin_store._version(str(old.get("version", ""))) > plugin_store._version(item["version"]):
            print(f"{item['id']}: the listing already has the newer {old['version']}; {item['version']} skipped")
            continue
        listing["plugins"] = [p for p in listing["plugins"] if p.get("id") != item["id"]] + [item]
        print(f"{item['id']} {item['version']}: {item['download']}")
    listing["plugins"].sort(key=lambda p: str(p.get("id")))
    plugin_sources.parse(args.output, json.dumps(listing).encode())     # refuses what the app would
    with open(args.output, "w", encoding="utf-8") as out:
        json.dump(listing, out, indent=2, ensure_ascii=False)
        out.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
