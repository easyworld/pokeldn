"""Status, field and side conditions: their checks, start, application, the code requests and their end."""

from pokeldn.sv.battle.engine.calls import M32, M64, _need, _s32, _tail, m_s32
from pokeldn.sv.battle.engine.containers import battler
from pokeldn.sv.battle.engine.events import _bump_record, _event, _id, _id_at, _t78, _value
from pokeldn.sv.battle.engine.members import _first_party_id, _standing
from pokeldn.sv.battle.engine.rules import _rule_499_bit2
from pokeldn.sv.battle.engine.targets import _walk_pre_resume
from pokeldn.sv.battle.machine import lifted


@lifted(0x287DA44)
def changed_condition_17(m, o, action, *_):
    """The value of the battler's condition 0x17 when the action (kind 1, flags +0x58 & 0x18 clear, u16
    +0x10 not 0xa5) names another one and vf 0x698 accepts it; else 0."""
    if m.u8(action + 0x58) & 0x18:
        return 0
    b = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.u32(action))
    if m.vcall(b, 0x220, 0x17) & 1 == 0 or m.u32(action + 4) != 1:
        return 0
    cur = m.u16(action + 0x10)
    if cur == 0xA5:
        return 0
    with m.frame(16) as pair:
        p = m.vcall(b, 0x240, 0x17)
        m.put(pair, 8, p[0]); m.put(pair + 8, 8, p[1])
        v = m.call(m.main + 0xF7FFE0, pair) & 0xFFFFFFFF
    if cur == v & 0xFFFF:
        return 0
    return v if m.vcall(b, 0x698, v) & 0xFFFF else 0


@lifted(0x19375B0)
def condition_bits_3_8(m, pair, *_):
    """Bits 3..8 of the entry's second word when its kind (bits 0..2) is 2 or 4; else 0."""
    w = m.u64(pair + 8) & 0xFFFFFFFF
    return w >> 3 & 0x3F if w & 7 in (2, 4) else 0


@lifted(0x2D3C0CC)
def condition_2_or_d5(m, b, kind, *_):
    """1 for kind 1 when vf 0xf8 is 0xd5; else vf 0x220 with 2."""
    if kind & 0xFFFFFFFF == 1 and m.vcall(b, 0xF8) & 0xFFFF == 0xD5:
        return 1
    return m.vcall(b, 0x220, 2)


@lifted(0x287DB40)
def build_condition(m, o, packed, b, out, *_):
    """Tail call of 0x1793efc with the server's 0x14d96d8 object, the u16 packed value and 0x11440e8's."""
    x = m.call(m.main + 0x11440E8, m.u64(o + 0x10))
    y = m.call(m.main + 0x14D96D8, m.u64(o + 0x10))
    return _tail(m, m.main + 0x1793EFC, y, packed & 0xFFFF, b, out, x)


@lifted(0x17CE41C)
def raise_level(m, o, b, n, out, *_):
    """For n (u16) nonzero: b's vf 0x240(n) result (16 bytes) into `out` when given; then on the main
    battler for b's id, n up to 5: vf 0x608, command 0x14 and, unless the id has slot 10 (0x1381420),
    command 0x90 (id, 0) as the tail call; above 5: vf 0x610(n) and command 0x15 (id, n)."""
    if n & 0xFFFF == 0:
        return o
    if out:
        r = m.vcall(b, 0x240, n & 0xFFFFFFFF)
        m.put(out, 8, r[0]); m.put(out + 8, 8, r[1])
    ident = m.vcall(b, 0x98) & 0xFFFFFFFF
    t = m.call(m.main + 0xF21C94, m.u64(m.u64(m.u64(o + 0x20) + 0x10) + 0x30), ident)
    if n & 0xFFFF > 5:
        m.vcall_void(t, 0x610, n & 0xFFFFFFFF)
        return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x15, ident, n & 0xFFFF)
    m.vcall_void(t, 0x608)
    m.call_void(m.main + 0x119AFF0, m.u64(o + 0x18), 0x14, ident)
    s = m.call(m.main + 0x1381420, m.u64(m.u64(o + 0x10) + 0xF0), ident)
    if s & 0xFF == 0xA:
        return s
    return _tail(m, m.main + 0x119AFF0, m.u64(o + 0x18), 0x90, ident, 0)


@lifted(0x288C730)
def clear_slot(m, o, i, *_):
    """Falls into 0x288c73c on [[o+0x10]+0x70]: clears slot i (signed i <= 13, flag at +0xa8 + 4i)."""
    base = m.u64(m.u64(o + 0x10) + 0x70)
    i &= 0xFFFFFFFF
    if m_s32(i) > 0xD:
        return 0
    flag = (base + i * 4 + 0xA8) & 0xFFFFFFFFFFFFFFFF
    if m.u32(flag) == 0:
        return 0
    a = base + 8 + i * 0x10; b = base + 8 + i * 4; c = base + i * 0x2C
    m.put(a + 0x348, 8, 0); m.put(a + 0x340, 8, 0)
    m.put(b + 0x30, 4, 0); m.put(b + 0x68, 4, 0); m.put(flag, 4, 0)
    m.put(c + 0x108, 4, 0)
    m.put(c + 0xF8, 8, 0); m.put(c + 0x100, 8, 0)
    m.put(c + 0xE8, 8, 0); m.put(c + 0xF0, 8, 0)
    m.put(c + 0xE0, 8, 0)
    return 1


@lifted(0x17CE294)
def take_pending_code(m, _o, b, p, *_):
    """Consume the code at p (set to 0, or 6 for code 0x32 while vf 0x230 is nonzero); the result
    depends on the code: 0x31 gives vf 0x230, 0x32 vf 0x230 or 6 when vf 0x220(6), 0x33 0x17ce3c0
    (p kept when nonzero), anything else the code itself when vf 0x220(code)."""
    v = m.vcall(b, 0x230)
    code = m.u32(p)
    if code == 0x32:
        if v & 0xFFFF:
            m.put(p, 4, 6)
            return v
        r = 6 if m.vcall(b, 0x220, 6) & 1 else 0
    elif code == 0x31:
        r = v
    elif code == 0x33:
        r = m.call(m.main + 0x17CE3C0, b)
        if r & 0xFFFF:
            return r
        r = 0
    else:
        r = m.u32(p) if m.vcall(b, 0x220, code) & 1 else 0
    m.put(p, 4, 0)
    return r


_CODES_3C69DC4 = (0x7, 0xC, 0xD, 0xF, 0x17, 0xB)   # u16 x 6 at 0x3c69dc4


@lifted(0x2823BE0)
def code_at(m, i, *_):
    i &= 0xFFFFFFFF
    return _CODES_3C69DC4[i] if i <= 5 else 0


@lifted(0x17CE3C0)
def first_code_held(m, b, *_):
    """The first code of 0x2823be0's list for which vf 0x220 holds; 0 at the end of the list."""
    i = 0
    while True:
        v = m.call(m.main + 0x2823BE0, i) & 0xFFFFFFFF
        i += 1
        if v & 0xFFFF == 0 or m.vcall(b, 0x220, v) & 1:
            return v


