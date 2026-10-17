"""The field-script macros Emerald's Mystery Gift scripts are written in, assembled as
asm/macros/event.inc does, for a RAM script that runs at a virtual address (`setvaddress`)."""

from pokeldn.frlg.gift.gift_composer import MESSAGE_TOKENS, _TOKEN_RE
from pokeldn.frlg.rom.scrcmd import RAM_SCRIPT_VIRTUAL_BASE
from pokeldn.frlg.text import charmap

# include/constants/script_commands.h; the same numbers in FireRed below 0xC7.
END, CALLSTD, SETVAR, ADDVAR, SETORCOPYVAR, COMPARE_VAR_TO_VALUE = 0x02, 0x09, 0x16, 0x17, 0x1A, 0x21
SETFLAG, CHECKFLAG, CHECKITEMSPACE, CHECKITEM = 0x29, 0x2B, 0x46, 0x47
FACEPLAYER, WAITMESSAGE, LOCK, RELEASE, WAITBUTTONPRESS = 0x5A, 0x66, 0x6A, 0x6C, 0x6D
SETVADDRESS, VGOTO_IF, VMESSAGE = 0xB8, 0xBB, 0xBD
VAR_0x8000, VAR_0x8001, VAR_RESULT = 0x8000, 0x8001, 0x800D
STD_OBTAIN_ITEM = 0
TRUE, FALSE = 1, 0          # vgoto_if_ne passes FALSE, which is LESS_THAN [event.inc:1882]


def encode_text(text):
    """Text as the game stores it: "\\n" a line break (0xFE), "\\f" a new box (0xFA, `\\p`),
    MESSAGE_TOKENS for {PLAYER} and the buffers, 0xFF at the end."""
    out = bytearray()
    for page_index, page in enumerate(text.split("\f")):
        if page_index:
            out.append(0xFA)
        for line_index, line in enumerate(page.split("\n")):
            if line_index:
                out.append(0xFE)
            for piece in _TOKEN_RE.split(line):
                out += MESSAGE_TOKENS.get(piece) or charmap.encode(piece)
    return bytes(out) + b"\xFF"


def _u16(value):
    return (value & 0xFFFF).to_bytes(2, "little")


class Script:
    """One RAM script: macros append bytecode, `label` names a place, text goes after the code.
    `assemble()` resolves every label to RAM_SCRIPT_VIRTUAL_BASE + its offset, the address the
    leading `setvaddress` makes it."""

    def __init__(self):
        self.code = bytearray()
        self.labels = {}
        self.fixups = []
        self.texts = {}
        self.setvaddress()

    def label(self, name):
        if name in self.labels:
            raise ValueError(f"duplicate label {name!r}")
        self.labels[name] = len(self.code)

    def _pointer(self, label):
        self.fixups.append((len(self.code), label))
        self.code += b"\x00" * 4

    def setvaddress(self):
        self.code.append(SETVADDRESS)
        self.code += RAM_SCRIPT_VIRTUAL_BASE.to_bytes(4, "little")

    def op(self, opcode, *halfwords):
        self.code.append(opcode)
        for value in halfwords:
            self.code += _u16(value)

    def vgoto_if(self, condition, label):
        self.code += bytes((VGOTO_IF, condition))
        self._pointer(label)

    def vgoto_if_set(self, flag, label):
        self.op(CHECKFLAG, flag)
        self.vgoto_if(TRUE, label)

    def vgoto_if_eq(self, var, value, label):
        self.op(COMPARE_VAR_TO_VALUE, var, value)
        self.vgoto_if(TRUE, label)

    def vgoto_if_ne(self, var, value, label):
        self.op(COMPARE_VAR_TO_VALUE, var, value)
        self.vgoto_if(FALSE, label)

    def checkitem(self, item, quantity=1):
        self.op(CHECKITEM, item, quantity)

    def checkitemspace(self, item, quantity=1):
        self.op(CHECKITEMSPACE, item, quantity)

    def giveitem(self, item, amount=1):
        self.op(SETORCOPYVAR, VAR_0x8000, item)
        self.op(SETORCOPYVAR, VAR_0x8001, amount)
        self.code += bytes((CALLSTD, STD_OBTAIN_ITEM))

    def vmessage(self, text):
        """vmessage, waitmessage, waitbuttonpress: the three lines every gift script writes."""
        name = self.texts.setdefault(encode_text(text), f"text_{len(self.texts)}")
        self.code.append(VMESSAGE)
        self._pointer(name)
        self.code += bytes((WAITMESSAGE, WAITBUTTONPRESS))

    def assemble(self):
        code = bytearray(self.code)
        labels = dict(self.labels)
        for text, name in self.texts.items():
            labels[name] = len(code)
            code += text
        for position, label in self.fixups:
            if label not in labels:
                raise ValueError(f"unresolved label {label!r}")
            code[position:position + 4] = (RAM_SCRIPT_VIRTUAL_BASE + labels[label]).to_bytes(4, "little")
        return bytes(code)
