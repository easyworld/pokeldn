"""Rebuilds the AltStore / SideStore feed (.github/altstore/source.json) from the published releases,
so every version entry comes from the pokeldn-ios.ipa asset it points at. Run after a release, then
commit the file; players add https://raw.githubusercontent.com/Decryptu/pokeldn/main/.github/altstore/source.json.

    ./.venv/bin/python scripts/altstore_source.py
"""
import json
from pathlib import Path
import subprocess
import sys

REPO = "Decryptu/pokeldn"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".github" / "altstore" / "source.json"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
BUNDLE_ID = "io.pokeldn.app"
MIN_IOS = "15.0"   # examples/ios/build.py
TINT = "#47AEFA"   # gui/theme.py BLUE
SUBTITLE = "Trade and send gifts to Pokemon games over local wireless"
DESCRIPTION = (
    "pokeldn speaks Nintendo Switch local wireless to Pokemon games on a real console: trades in both "
    "roles, Mystery Gifts and more, for FireRed and LeafGreen through Legends Z-A.\n\n"
    "The radio is an ESP32 board running pokeldn's Bluetooth radio firmware; the phone talks to it over "
    "Bluetooth. You supply prod.keys dumped from your own console.")


def releases() -> list[dict]:
    out = subprocess.run(["gh", "api", f"repos/{REPO}/releases", "--paginate"], check=True,
                         capture_output=True, text=True).stdout
    return json.loads(out.replace("][", ","))


def versions(found: list[dict]) -> list[dict]:
    entries = []
    for release in found:
        if release["draft"]:
            continue
        ipa = next((a for a in release["assets"] if a["name"] == "pokeldn-ios.ipa"), None)
        if ipa is None:
            continue
        version = release["tag_name"].removeprefix("v")
        entries.append({"version": version, "buildVersion": version, "date": release["published_at"],
                        "localizedDescription": release["body"] or "", "downloadURL": ipa["browser_download_url"],
                        "size": ipa["size"], "minOSVersion": MIN_IOS})
    return entries


def source(entries: list[dict]) -> dict:
    icon = f"{RAW}/gui/assets/icon.png"
    app = {"name": "pokeldn", "bundleIdentifier": BUNDLE_ID, "developerName": "Decryptu",
           "subtitle": SUBTITLE, "localizedDescription": DESCRIPTION, "iconURL": icon, "tintColor": TINT,
           "category": "games", "versions": entries}
    if entries:   # the app-level copy of the newest version, which older clients read
        newest = entries[0]
        app.update(version=newest["version"], versionDate=newest["date"],
                   versionDescription=newest["localizedDescription"], downloadURL=newest["downloadURL"],
                   size=newest["size"])
    return {"name": "pokeldn", "identifier": BUNDLE_ID, "sourceURL": f"{RAW}/.github/altstore/source.json",
            "subtitle": SUBTITLE, "description": DESCRIPTION, "iconURL": icon,
            "website": f"https://github.com/{REPO}", "tintColor": TINT, "apps": [app]}


def main() -> int:
    entries = versions(releases())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(source(entries), indent=2) + "\n")
    print(f"{OUT}: {len(entries)} versions" + (f", newest {entries[0]['version']}" if entries else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