@lifted(0x17CE354)
def maybe_114b0ac(m, o, a, p, *_):
    """When 0x17ce3ac(p) holds (bits 0..6 of the byte at p+2), tail-calls 0x114b0ac(0x1143584(o), a, p)."""
    if m.call(m.main + 0x17CE3AC, p) & 1 == 0:
        return
    return _tail(m, m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), a & 0xFFFFFFFF, p)


@lifted(0x13616F0)
def remove_id(m, o, i, ident, *_):
    """Drop `ident` from list i (0..13): flag at +0xa8+4i, count at +0x70+4i, ten u32 slots at
    +0xe0+0x2c*i. Returns 1 when the list became empty and was cleared."""
    i &= 0xFFFFFFFF
    if (i ^ 0x80000000) - 0x80000000 > 0xD:
        return 0
    flag, count = o + 0xA8 + 4 * i, o + 0x70 + 4 * i
    if m.u32(flag) == 0:
        return 0
    n = m.u32(count)
    arr = o + 0x2C * i + 0xE0
    ident &= 0xFFFFFFFF
    for j in range(n):
        if m.u32(arr + 4 * j) == ident:
            break
    else:
        return 0
    if j <= 9:
        k = j
        if j & 1:
            m.put(arr + 4 * j, 4, m.u32(arr + 4 * j + 4))
            k = j + 1
        if j != 9:
            for off in range(4 * k, 0x28, 8):
                a, b = m.u32(arr + off + 4), m.u32(arr + off + 8)
                m.put(arr + off, 4, a); m.put(arr + off + 4, 4, b)
        j = 10
    n = (n - 1) & 0xFFFFFFFF
    m.put(arr + 4 * j, 4, 0)
    m.put(count, 4, n)
    pair = o + 8 + 0x10 * i + 0x340
    if n == 0:
        m.write(pair, bytes(0x10))
        m.put(o + 4 * i + 0x38, 4, 0)
        m.put(count, 4, 0); m.put(flag, 4, 0)
        m.put(arr + 0x28, 4, 0)
        m.write(arr, bytes(0x28))
        return 1
    if m.call(m.main + 0x184A110, pair) & 0xFFFFFFFF == ident:
        m.call_void(m.main + 0x28787A0, pair, m.u32(arr))
    return 0


@lifted(0x1141160)
def standing_condition_c(m, o, *_):
    if _rule_499_bit2(m, o):
        return
    for b in _standing(m, o):
        if m.vcall(b, 0x4D0, 0xC) & 1:
            m.call_void(m.main + 0x1140198, m.u64(o + 0x20), b, 0xC)
            m.call_void(m.main + 0x1148470, m.u64(o + 0x20), b, 0x13)


@lifted(0x286FE20)
def double_on_condition(m, o, ident, *_):
    s = m.u64(m.u64(o + 0x38) + 0x78)
    p = m.u64(s + 0x20)
    if (m.u32(p + 0xC) if p else 0) != ident & 0xFFFFFFFF:
        return
    q = m.u64(s + 0x28)
    b = battler(m, m.u64(m.u64(o + 8) + 0x30), m.u32(q + 0xC) if q else 0)
    if m.vcall(b, 0x230) & 0xFFFF == 0 and m.vcall(b, 0x228, 1) & 1 == 0:
        return
    return _tail(m, m.main + 0x181D0D0, o, 2)


@lifted(0x17CDF14)
def apply_pending_codes(m, o, out, req, *_):
    """For each of the u8 [req+0x30] battlers (ids at req+8) able to act (vf 0x208), consume its pending
    codes (0x17ce294 on a copy of req+4) until none is left: code 0x1c may be skipped by 0x17ce520;
    each other one is recorded (0x17ce41c) and applied (0x17ce354 when +0x35, else 0x114a970 then
    0x114b0ac), code 0x13 also runs 0x287fe9c, and out[0] / out[1 + i] are set. With +0x34 the run is
    bracketed by 0x17ce0e4 / 0x17ce27c."""
    bracket = m.u8(req + 0x34)
    if bracket:
        for a in (0x1143584, 0x17CE0E4, 0x17CE27C):
            _need(m, m.main + a)
    if m.u8(req + 0x30):
        for a in (0x17CE294, 0x17CE520, 0x1146E90, 0x179372C, 0x17CE41C, 0x1143584, 0x114A970, 0x114B0AC,
                  0x287FE9C, 0x1146154):
            _need(m, m.main + a)
    m.put(out + 5, 8, 0)
    m.put(out, 8, 0)
    if bracket:
        m.call_void(m.main + 0x17CE0E4, m.call(m.main + 0x1143584, o), m.u32(req))
    if m.u8(req + 0x30):
        i = 0
        with m.frame(0x50) as sp:
            while True:
                b = m.call(m.main + 0x13813F4, o, m.u32(req + 8 + 4 * i))
                if m.vcall(b, 0x208) & 1:
                    m.put(sp + 0x14, 4, m.u32(req + 4))
                    while True:
                        code = m.call(m.main + 0x17CE294, 0, b, sp + 0x14) & 0xFFFFFFFF
                        if code & 0xFFFF == 0:
                            break
                        if code & 0xFFFF == 0x1C and m.call(m.main + 0x17CE520, m.call(m.main + 0x1146E90, o), b) & 1:
                            continue
                        m.call_void(m.main + 0x179372C, sp)
                        m.call_void(m.main + 0x17CE41C, m.call(m.main + 0x1143584, o), b, code, sp)
                        who = m.u32(req)
                        if m.u8(req + 0x35):
                            m.call_void(m.main + 0x17CE354, o, who, req + 0x38)
                        else:
                            key = m.u16(req + 0x32)
                            m.call_void(m.main + 0x1146154, sp + 0x18)
                            ident = m.vcall(b, 0x98) & 0xFFFFFFFF
                            if m.call(m.main + 0x114A970, code, sp, ident, key, sp + 0x18) & 1:
                                m.call_void(m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), who, sp + 0x18)
                        if code & 0xFFFF == 0x13:
                            m.call_void(m.main + 0x287FE9C, o, b)
                        m.put(out, 1, 1)
                        m.put(out + i + 1, 1, 1)
                i += 1
                if i >= m.u8(req + 0x30):
                    break
    if bracket:
        m.call_void(m.main + 0x17CE27C, m.call(m.main + 0x1143584, o), m.u32(req))


@lifted(0x283F0DC)
def apply_side_effects(m, o, out, req, *_):
    """For each target 0x2823478 lists for the u8 req+4: 0x288818c(o, flags, target, req+5) (out set when
    one holds); then for each of the 2 x 19 flags set, 0x288835c([req], side, k); bracketed by
    0x17ce0e4 / 0x17ce27c when req+9 and 0x2888224(flags) hold."""
    for a in (0x1482534, 0x13813EC, 0x2823478, 0x288818C, 0x2888224, 0x1143584, 0x288835C):
        _need(m, m.main + a)
    if m.u8(req + 9):
        _need(m, m.main + 0x17CE0E4); _need(m, m.main + 0x17CE27C)
    m.put(out, 1, 0)
    with m.frame(0x30) as sp:
        flags = sp + 8
        m.write(sp, bytes(0x30))
        t = m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o))
        m.call_void(m.main + 0x2823478, t, sp + 4, sp, m.u8(req + 4))
        i = 0
        while i < m.u8(sp):
            if m.call(m.main + 0x288818C, o, flags, m.u8(sp + 4 + i), req + 5) & 1:
                m.put(out, 1, 1)
            i += 1
        if m.u8(req + 9) and m.call(m.main + 0x2888224, flags) & 1:
            m.call_void(m.main + 0x17CE0E4, m.call(m.main + 0x1143584, o), m.u32(req))
        for side in range(2):
            for k in range(0x13):
                if m.u8(flags + side * 0x13 + k):
                    m.call_void(m.main + 0x288835C, m.call(m.main + 0x1143584, o), m.u32(req), side, k)
        if m.u8(req + 9) and m.call(m.main + 0x2888224, flags) & 1:
            m.call_void(m.main + 0x17CE27C, m.call(m.main + 0x1143584, o), m.u32(req))


