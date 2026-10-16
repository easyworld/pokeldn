#!/usr/bin/env python3
"""Walk a Switch container (XCI/HFS0 or NSP/PFS0) and read its NCAs in place; nothing is extracted.

    ./.venv/bin/python tools/switch/xci_read.py CONTAINER [--type Program] [--exefs N --extract main]

A RomFS section's `level6` offset and section key are romfs_read.py's --romfs-offset and --title-key.
Header and key rules: docs/switch_re.md "Do not unpack the NSP".
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pokeldn.switch.container import (  # noqa: E402,F401
    CONTENT_TYPES, CRYPT_TYPES, FS_TYPES, HASH_TYPES, SECTOR, Container, CtrSection, load_keys, nca_header,
    parse_fs_header, section_key, xts_decrypt)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("container")
    ap.add_argument("--keys", default=os.path.expanduser("~/.switch/prod.keys"))
    ap.add_argument("--type", help="only NCAs of this content type, e.g. Program")
    ap.add_argument("--nca", help="only the NCA whose name starts with this")
    ap.add_argument("--exefs", type=int, metavar="N",
                    help="list the PartitionFS in section N of the selected NCA")
    ap.add_argument("--extract", help="with --exefs: the file in it to write out")
    ap.add_argument("--out", help="where --extract writes")
    args = ap.parse_args(argv)

    keys = load_keys(args.keys)
    if "header_key" not in keys:
        sys.exit(f"{args.keys}: no header_key")

    c = Container(args.container)
    entries = list(c.partitions())
    tickets = {name.split(":")[-1][:-4]: c.read(off, size)
               for name, off, size in entries if name.endswith(".tik")}
    for name, off, size in entries:
        if not name.endswith(".nca"):
            if not args.nca:
                print(f"{name:64s} {off:#014x} {size:>16,}")
            continue
        base = name.split(":")[-1]
        if args.nca and not base.startswith(args.nca):
            continue
        h = nca_header(c, off, keys["header_key"])
        if h is None:
            print(f"{name:64s} {off:#014x} {size:>16,}  (header did not decrypt)")
            continue
        ctype = CONTENT_TYPES.get(h["content_type"], str(h["content_type"]))
        if args.type and ctype.lower() != args.type.lower():
            continue
        key, keyname = section_key(h, keys, tickets)
        rights = h["rights_id"].hex()
        print(f"\n{name}  nca at {off:#014x}  {size:,} bytes")
        print(f"    {h['magic']}  {ctype}  title {h['title_id']:016x}  keygen {h['keygen']}"
              f"  sdk {'.'.join(map(str, h['sdk']))}")
        print(f"    rights id {rights}"
              f"{'  (zero: key-area crypto, no ticket needed)' if rights == '0' * 32 else ''}")
        print(f"    section key {key.hex() if key else f'?? no {keyname} in the keyset'}")
        for s in h["sections"]:
            line = (f"    section {s['index']}  {FS_TYPES.get(s['fs_type'], s['fs_type'])}"
                    f"  {HASH_TYPES.get(s['hash_type'], s['hash_type'])}"
                    f"  {CRYPT_TYPES.get(s['crypt'], s['crypt'])}"
                    f"  nca+{s['offset']:#x}..{s['offset'] + s['size']:#x}"
                    f"  ctr {s['ctr'].hex()}")
            if s["data_offset"] is not None:
                line += (f"\n              data at nca+{s['offset'] + s['data_offset']:#x}"
                         f"  ({s['data_size']:,} bytes)")
            print(line)

        if args.exefs is None:
            continue
        want = next((s for s in h["sections"] if s["index"] == args.exefs), None)
        if want is None:
            sys.exit(f"no section {args.exefs} in {base}")
        if want["crypt"] != 3:
            sys.exit(f"section {args.exefs} is {CRYPT_TYPES.get(want['crypt'])}, not CTR")
        sec = CtrSection(c, off, want, key)
        pfs_at = want["data_offset"]
        hdr = sec.read(pfs_at, 0x10)
        if hdr[:4] != b"PFS0":
            sys.exit(f"section {args.exefs} data is not a PFS0: {hdr[:4]!r}")
        count, str_size = struct.unpack_from("<II", hdr, 4)
        table = sec.read(pfs_at + 0x10, count * 0x18)
        strings = sec.read(pfs_at + 0x10 + count * 0x18, str_size)
        data = pfs_at + 0x10 + count * 0x18 + str_size
        print(f"    PFS0: {count} files")
        for i in range(count):
            foff, fsize, name_off = struct.unpack_from("<QQI", table, i * 0x18)
            fname = strings[name_off:strings.index(b"\0", name_off)].decode()
            print(f"        {fsize:12,}  {fname}")
            if args.extract == fname:
                out = args.out or fname
                with open(out, "wb") as fh:
                    left, at = fsize, data + foff
                    while left:
                        chunk = sec.read(at, min(left, 1 << 20))
                        fh.write(chunk)
                        at += len(chunk)
                        left -= len(chunk)
                print(f"        -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
