"""Scarlet 4.0.0's own code and data the battle server runs on, taken from the user's dump: the static
image as the loader leaves it and the five data tables (docs/sv_raid.md, Reproducing a round).

`prepare(update, base, keys, cache)` reads the v4.0.0 update NSP's ExeFS and the update's RomFS over
the base game's (XCI or NSP), decrypted with the user's prod.keys, and writes the image and the tables
under `cache`; `load(cache)` reads them back. Nothing here writes anywhere but `cache`.

The image: main at MAIN with its RELATIVE relocations, the SDK at MAIN + SDK with its own, and every
GLOB_DAT / JUMP_SLOT / ABS64 slot bound to the first module exporting the symbol, main then the SDK.
"""

import json
import os
import struct
from pathlib import Path

from pokeldn.sv.battle.engine import session
from pokeldn.switch import container, nso, trpfs

TITLE_SCARLET = 0x0100A3D008C5C000
MAIN = 0x8504000                    # main's load base in the snapshots' process
SDK = 0x4E6D000                     # the SDK module, from main
MAIN_MODULE_ID = "421c5411b487eb4d049dd065fec9547773e8e598"     # Scarlet 4.0.0's main NSO build id
OODLE = 0xCC8750                    # OodleLZ_Decompress in main
TABLES = tuple(t[4] for t in session.TABLES) + (session.IDHASH[4],)     # the romfs files build_tables reads
FORMAT = 1                          # the cache layout; a different one is rebuilt


class Game:
    """The static image by page and the data tables by romfs path."""

    def __init__(self, main, sdk, tables):
        self.main, self.sdk, self.tables = main, sdk, tables

    def static_page(self, p):
        """-> the 4096 bytes the image holds at address `p`, or None outside it."""
        off = p - MAIN
        if 0 <= off < len(self.main):
            return self.main[off:off + 0x1000].ljust(0x1000, b"\0")
        if SDK <= off < SDK + len(self.sdk):
            return self.sdk[off - SDK:off - SDK + 0x1000].ljust(0x1000, b"\0")
        return None


def bind(main_layout, sdk_layout):
    """-> (main, sdk) images relocated at MAIN and MAIN + SDK, their symbol slots bound."""
    main = nso.load(main_layout, MAIN)
    sdk = nso.load(sdk_layout, MAIN + SDK)
    if MAIN + len(main) > MAIN + SDK:
        raise ValueError(f"main spans 0x{len(main):x} bytes, past the SDK at main+0x{SDK:x}")
    mexp, mrel = nso.symbols(bytes(main_layout))
    sexp, srel = nso.symbols(bytes(sdk_layout))

    def resolve(name):
        if name in mexp:
            return MAIN + mexp[name]
        if name in sexp:
            return MAIN + SDK + sexp[name]
        return None
    for img, rel in ((main, mrel), (sdk, srel)):
        for off, name, add in rel:
            v = resolve(name)
            if v is not None and off + 8 <= len(img):
                struct.pack_into("<Q", img, off, (v + add) & 0xFFFFFFFFFFFFFFFF)
    return bytes(main), bytes(sdk)


def prepare(update, base, keys, cache, title_id=TITLE_SCARLET):
    """Read the image and the tables out of the user's dump (the v4.0.0 update and the base game, read
    in place with prod.keys at `keys`) into the directory `cache`; -> load(cache)."""
    k = container.load_keys(keys)
    if "header_key" not in k:
        raise ValueError(f"{keys}: no header_key")
    exe = container.exefs(update, k, title_id)
    main_nso = exe["main"]
    found = nso.module_id(main_nso).hex().rstrip("0")
    if found != MAIN_MODULE_ID.rstrip("0"):
        raise ValueError(f"{update}: main is build {found}, not Scarlet 4.0.0's {MAIN_MODULE_ID}")
    main_layout = nso.layout(main_nso)
    main, sdk = bind(main_layout, nso.layout(exe["sdk"]))
    virt, romfs = container.open_update_romfs(update, base, k, title_id=title_id)
    try:
        fs = trpfs.Trpfs(trpfs.Source.romfs(romfs))
        oodle = trpfs.Oodle(bytes(main_layout), OODLE)
        tables = {path: fs.read(trpfs.fnv1a64(path), oodle) for path in TABLES}
    finally:
        virt.close()
    cache = Path(cache)
    for path, data in tables.items():
        out = cache / "romfs" / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    (cache / "main.bin").write_bytes(main)
    (cache / "sdk.bin").write_bytes(sdk)
    (cache / "game.json").write_text(json.dumps({"format": FORMAT, "main": MAIN_MODULE_ID}))
    return load(cache)


def ready(cache):
    """Whether `cache` holds what prepare writes, in this layout."""
    try:
        meta = json.loads((Path(cache) / "game.json").read_text())
    except (OSError, ValueError):
        return False
    return meta == {"format": FORMAT, "main": MAIN_MODULE_ID} and all(
        os.path.exists(os.path.join(cache, *p)) for p in [("main.bin",), ("sdk.bin",)]
        + [("romfs", t) for t in TABLES])


def load(cache):
    """-> the Game `prepare` wrote under `cache`."""
    if not ready(cache):
        raise FileNotFoundError(f"{cache}: no Scarlet 4.0.0 image and tables (prepare them from the dump)")
    cache = Path(cache)
    return Game((cache / "main.bin").read_bytes(), (cache / "sdk.bin").read_bytes(),
                {p: (cache / "romfs" / p).read_bytes() for p in TABLES})


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Read Scarlet 4.0.0's image and battle tables out of the dump.")
    ap.add_argument("--update", required=True, help="the v4.0.0 update NSP")
    ap.add_argument("--base", required=True, help="the base game's XCI or NSP")
    ap.add_argument("--keys", required=True, help="prod.keys")
    ap.add_argument("--cache", required=True, help="the directory the image and tables are written to")
    args = ap.parse_args(argv)
    Path(args.cache).mkdir(parents=True, exist_ok=True)
    g = prepare(args.update, args.base, args.keys, args.cache)
    print(f"{args.cache}: main 0x{len(g.main):x} bytes, sdk 0x{len(g.sdk):x}, {len(g.tables)} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