@lifted(0x116EBBC)
def weather_of(m, o, out, ident_ptr, *_):
    """out (byte) = event 0x9d's answer, passed through event 0x9e for a nonzero [ident_ptr]."""
    v = m.call(m.main + 0x116EC0C, m.u64(o + 0x38), out, ident_ptr)
    ident = m.u32(ident_ptr)
    if ident:
        v = m.call(m.main + 0x116EE6C, m.u64(o + 0x38), ident, v & M32)
    m.put(out, 1, v)


@lifted(0x14C78D0)
def weather_for(m, o, ident, *_):
    with m.frame(0x10) as p:
        m.put(p, 4, ident)
        m.call_void(m.main + 0x116EBBC, m.call(m.main + 0x116EBB4, m.u64(o + 0x28)), p + 8, p)
        return m.u8(p + 8)


@lifted(0x285CB30)
def apply_field(m, o, ident, kind, src, *_):
    """When the field state is not `kind`: record (ident, 8, kind; ident, 0x2a, 0x9c, flag 0x4a, the 0x24
    bytes at src) through 0x283fbf0."""
    v = m.call(m.main + 0x13616DC, m.call(m.main + 0x148253C, m.u64(o + 8)))
    if v & 0xFF == kind & 0xFF:
        return
    with m.frame(0x50) as s:
        m.write(s, bytes(0x50))
        m.put(s, 4, ident); m.put(s + 4, 4, 8); m.put(s + 8, 1, kind)
        m.put(s + 0x10, 8, ident & M32); m.put(s + 0x18, 8, 0x2A)
        m.put(s + 0x20, 2, 0x9C); m.put(s + 0x4A, 1, 1)
        if src:
            m.write(s + 0x24, m.read(src, 0x24))
        m.call_void(m.main + 0x283FBF0, o, s)


@lifted(0x285CB00)
def apply_field_3(m, o, ident, *_):
    if _id_at(m, _t78(m, o), 0x18) != ident & M32:
        return
    return _tail(m, m.main + 0x285CB30, o, ident, 3, 0)


@lifted(0x286C400)
def apply_side_1(m, o, ident, *_):
    """apply_side kind 1 (text 0x273) with the field class of `ident`; when it applies, record 0x3c8
    takes 1."""
    cls = m.call(m.main + 0x283D690, o, ident) & M32
    r = m.call(m.main + 0x28616B0, ident & M32, 5)
    with m.frame(0x10) as pair:
        m.put(pair, 8, r[0]); m.put(pair + 8, 8, r[1])
        ok = m.call(m.main + 0x286C320, o, ident & M32, cls, 1, pair, 0x9C, 0x273, cls & 0xFF) & 1
    if ok:
        _bump_record(m, m.u64(_t78(m, o) + 0x3C8), 1)


@lifted(0x1154148)
def apply_condition(m, o, out, r, *_):
    """Apply the condition record r (id +0, kind +4, sub +8/+9, target descriptor +0x10, message +0x20,
    text +0x24, flags +0x48..+0x4a); out (byte) = whether it took."""
    for a in ((0x2836050, 0x2836450) if m.u32(r + 4) == 8 else (0x2836A78,)):
        _need(m, m.main + a)
    with m.frame(0x40) as f:
        text = f
        m.call_void(m.main + 0x1146154, text)
        ident = m.u32(r)
        if m.u8(r + 0x4A):
            m.call_void(m.main + 0x17CE0E4, m.call(m.main + 0x1143584, o), ident)
        kind = m.u32(r + 4)
        if kind == 8:
            desc = f + 0x30
            m.write(desc, m.read(r + 0x10, 0x10))
            m.call_void(m.main + 0x2836050, m.call(m.main + 0x1146E90, o), ident, m.u8(r + 8), desc)
            ok = m.call(m.main + 0x28806B0, o, ident, m.u8(r + 8), desc, m.u8(r + 9)) & 1
            m.call_void(m.main + 0x2880738, text, m.u8(r + 8), m.u8(r + 9))
        else:
            ok = m.call(m.main + 0x28807C0, o, kind, r + 0x10, m.u8(r + 0x49)) & 1
        if ok and not m.u8(r + 0x48):
            if m.u16(r + 0x20) != 0x9C:
                m.call_void(m.main + 0x2880868, m.call(m.main + 0x1143584, o), m.u16(r + 0x20))
            own = m.call(m.main + 0x17CE3AC, r + 0x24) & 1
            m.call_void(m.main + 0x114B0AC, m.call(m.main + 0x1143584, o), m.u32(r), r + 0x24 if own else text)
        if m.u8(r + 0x4A):
            m.call_void(m.main + 0x17CE27C, m.call(m.main + 0x1143584, o), m.u32(r))
        kind = m.u32(r + 4)
        if kind == 8 and ok:
            m.call_void(m.main + 0x2836450, m.call(m.main + 0x1146E90, o), m.u32(r), m.u8(r + 8))
            kind = m.u32(r + 4)
        if kind != 8 and ok:
            m.call_void(m.main + 0x2836A78, m.call(m.main + 0x1146E90, o), m.u32(r), m.u32(r + 4))
            kind = m.u32(r + 4)
            if kind == 9:
                m.call_void(m.main + 0x2880878, o)
                kind = m.u32(r + 4)
        if kind == 2 and ok:
            m.call_void(m.main + 0x288090C, o, m.u32(r))
        m.put(out, 1, ok)


@lifted(0x283FBF0)
def apply_condition_of(m, o, r, *_):
    with m.frame(0x10) as out:
        m.call_void(m.main + 0x1154148, m.call(m.main + 0x113DFC4, m.u64(o + 0x28)), out, r)
        return m.u8(out)


@lifted(0x17CE0E4)
def flag_and_push_25_c7_0(m, o, ident, *_):
    return _tail(m, m.main + 0x17CE0EC, o, ident, 0)


@lifted(0x287E9E8)
def start_field(m, o, out, r, *_):
    """out (byte) = whether the field effect (kind r+4, descriptor r+8) started: then 0x114beb0(8), unless
    r+0x18 is 1 queue 0xb2 and 0xaa (kind), then 0x114bf8c(8, kind)."""
    ok = m.call(m.main + 0x287EA80, m.call(m.main + 0x1143584, o), m.u8(r + 4), r + 8) & 1
    if ok:
        m.call_void(m.main + 0x114BEB0, m.call(m.main + 0x1143584, o), 8)
        if m.u8(r + 0x18) != 1:
            m.call_void(m.main + 0x287EAD4, m.call(m.main + 0x1143584, o))
            m.call_void(m.main + 0x287EAE4, m.call(m.main + 0x1143584, o), m.u8(r + 4))
        m.call_void(m.main + 0x114BF8C, m.call(m.main + 0x1143584, o), 8, m.u8(r + 4))
    m.put(out, 1, ok)


