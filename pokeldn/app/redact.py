"""Log lines with what identifies a player masked, so a log can be shared or filmed: the home folder in
paths, the device half of MAC addresses, trainer names and nicknames, trainer IDs. What a report
needs stays: species, levels, steps, errors, the vendor half of a MAC. docs/gui.md, Private logs."""
import os
import re

MASK = "***"
OURS = {"POKELDN", "PKLDN"}   # the program's own default trainer: no one's name
MAC = re.compile(r"\b([0-9A-Fa-f]{2}([:-]))((?:[0-9A-Fa-f]{2}\2){1}[0-9A-Fa-f]{2})\2"
                 r"[0-9A-Fa-f]{2}\2[0-9A-Fa-f]{2}\2[0-9A-Fa-f]{2}\b")
HOMES = (re.compile(r"/Users/[^/\s'\"]+"), re.compile(r"/home/[^/\s'\"]+"),
         re.compile(r"[A-Za-z]:\\Users\\[^\\\s'\"]+", re.I),
         re.compile(r"(/private)?/var/mobile/Containers/(Data|Shared/AppGroup|Bundle)/Application/[0-9A-F-]{36}"))
# A name after one of these keys, quoted: 'ot_name': 'Name', OT='Name', nickname="Name".
NAME_KEYS = r"(?:ot_name|ht_name|ot|OT|nickname|nick|trainer|trainer_name|player|player_name|name)"
QUOTED = re.compile(r"""(\b%s['"]?\s*[:=]\s*b?)(['"])(.*?)\2""" % NAME_KEYS)   # b'...' as Python prints bytes
BARE_MAC = re.compile(r"(\bmac\s*[:=]\s*)([0-9A-Fa-f]{6})[0-9A-Fa-f]{6}\b")
IDS = re.compile(r"""(\b(?:TID|SID|tid|sid|trainer_id|trainerId|tid16|sid16)['"]?\s*[:=]\s*)(0x[0-9A-Fa-f]+|\d+)""")


class Redactor:
    """One per run: a name masked once is masked wherever it appears again, in any later line."""

    def __init__(self, names=()):
        self.names = {n for n in names if len(n) >= 3 and n.upper() not in OURS}

    def __call__(self, line: str) -> str:
        home = os.path.expanduser("~")
        if len(home) > 1:
            line = line.replace(home, "~")
        for pattern in HOMES:
            line = pattern.sub(lambda m: "~" if not m.group(0).startswith(("/var", "/private")) else "<app>", line)
        line = MAC.sub(lambda m: m.group(1) + m.group(3) + m.group(2) + "**" + m.group(2) + "**" + m.group(2) + "**", line)
        line = BARE_MAC.sub(lambda m: m.group(1) + m.group(2) + "******", line)

        def name(m):
            key, value = m.group(1), m.group(3)
            if not value or value.upper() in OURS:
                return m.group(0)
            # A trainer's name is remembered for later lines; a nickname is often the species' own name.
            if len(value) >= 3 and "nick" not in key:
                self.names.add(value)
            return key + m.group(2) + MASK + m.group(2)
        line = QUOTED.sub(name, line)
        line = IDS.sub(lambda m: m.group(1) + MASK, line)
        for known in sorted(self.names, key=len, reverse=True):
            line = re.sub(r"(?<!\w)%s(?!\w)" % re.escape(known), MASK, line)
        return line
