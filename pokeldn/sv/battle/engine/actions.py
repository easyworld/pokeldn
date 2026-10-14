"""A battler's chosen action: the packed action word of a round's action block, decoded into the
server's 0x8c-byte action entry."""

from pokeldn.sv.battle.machine import lifted

ENTRY = 0x8C


@lifted(0x11461B4)
def decode_action(m, o, entry, word_ptr, client, *_):
    """Decode the packed action at word_ptr (u64 word, then the actor's id) for `client`. 0 for the
    kinds the server ignores; 1 otherwise. Low nibble of the word = kind; a fight (1) carries the
    target position in bits 4..7 and the move in bits 8..23."""
    w = m.u64(word_ptr)
    if w & 0x100F == 0x1003:
        return 0
    client &= 0xFF
    m.write(entry, bytes(ENTRY))
    m.put(entry + 0x84, 4, 0x5400000); m.put(entry + 0x88, 1, 5); m.put(entry + 0x58, 4, 0x20)
    kind = w & 0xF
    lo = w & 0xFFFFFFFF
    if kind == 1:
        m.put(entry + 4, 4, 1)
        m.put(entry + 0x10, 2, lo >> 8)
        m.put(entry + 8, 1, (lo & 0xFF) >> 4)
        m.put(entry + 0xC, 4, m.call(m.main + 0x11464B0, o, (lo & 0xFF) >> 4))
        m.put(entry + 0x12, 1, lo >> 25 & 1)
    elif kind == 2:
        m.put(entry + 4, 4, 2); m.put(entry + 0x14, 4, m.u32(word_ptr + 4))
        m.put(entry + 0x18, 2, lo >> 4); m.put(entry + 0x1A, 1, lo >> 20)
    elif kind == 3:
        m.put(entry + 4, 4, 3); m.put(entry + 0x1C, 1, (lo & 0xFF) >> 4)
        m.put(entry + 0x1D, 1, m.u8(word_ptr + 1) & 0xF); m.put(entry + 0x1E, 1, lo >> 12 & 1)
    elif kind == 4:
        m.put(entry + 4, 4, 6); m.put(entry + 0x1F, 1, lo >> 4); m.put(entry + 0x20, 1, lo >> 12 & 0xF)
        m.put(entry + 0x21, 1, m.u16(word_ptr + 2))
    elif kind == 5:
        m.put(entry + 4, 4, 4); m.put(entry + 0x24, 1, 0); m.put(entry + 0x23, 1, (w & 0xFF) >> 4 & 1)
    elif kind == 6:
        m.put(entry + 4, 4, 5); m.put(entry + 0x22, 1, lo >> 4)
    elif kind in (7, 10, 11):
        m.put(entry + 4, 4, {7: 7, 10: 8, 11: 9}[kind])
    elif kind == 9:
        m.put(entry + 4, 4, 10); m.put(entry + 0x25, 1, lo >> 4)
    elif kind == 0xC:
        m.put(entry + 4, 4, 0xB); m.put(entry + 0x28, 1, w >> 4); m.put(entry + 0x2C, 4, m.u32(word_ptr + 4))
    elif kind == 0xD:
        m.put(entry + 4, 4, 0xE); m.put(entry + 0x40, 1, (w & 0xFF) >> 4)
        m.put(entry + 0x41, 1, m.u8(word_ptr + 1) & 0xF); m.put(entry + 0x42, 1, lo >> 12 & 0xF)
        m.put(entry + 0x43, 1, w >> 60); m.put(entry + 0x4A, 2, m.u8(word_ptr + 7) & 0xF)
        m.put(entry + 0x44, 2, m.u16(word_ptr + 2) & 0xFFF); m.put(entry + 0x46, 2, m.u16(word_ptr + 4) & 0xFFF)
        m.put(entry + 0x48, 2, (w >> 44) & 0xFFF)
    else:
        return 0
    if lo & 0xF == 3:
        plist = m.u64(m.u64(o + 0x10) + 0x30) + 0x38 * client + 0x28 if client < 5 else 0
        b = m.call(m.main + 0x114C614, plist, (lo >> 4) & 0xF)
        actor = m.vcall(b, 0x98) if b else 0
    else:
        actor = m.u64(word_ptr + 8)
    m.put(entry, 4, actor)
    m.put(entry + 0x88, 1, client)
    m.put(entry + 0x89, 2, 0); m.put(entry + 0x8B, 1, 0)
    counter = m.u64(m.u64(o + 0x10) + 0x190)
    n = m.u32(counter + 8)
    if n == 0:
        n = 1
        m.put(counter + 8, 4, 1)
    m.put(entry + 0x54, 4, n)
    m.put(counter + 8, 4, m.u32(counter + 8) + 1)
    return 1


BLOCK, COUNTS = 0x70, 0x230      # one 0x70-byte block of (action word, actor id) pairs per client


@lifted(0x1145E40)
def collect_actions(m, o, actions, header, *_):
    """Decode every action of a round's action header into the server's action list: client c's
    count is the byte at header+0x230+c and its pairs start at header+0x70*c."""
    from pokeldn.sv.battle.engine.getters import append_action
    with m.frame(0xA0) as entry, m.frame(0x10) as word:
        for client in range(5):
            for k in range(m.u8(header + COUNTS + client)):
                pair = header + BLOCK * client + 0x10 * k
                m.write(word, m.read(pair, 0x10))
                if decode_action(m, o, entry, word, client) & 1:
                    append_action(m, actions, entry)