@lifted(0x28806B0)
def start_field_of(m, o, ident, kind, desc, flag, *_):
    with m.frame(0x30) as r:
        m.write(r, bytes(0x20))
        m.call_void(m.main + 0x179372C, r + 8)
        m.put(r, 4, ident); m.put(r + 4, 1, kind)
        m.write(r + 8, m.read(desc, 0x10))
        m.put(r + 0x18, 1, flag)
        out = r + 0x20
        m.call_void(m.main + 0x287E9E8, m.call(m.main + 0x288093C, m.call(m.main + 0x1361214, o)), out, r)
        return m.u8(out)


@lifted(0x2878714)
def add_condition_id(m, o, k, v, *_):
    """Add id v to the list of active condition k (<= 13, at most 11 ids at o + 0x2c k + 0xe0)."""
    k &= M32
    if _s32(k) > 0xD or m.u32(o + 0xA8 + 4 * k) == 0:
        return 0
    c = m.u32(o + 0x70 + 4 * k)
    if c > 10:
        return 0
    lst = o + 0x2C * k + 0xE0
    v &= M32
    for i in range(c):
        if m.u32(lst + 4 * i) == v:
            return 0
    m.put(lst + 4 * c, 4, v)
    m.put(o + 0x70 + 4 * k, 4, c + 1)
    return 1


@lifted(0x2878668)
def start_condition(m, o, k, desc, v, *_):
    """Start condition k unless active: its descriptor, u16 v, cleared counters and list, and the
    descriptor's packed index as its first id."""
    k &= M32
    if m.u32(o + 0xA8 + 4 * k):
        return 0
    m.put(o + 0xA8 + 4 * k, 4, 1)
    m.put(o + 0x348 + 16 * k, 8, m.u64(desc)); m.put(o + 0x350 + 16 * k, 8, m.u64(desc + 8))
    m.put(o + 0x38 + 4 * k, 4, 0); m.put(o + 0x70 + 4 * k, 4, 0)
    m.put(o + 0x1C + 2 * k, 2, v)
    m.write(o + 0x2C * k + 0xE0, bytes(0x2C))
    n = m.call(m.main + 0x184A110, desc) & M32
    if n:
        m.call_void(m.main + 0x2878714, o, k, n)
    return 1


@lifted(0x28787E0)
def set_field_kind(m, o, kind, d0, d1, *_):
    """Set the field kind (+0x18) when it changes: an active state clears its counters; a nonzero kind
    starts condition 8 with descriptor (d0, d1)."""
    kind &= 0xFF
    if m.u8(o + 0x18) == kind:
        return 0
    if m.u32(o + 0xC8):
        for off, n in ((0x3D0, 8), (0x3C8, 8), (0x58, 4), (0x90, 4), (0xC8, 4), (0x240, 8), (0x248, 8),
                       (0x250, 8), (0x258, 8), (0x260, 8), (0x268, 4)):
            m.put(o + off, n, 0)
    if kind:
        with m.frame(0x10) as d:
            m.put(d, 8, d0); m.put(d + 8, 8, d1)
            m.call_void(m.main + 0x2878668, o, 8, d, kind)
    m.put(o + 0x18, 1, kind)
    return 1


@lifted(0x283EF9C)
def place_side_condition(m, o, out, r, *_):
    """Place side condition r (ident +0, side +4, descriptor +8, pos +0x18) on each position 0x2823478
    names that takes it (0x2887f9c): queue it, send the record, raise 0xf2. out = whether any took."""
    _need(m, m.main + 0x283AAE8); _need(m, m.main + 0x283AEC0)
    took = 0
    with m.frame(0x30) as f:
        d = f + 0x10
        m.write(d, m.read(r + 8, 0x10))
        m.call_void(m.main + 0x283AAE8, m.call(m.main + 0x1146E90, o), m.u32(r), m.u32(r + 4), m.u8(r + 0x18), d)
        m.put(f + 8, 1, 0)
        lst = f + 0xC
        m.call_void(m.main + 0x2823478, m.call(m.main + 0x13813EC, m.call(m.main + 0x1482534, o)), lst, f + 8,
                    m.u8(r + 0x18))
        i = 0
        while i < m.u8(f + 8):
            p = m.u8(lst + i)
            if m.call(m.main + 0x2887F9C, m.call(m.main + 0x1143584, o), p, m.u32(r + 4), d) & 1:
                m.call_void(m.main + 0x2888018, m.call(m.main + 0x1143584, o), p, m.u32(r + 4), d)
                m.call_void(m.main + 0x2888060, o, r, m.u8(lst + i))
                m.call_void(m.main + 0x283AEC0, m.call(m.main + 0x1146E90, o), m.u32(r), m.u32(r + 4),
                            m.u8(r + 0x18), d)
                took = 1
            i += 1
    m.put(out, 1, took)


@lifted(0x283EF60)
def place_side_condition_of(m, o, r, *_):
    with m.frame(0x10) as out:
        m.call_void(m.main + 0x283EF9C, m.call(m.main + 0x283EF94, m.u64(o + 0x28)), out, r)
        return m.u8(out)


# Type masks for kinds 1, 3, 4 and 18 of 0x1795308 (a battler's three type fields, bits 10..14, 0..4
# and 5..9 of vf 0x2f8): kinds whose own type blocks them.
_TYPE_BLOCKS = {1: (0x3000, 0xC, 0x180), 3: (0x3800, 0xE, 0x1C0), 4: (0x2400, 9, 0x120), 18: (0x2C00, 0xB, 0x160)}


@lifted(0x1795308)
def can_take_condition(m, o, out, s, *_):
    """Check status condition record s (user +0, target +8, kind +0x10, sub +0x28, flags +0x30..+0x33):
    when the target is immune, already holds it or a check refuses, show why (when +0x31 is set) and
    out = 1; otherwise out = whether 0x1796364 lets it apply."""
    o10 = m.u64(o + 0x10)
    flag_a = flag_b = 0
    code = None
    if m.call(m.main + 0x1381540, m.call(m.main + 0x13813EC, o10)) & 1 and not m.vcall(m.u64(s + 8), 0x78) & 1:
        if m.u8(s + 0x31):
            uid = m.vcall(m.u64(s), 0x98)
            m.call_void(m.main + 0x287DB9C, m.call(m.main + 0x1143584, o), uid & M32, m.u64(s + 8), 2,
                        m.u16(s + 0x10), m.u8(s + 0x28))
            m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)
        m.put(out, 1, 1)
        return
    u, b = m.u64(s), m.u64(s + 8)
    k, sub, mode = m.u16(s + 0x10), m.u8(s + 0x28), m.u8(s + 0x30)
    if mode != 2 and m.vcall(b, 0x220, k) & 1:
        flag_a, flag_b, code = 1, 1, 1
    else:
        apply = False
        if k <= 5 and m.vcall(b, 0x230) & 0xFFFF and mode == 0:
            code = 3
        elif m.call(m.main + 0x1795EA4, m.call(m.main + 0x1146E90, o), b, u, k, sub) & 1:
            apply = True
        else:
            node = m.vcall(b + 0x28, 0)
            static = m.call(m.main + 0x2D1FD38)
            while node:
                if node == static:
                    if k == 0x2A and m.u8(b + 0x714):
                        code, flag_a = 2, 1
                    break
                node = m.u64(node)
            if code is None:
                r = m.call(m.main + 0x287DD04, o, b)
                if k == 3 and r & 1:
                    code = 3
                elif k in _TYPE_BLOCKS:
                    v = m.vcall(b, 0x2F8)
                    a, c, d = _TYPE_BLOCKS[k]
                    if v & 0x7C00 == a or v & 0x1F == c or v & 0x3E0 == d:
                        code, flag_a = 2, 1
                    else:
                        apply = True
                elif k == 5:
                    v = m.vcall(b, 0x2F8)
                    if (v & 0x3E0 in (0x100, 0x60) or v & 0x1F in (8, 3) or v & 0x7C00 in (0xC00, 0x2000)):
                        code, flag_a = 2, 1
                    else:
                        apply = True
                elif k in (7, 12):
                    uid = m.vcall(b, 0x98) & M32
                    first = _first_party_id(m, m.u64(o10 + 0x310))
                    if first == uid:
                        code, flag_a = 2, 1
                    elif k == 7:
                        apply = True
                    else:
                        bb = m.call(m.main + 0xF21C94, m.u64(m.u64(o + 0x10) + 0x30), m.vcall(b, 0x98) & M32)
                        if bb == 0 or m.vcall(bb, 0x78) & 1:
                            apply = True
                        else:
                            code, flag_a = 2, 1
                elif k == 14:
                    if m.vcall(b, 0x230) & 0xFFFF:
                        code = 3
                    else:
                        apply = True
                elif k == 16:
                    from pokeldn.sv.battle.engine import flatbuffer as fb
                    from pokeldn.sv.battle.engine.data import static_table
                    if m.call(m.main + 0x287DD60, o, b) & 1:
                        code = 3
                    else:
                        v = m.vcall(b, 0xF0)
                        table = static_table(m, 0x46DDAA8, 0x46DDAB0, 0x46DDAB8)
                        if fb.u8(m, m.call(m.main + 0xF74860, table, v), 6):
                            code = 3
                        else:
                            apply = True
                elif k == 0x1C and m.call(m.main + 0xF7FFE0, s + 0x18) & 0xFFFF == 0xA5:
                    code = 3
                else:
                    apply = True
        if apply:
            with m.frame(0x10) as f:
                m.put(f, 1, 0)
                r = m.call(m.main + 0x1796364, m.call(m.main + 0x1146E90, o), u, b, k, sub, f) & 1
                if r and (m.u8(s + 0x32) | m.u8(f)):
                    m.call_void(m.main + 0x287DD9C, m.call(m.main + 0x1146E90, o), m.u64(s + 8), m.u64(s),
                                m.u16(s + 0x10), m.u8(s + 0x28), m.u32(s + 0x2C))
                    m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)
            m.put(out, 1, r)
            return
    if m.u8(s + 0x31) and (flag_a or m.u8(s + 0x28) != 5 or not m.u8(s + 0x33)):
        uid = m.vcall(m.u64(s), 0x98)
        k = m.u16(s + 0x10)
        if flag_b and k == 0x14:
            m.put(m.call(m.main + 0x139B698, o) + 0xC1, 1, 1)
        else:
            m.call_void(m.main + 0x287DB9C, m.call(m.main + 0x1143584, o), uid & M32, m.u64(s + 8), code, k,
                        m.u8(s + 0x28))
            m.put(m.call(m.main + 0x139B698, o) + 0xC0, 1, 1)
    m.put(out, 1, 1)


# 0x17959d4: the a7 text when a condition is applied with +0x28 set, kinds 1..7 (jump table 0x3c6a484).
_APPLY_A7 = {1: 0x2E, 2: 0x2A, 3: 0x2D, 4: 0x2C, 5: 0x2B, 6: 0x2F, 7: 0x30}
# The 0x82 message per kind 1..21 when +0x29 is set (jump table 0x3c6a48b); kind 5 is 0x4f or 0x50,
# kinds 8, 10, 16 and 20 send an empty message.
_APPLY_TEXT = {1: 0x5C, 2: 0x67, 3: 0x61, 4: 0x56, 6: 0x74, 7: 0x6E, 9: 0x6C, 11: 0xBD, 12: 0xC0, 13: 0xC5,
               14: 0xDA, 15: 0x11B, 17: 0x7C, 18: 0xCA, 19: 0xEE, 21: 0xF1}


@lifted(0x17959D4)
def apply_condition_record(m, o, _out, s, *_):
    """Apply status condition record s (user +0, target +8, kind +0x10, descriptor +0x18, flags +0x28,
    +0x29, text +0x30, +0x38): set it on the target, queue it, send its messages, then the kind's
    follow-up (0x2835034 for kinds 0..5, 0x287e310 for 16, else 0x2d0cdf4)."""
    k = m.u16(s + 0x10)
    for a in (0x2835034,) if k <= 5 else (0x287E310, 0x283544C) if k == 0x10 else (0x2D0CDF4,):
        _need(m, m.main + a)
    b = m.u64(s + 8)
    q = m.u64(o + 0x20)
    k = m.u16(s + 0x10)
    desc = s + 0x18
    bid = m.vcall(b, 0x98) & M32
    m.vcall_void(b, 0x368, k, desc)
    m.call_void(m.main + 0x174AE20, m.u64(q + 0x18), bid, k, desc)
    if k <= 5:
        m.call_void(m.main + 0x119AFF0, m.u64(q + 0x18), 0x90, bid, k)
    if m.u8(s + 0x28):
        k2 = m.u16(s + 0x10)
        if k2 in _APPLY_A7:
            m.call_void(m.main + 0x114ADE8, m.u64(o + 0x20), m.u64(s + 8), _APPLY_A7[k2])
    b = m.u64(s + 8)
    k = m.u16(s + 0x10)
    u = m.u64(s)
    flag = m.u8(s + 0x29)
    text = m.u64(s + 0x30)
    if u:
        uid = m.vcall(u, 0x98) & M32
    elif b:
        uid = m.vcall(b, 0x98) & M32
    else:
        uid = 0
    if b and flag:
        with m.frame(0x30) as msg:
            m.write(msg, bytes(0x24))
            if 1 <= k <= 21 and k not in (8, 10, 16, 20):
                if k == 5:
                    n = m.vcall(m.call(m.main + 0x114ACBC, o), 0x68, m.u64(m.main + 0x46E2700))
                    v = m.u64(s + 0x20)
                    t = 0x50 if v & 7 == 1 and (v >> 3) & 0x3F == (n - 1) & M32 else 0x4F
                else:
                    t = _APPLY_TEXT[k]
                m.put(msg, 2, t)
                m.put(msg + 4, 4, m.vcall(b, 0x98))
                m.put(msg + 2, 2, 0x82)
                if k == 0xD:
                    v = m.call(m.main + 0xF7FFE0, desc)
                    m.put(msg + 2, 2, 0x102)
                    m.put(msg + 8, 4, v & 0xFFFF)
            m.call_void(m.main + 0x114B0AC, m.u64(o + 0x20), uid, msg)
    elif text:
        m.call_void(m.main + 0x114B0AC, m.u64(o + 0x20), uid, text)
    u, b, k = m.u64(s), m.u64(s + 8), m.u16(s + 0x10)
    node = m.vcall(b + 0x28, 0)
    static = m.call(m.main + 0x2D1FD38)
    while node and node != static:
        node = m.u64(node)
    if node and k == 3 and m.u16(b + 0x710) == 0x1EC and m.u16(b + 0x718) == 1:
        m.call_void(m.main + 0x282F7A4, m.u64(o + 0x38), b)
        m.call_void(m.main + 0x13606C4, m.u64(o + 0x20), m.vcall(b, 0x98) & M32)
        m.call_void(m.main + 0x187FF90, b, 0, 0)
        m.call_void(m.main + 0x187FE48, m.u64(o + 0x20), m.vcall(b, 0x98) & M32, 0, 0)
        m.call_void(m.main + 0x119AFF0, m.u64(m.u64(o + 0x20) + 0x18), 0xAC, m.vcall(b, 0x98) & M32)
        m.call_void(m.main + 0x114F1EC, m.u64(o + 0x20), m.u64(o + 0x38), b)
        who = m.vcall(u, 0x98) & M32 if u else 0
        m.call_void(m.main + 0x157EBC0, m.u64(m.u64(o + 0x20) + 0x18), 0xCB, who, 0x4C, m.vcall(b, 0x98) & M32,
                    0xFFFF0000)
    k = m.u16(s + 0x10)
    if k <= 5:
        m.call_void(m.main + 0x2835034, m.u64(o + 0x38), m.u64(s + 8), m.u64(s), k, m.u64(s + 0x18), m.u64(s + 0x20))
    elif k == 0x10:
        m.call_void(m.main + 0x287E310, o, m.u64(s + 8), m.u64(s), k)
    else:
        m.call_void(m.main + 0x2D0CDF4, m.u64(o + 0x38), m.u64(s + 8), m.u64(s), k)
    if not m.u8(s + 0x38):
        m.call_void(m.main + 0x177767C, o, m.u64(s + 8))
    if m.u16(s + 0x10) == 5:
        with m.frame(0x20) as f:
            m.put(f + 8, 8, 0x1D); m.put(f + 0x10, 2, 0); m.put(f + 0x12, 1, 0); m.put(f + 0x14, 2, 0)
            m.put(f + 0xC, 4, m.vcall(m.u64(s + 8), 0x98))
            m.put(f, 1, 0)
            m.call_void(m.main + 0x121BDB0, m.u64(m.u64(o + 0x78) + 0x1D40), f, f + 8)


@lifted(0x287E388)
def after_condition_16(m, o, _out, pb, *_):
    """Event 0x8a for battler [pb]; a battler of form 0x7f then goes through 0x2888968."""
    b = m.u64(pb)
    m.call_void(m.main + 0x283544C, m.call(m.main + 0x1146E90, o), b)
    if m.vcall(b, 0xF0) & 0xFFFF == 0x7F:
        return _tail(m, m.main + 0x2888968, o, b)


@lifted(0x287E310)
def condition_16(m, o, b, *_):
    """Unless b is form 0x100 or vf 0x438 says so: 0x287e388 for b."""
    if m.vcall(b, 0xF0) & 0xFFFF != 0x100 and m.vcall(b, 0x438) & 1:
        return
    with m.frame(0x10) as f:
        m.put(f, 8, b)
        m.call_void(m.main + 0x287E388, m.call(m.main + 0x287E380, m.u64(o + 0x78)), f + 8, f)


@lifted(0x1793740)
def secondary_condition(m, o, mv, a, b, out, *_):
    """The move's secondary condition on b: its kind, chance and target descriptor (0x1793efc), event
    0x84 (parameters 4/3 the ids, 0x12 the move, 0x1f the descriptor, 0x1e the kind, 0x48 0, 0x29 the
    chance); unless rule bit 5 of +0x49a, a kind, a positive chance, no 0x48 and a roll below it give
    the kind with the descriptor in out (16 bytes); 0 otherwise."""
    with m.frame(0x10) as d:
        m.call_void(m.main + 0x179372C, d)
        kind = m.call(m.main + 0x1793E2C, mv)
        x = m.call(m.main + 0x1793E94, mv)
        pct = m.call(m.main + 0x1793E60, mv)
        r = m.u64(o + 0x18)
        m.call_void(m.main + 0x1793EFC, m.u64(r + 8), x, a, d, m.u64(r + 0x10))
        def read(ctx):
            return _value(m, ctx, 0xF8), _value(m, ctx, 0x150), _value(m, ctx, 0x248)
        k, c, stop = _event(m, o, 0x84, ((4, _id(m, b), 4, 0x28), (3, _id(m, a), 4, 0x20), (0x12, mv & 0xFFFF, 4, 0x98),
                                         (0x1F, d, "ptr", 0x100), (0x1E, kind & 0xFFFF, 0, 0xF8), (0x48, 0, 1, 0x248),
                                         (0x29, pct, 0, 0x150)), None, read)
        if m.u8(m.u64(m.u64(o + 8) + 0x38) + 0x49A) & 0x20:
            return 0
        if k & 0xFFFF == 0 or _s32(c) < 1 or stop & 0xFF:
            return 0
        if not m.call(m.main + 0x114DA8C, m.u64(m.u64(o + 0x18) + 0x10), c) & 1:
            return 0
        m.write(out, m.read(d, 0x10))
        return k


@lifted(0x114BD20)
def condition_bit_25(m, pair, *_):
    """Bit 25 of a condition entry's second word, for kinds 1 to 4."""
    w = m.u64(pair + 8)
    return (w >> 25) & 1 if 1 <= w & 7 <= 4 else 0


@lifted(0x2882ADC)
def request_code_3(m, o, b, *_):
    """Apply a one-battler request {b's id, code 3, b's id, +0x30 = 1} through 0x17cdf14."""
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x70))
        r = sp + 0x10
        m.put(r + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, r + 0x38)
        m.put(r, 4, m.vcall(b, 0x98) & M32); m.put(r + 4, 4, 3)
        m.put(r + 8, 4, m.vcall(b, 0x98) & M32)
        m.put(r + 0x35, 1, 0); m.put(r + 0x30, 1, 1)
        m.call_void(m.main + 0x17CDF14, m.call(m.main + 0x17CDF0C, m.u64(o + 0x78)), sp, r)


_FORM_TEXT = {1: 0x2D3, 2: 0x2D0, 3: 0x2D4, 4: 0x2D2, 5: 0x2D1}   # jump table 0x3c6a62e


@lifted(0x1143AF4)
def status_requests(m, o, *_):
    """For each member 0x1143db8 lists, outside rule bit 2 with fewer than two of [[o+8]+0x38]+0x30: one
    with no slot level 1..4, vf 0x460 >= 220, a status (vf 0x230) and 0x114d360(0x14) nonzero applies the
    request {id, status, id, text by status} through 0x17cdf14, then command 0xb3 (id, 0)."""
    with m.frame(0x190) as sp:
        lst = sp + 8
        m.call_void(m.main + 0x1143D84, lst)
        m.call_void(m.main + 0x1143DB8, o, lst)
        m.call_void(m.main + 0x1143D7C, lst)
        for t in _walk_pre_resume(m, lst):
            rules = m.u64(m.u64(o + 8) + 0x38)
            if m.u8(rules + 0x499) >> 2 & 1 or m.u32(rules + 0x30) > 1:
                continue
            slots = m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50)
            p = m.call(m.main + 0x10E2DD4, slots, m.vcall(t, 0x98) & M32)
            if p and 0 < m.s(p, 4) <= 4:
                continue
            if m.vcall(t, 0x460) & 0xFF < 0xDC:
                continue
            status = m.vcall(t, 0x230) & 0xFFFF
            if not status or not m.call(m.main + 0x114D360, o, 0x14) & M32:
                continue
            ident = m.vcall(t, 0x98) & M32
            slots = m.u64(m.u64(m.u64(m.u64(o + 0x10) + 0x290) + 8) + 0x50)
            p = m.call(m.main + 0x10E2DD4, slots, ident)
            level = 0
            if p:
                v = m.s(p, 4)
                level = v & 0xFF if v < 5 else 0
            req = sp + 0xC8
            m.write(req, bytes(0x60))
            m.put(req, 4, ident); m.put(req + 4, 4, status); m.put(req + 8, 4, ident)
            m.put(req + 0x30, 1, 1); m.put(req + 0x35, 1, 1)
            if status in _FORM_TEXT:
                m.put(req + 0x38, 2, _FORM_TEXT[status]); m.put(req + 0x3A, 2, 0x101)
                m.put(req + 0x3C, 4, ident); m.put(req + 0x40, 4, level)
            m.call_void(m.main + 0x17CDF14, m.u64(m.u64(o + 0x78) + 0xAE0), sp + 0xB8, req)
            q = m.call(m.main + 0x1143584, o)
            m.call_void(m.main + 0x1832FA4, q, m.vcall(t, 0x98) & M32, 0)


def _code_request(m, b, code, queue, extra=None):
    """Apply the one-battler request {b's id, code, b's id, +0x30 = 1} through 0x17cdf14 on `queue`;
    `extra(aux)` fills the aux record at +0x38 and the request takes +0x35 = 1."""
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x70))
        r = sp + 0x10
        m.put(r + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, r + 0x38)
        m.put(r, 4, m.vcall(b, 0x98) & M32); m.put(r + 4, 4, code)
        m.put(r + 8, 4, m.vcall(b, 0x98) & M32)
        m.put(r + 0x30, 1, 1); m.put(r + 0x35, 1, 1 if extra else 0)
        if extra:
            extra(r + 0x38)
        m.call_void(m.main + 0x17CDF14, queue, sp, r)


@lifted(0x288B840)
def request_code_2(m, o, b, *_):
    _code_request(m, b, 2, m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o)))


@lifted(0x1482DE4)
def request_code_3_of(m, o, b, *_):
    _code_request(m, b, 3, m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o)))


@lifted(0x288B8DC)
def request_code_6(m, o, b, *_):
    def extra(aux):
        m.call_void(m.main + 0x2843244, aux, 2, 0x76)
        m.call_void(m.main + 0x284325C, aux, m.vcall(b, 0x98) & M32)
    _code_request(m, b, 6, m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o)), extra)


@lifted(0x1581098)
def drain_4e8(m, o, b, *_):
    """Apply b's vf 0x4e8 values through 0x1140198 until it answers 0x20."""
    while True:
        w = m.vcall(b, 0x4E8)
        if w & M32 == 0x20:
            return w
        m.call_void(m.main + 0x1140198, m.call(m.main + 0x1143584, o), b, w & M32)


@lifted(0x1580E50)
def request_1b(m, o, b, *_):
    """With b's condition 0x1b: a request {id, 0x1b, id, +0x30 = 1, +0x35 = 1} through 0x17cdf14, then vf
    0x508(0xb)."""
    r = m.vcall(b, 0x220, 0x1B)
    if not r & 1:
        return r
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x70))
        q = sp + 0x10
        m.put(q + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, q + 0x38)
        m.put(q, 4, m.vcall(b, 0x98) & M32); m.put(q + 4, 4, 0x1B)
        m.put(q + 8, 4, m.vcall(b, 0x98) & M32)
        m.put(q + 0x30, 1, 1); m.put(q + 0x35, 1, 1)
        m.call_void(m.main + 0x17CDF14, m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o)), sp, q)
    return m.vcall(b, 0x508, 0xB)


@lifted(0x1580E20)
def request_1b_then_drain(m, o, _out, pb, *_):
    m.call_void(m.main + 0x1580E50, o, m.u64(pb))
    return _tail(m, m.main + 0x1581098, o, m.u64(pb))


# Side-effect end texts by kind (s32 table 0x3c6a8c4); kinds with bit clear in 0x279ff have none.
_SIDE_END_TEXT = (0x271, 0x275, 0x27D, 0x281, 0x285, 0x289, 0x28D, 0x291, 0x295, 0x271, 0x271, 0x29D, 0x2A1,
                  0x2A5, 0x2CB, 0x271, 0x271, 0x279)


@lifted(0x288835C)
def side_end_text(m, o, who, side, kind, *_):
    """Command 0xca (who, text for `kind`, side byte) for the kinds bit-set in 0x279ff."""
    kind &= M32
    if kind > 0x11 or not 0x279FF >> kind & 1:
        return
    return _tail(m, m.main + 0x157EBC0, m.u64(o + 0x18), 0xCA, who & M32, _SIDE_END_TEXT[kind], side & 0xFF,
                 0xFFFF0000)


def _request(m, o, ident_of, code):
    """A one-battler request {id, code, id, +0x30 = 1, +0x35 = 1} through 0x17cdf14."""
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x70))
        q = sp + 0x10
        m.put(q + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, q + 0x38)
        m.put(q, 4, ident_of() & M32)
        m.put(q + 4, 4, code); m.put(q + 8, 4, ident_of() & M32)
        m.put(q + 0x30, 1, 1); m.put(q + 0x35, 1, 1)
        return _tail(m, m.main + 0x17CDF14, m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o)), sp, q)


@lifted(0x1150CE8)
def request_code_32(m, o, *_):
    """Request code 0x32 for the battler 0x1142508 names."""
    return _request(m, o, lambda: m.vcall(m.call(m.main + 0x1142508, o), 0x98), 0x32)


@lifted(0x287FE9C)
def run_17776d8_7(m, o, b, *_):
    """0x17776d8 with the record {b's id, 7}."""
    with m.frame(0x20) as f:
        r = f + 0x10
        m.put(r, 4, m.vcall(b, 0x98) & M32); m.put(r + 4, 1, 7)
        x = m.call(m.main + 0x17776D0, m.call(m.main + 0x1361214, o))
        m.call_void(m.main + 0x17776D8, x, f + 8, r)


@lifted(0x1143158)
def status_requests_of(m, o, *_):
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x1143AF4, m.call(m.main + 0x1143184, m.u64(o + 0x78)), f, f + 8)


@lifted(0x288BAB4)
def request_thaw(m, o, b, mv, *_):
    """Request {id, 3, id, +0x30 = 1, +0x35 = 1} with text (2, 0x66, id, move) through 0x17cdf14."""
    with m.frame(0x70) as sp:
        m.write(sp, bytes(0x70))
        q = sp + 0x10
        m.put(q + 4, 4, 0x31)
        m.call_void(m.main + 0x1146154, q + 0x38)
        m.put(q, 4, m.vcall(b, 0x98) & M32); m.put(q + 4, 4, 3)
        m.put(q + 8, 4, m.vcall(b, 0x98) & M32)
        m.put(q + 0x30, 1, 1); m.put(q + 0x35, 1, 1)
        m.call_void(m.main + 0x2843244, q + 0x38, 2, 0x66)
        m.call_void(m.main + 0x284325C, q + 0x38, m.vcall(b, 0x98) & M32)
        m.call_void(m.main + 0x284325C, q + 0x38, mv & 0xFFFF)
        x = m.call(m.main + 0x17CDF0C, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x17CDF14, x, sp, q)


@lifted(0x1361224)
def raise_side_condition(m, o, out, r, *_):
    """r = (u32 kind, battler or 0): set the condition (0x1361ad8 for the field, 0x13616f0 + command 0x33
    for a battler); when it takes, 0x114beb0 and 0x1361c58, then 0x2880d90 for kind 5, 0x2880e44 for kind 8,
    and for kind 9 vf 0x4e0(0x1d) or 0x282f9d4 on every standing member in speed order. out = whether it
    took. Kind 8 is skipped when 0x13616dc and 0x13616e4 agree."""
    m.put(out, 1, 0)
    kind, b = m.u32(r), m.u64(r + 8)
    if kind == 5:
        _need(m, m.main + 0x2880D90)
    if kind == 9:
        _need(m, m.main + 0x282F9D4)
    if kind == 8 and m.call(m.main + 0x13616DC, m.u64(m.u64(o + 0x10) + 0x70)) & 0xFF \
            == m.call(m.main + 0x13616E4, m.u64(o + 8)) & 0xFF:
        return
    c = m.u64(o + 0x20)
    if not b:
        ok = m.call(m.main + 0x1361AD8, c, kind)
    else:
        ident = m.vcall(b, 0x98) & M32
        ok = m.call(m.main + 0x13616F0, m.u64(m.u64(m.u64(c + 0x20) + 0x10) + 0x70), kind, ident)
        m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x33, ident, kind & 0xFF)
    if not ok & 1:
        return
    m.call_void(m.main + 0x114BEB0, m.u64(o + 0x20), m.u32(r))
    bid = m.vcall(m.u64(r + 8), 0x98) & M32 if m.u64(r + 8) else 0
    m.call_void(m.main + 0x1361C58, o, bid, m.u32(r))
    if m.u32(r) == 5:
        m.call_void(m.main + 0x2880D90, o)
    if m.u32(r) == 8:
        m.call_void(m.main + 0x2880E44, o)
    if m.u32(r) == 9:
        with m.frame(0xF0) as sp:
            lst = sp + 0x38
            m.call_void(m.main + 0x1144704, o, lst)
            m.put(sp + 8, 8, lst)
            m.call_void(m.main + 0x1143E3C, m.u64(m.u64(o + 0x78) + 0x17E0), sp + 0x10, sp + 8)
            m.put(lst + 0xA8, 1, 0)
            if m.u8(lst + 0xA6):
                m.put(lst + 0xA8, 1, 1)
                p = m.u64(lst)
                while p:
                    if m.vcall(p, 0x4D0, 0x1D) & 1:
                        m.vcall_void(p, 0x4E0, 0x1D)
                    else:
                        m.call_void(m.main + 0x282F9D4, m.u64(o + 0x38), m.vcall(p, 0x98) & M32)
                    i = m.u8(lst + 0xA8)
                    if i >= m.u8(lst + 0xA6):
                        break
                    m.put(lst + 0xA8, 1, i + 1)
                    p = m.u64(lst + 8 * i)
    m.put(out, 1, 1)


def _raise_condition(m, o, kind, b):
    with m.frame(0x20) as sp:
        r = sp + 0x10
        m.write(r, bytes(0x10))
        m.put(r, 4, kind); m.put(r + 8, 8, b)
        x = m.call(m.main + 0x136121C, m.call(m.main + 0x1361214, o))
        return _tail(m, m.main + 0x1361224, x, sp + 8, r)


@lifted(0x28889A0)
def raise_field_condition(m, o, kind, *_):
    """0x1361224 with {kind, no battler}."""
    return _raise_condition(m, o, kind & M32, 0)


@lifted(0x1360FFC)
def raise_every_condition(m, o, b, *_):
    """0x1361224 with {k, b} for k = 0..13."""
    for k in range(14):
        r = _raise_condition(m, o, k, b)
    return r


@lifted(0x288DA60)
def end_side_condition(m, rec, *_):
    """When the count +0x20 is set: clear the kind bits (low 3) of +0x10 and the 8 bytes at +0x1c; 1."""
    if not m.u32(rec + 0x20):
        return 0
    v = m.u64(rec + 0x10) & ~7 & M64
    m.put(rec + 0x1C, 8, 0)
    m.put(rec + 0x10, 8, v)
    return 1


@lifted(0x2888400)
def end_side_condition_and_queue(m, c, side, k, *_):
    """For side 0 or 1: end the side condition k (0x288da60) and queue command 0x4b (side, k)."""
    if not m.call(m.main + 0x288D980, side) & 1:
        return 0
    x = m.call(m.main + 0x13DF9D4, m.u64(c + 0x10), side, k)
    if not x:
        return 0
    if not m.call(m.main + 0x288DA60, x) & 1:
        return 0
    m.call_void(m.main + 0x119AFF0, m.u64(c + 0x18), 0x4B, side & 0xFF, k & M32)
    return 1


@lifted(0x11431C0)
def tick_side_conditions(m, o, *_):
    """For both sides and the 19 side conditions with a count (+0x20 of each 0x28-byte entry from
    [[o+0x10]+0x90]+8) whose kind (low 3 bits of +0x10) is 2 or 4: count one turn (0x2888a5c); when the
    count is reached (0x2888ab8), end it (0x2888400 / 0x2888474) and queue its end text 0x288835c."""
    for side, base in ((0, 0x28), (1, 0x320)):
        for k in range(0x13):
            e = m.u64(m.u64(o + 0x10) + 0x90) + base + 0x28 * k
            if not m.u32(e):
                continue
            x = e - 0x20
            p = m.call(m.main + 0x1143354, x)
            kind = m.u32(p + 8) & 7
            if kind not in (2, 4):
                continue
            m.call_void(m.main + 0x2888A5C, m.call(m.main + 0x1143584, o), side, k)
            if not m.call(m.main + 0x2888AB8, x) & 1:
                continue
            if m.call(m.main + 0x2888400, m.call(m.main + 0x1143584, o), side, k) & 1:
                m.call_void(m.main + 0x2888474, m.call(m.main + 0x1143584, o), side, k)
            m.call_void(m.main + 0x288835C, m.call(m.main + 0x1143584, o), m.u32(p), side, k)


@lifted(0x114318C)
def tick_side_conditions_of(m, o, *_):
    with m.frame(0x10) as f:
        return _tail(m, m.main + 0x11431C0, m.call(m.main + 0x11431B8, m.u64(o + 0x78)), f, f + 8)
