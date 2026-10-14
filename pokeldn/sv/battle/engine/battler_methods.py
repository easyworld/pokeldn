"""Battler methods reached through its vtable (main+0x44fbcb0): small getters, setters and the calls
it hands to the Pokemon object it holds at +0x48."""

from pokeldn.sv.battle.machine import lifted

MOVE_SLOT, MOVE_COUNT = 0x16, 0x482


def _core(m, b):
    return m.u64(b + 0x48)


def _forward(slot, *fixed):
    """A method that calls `slot` of the object at +0x48 with the given leading arguments, then the
    caller's remaining ones, and returns its result."""
    def fn(m, b, *args):
        return m.vcall(_core(m, b), slot, *(fixed + args[:4 - len(fixed)]))
    return fn


for _addr, _slot, _fixed in ((0x2D3BC88, 0x70, (0,)), (0x2D3BCAC, 0x70, (1,)), (0x2D3BCD0, 0x70, (2,)),
                             (0x2D3BCF4, 0x70, (3,)), (0x2D3BD18, 0x70, (4,)), (0x2D3BD3C, 0x70, (5,)),
                             (0x2D3EE3C, 0x1B0, (9,)), (0x2D3CD80, 0x170, ()), (0x2D3CD90, 0x178, ()),
                             (0x2D3E6E4, 0xC8, ()), (0x2D3EE60, 0x1C0, ())):
    lifted(_addr)(_forward(_slot, *_fixed))


def _own(slot):
    def fn(m, b, *args):
        return m.vcall(b, slot, *args[:4])
    return fn


lifted(0x2A10910)(_own(0x78))
lifted(0x2A1091C)(_own(0x98))


@lifted(0x2A10930)
def own_730(m, b, *args): return m.vcall(b, 0x730, *args[:4]) & 0xFFFF


@lifted(0x2A10950)
def own_740(m, b, *args): return m.vcall(b, 0x740, *args[:4]) & 0xFFFF


@lifted(0x2D3BF0C)
def is_41c_1fe(m, b, *_): return int(m.u16(b + 0x41C) == 0x1FE)


@lifted(0x2D3C250)
def condition_entry(m, b, cond, *_):
    """The 16-byte entry of condition `cond` (+0x80), returned in x0 and x1."""
    from pokeldn.sv.battle.machine import Pair
    e = b + 0x80 + 0x10 * (cond & 0xFFFF)
    return Pair(m.u64(e), m.u64(e + 8))


@lifted(0x2D3C25C)
def condition_turns(m, b, cond, *_): return m.u8(b + 0x390 + (cond & 0xFFFF))


@lifted(0x2D3B708)
def field_3e0(m, b, *_): return b + 0x3E0


@lifted(0x2D3D8B0)
def slot_4a0(m, b, i, *_): return b + 0x4A0 + 8 * (i & 0xFFFFFFFF)


@lifted(0x2D3D8BC)
def set_slot_4a0(m, b, i, src, *_): m.put(b + 0x4A0 + 8 * (i & 0xFFFFFFFF), 8, m.u64(src))


@lifted(0x2D3ECEC)
def has_6f8(m, b, *_): return int(m.u32(b + 0x6F8) != 0)


def _move_byte(off):
    def fn(m, b, i, *_): return m.u8(b + off + MOVE_SLOT * (i & 0xFF))
    return fn


lifted(0x2D3C94C)(_move_byte(0x428))
lifted(0x2D3C988)(_move_byte(0x429))


@lifted(0x2D3CB40)
def move_43a_clear(m, b, i, *_): return int(m.u8(b + 0x43A + MOVE_SLOT * (i & 0xFF)) == 0)


@lifted(0x2D1F674)
def is_710(m, b, v, *_): return int(m.u16(b + 0x710) == v & 0xFFFF)


@lifted(0x2D1F684)
def is_710_718(m, b, v, w, *_):
    return int(m.u16(b + 0x710) == v & 0xFFFF and m.u16(b + 0x718) == w & 0xFFFF)


@lifted(0x2D3E338)
def copy_6f2(m, b, other, *_): m.put(b + 0x6F2, 2, m.u16(other + 0x6F2))


@lifted(0x2D3E610)
def set_5a0(m, b, i, v, *_): m.put(b + 0x5A0 + (i & 0xFFFFFFFF), 1, v)


@lifted(0x2D3C7D8)
def move_433_minus_432(m, b, i, *_):
    s = b + MOVE_SLOT * (i & 0xFF)
    return (m.u8(s + 0x433) - m.u8(s + 0x432)) & 0xFFFFFFFF


@lifted(0x2D3C7F4)
def move_429_minus_428(m, b, i, *_):
    s = b + MOVE_SLOT * (i & 0xFF)
    return (m.u8(s + 0x429) - m.u8(s + 0x428)) & 0xFFFFFFFF


@lifted(0x2D3B7F0)
def set_6d_74(m, b, v, *_): m.put(b + 0x6D, 1, 1); m.put(b + 0x74, 4, v)


@lifted(0x2D3E6FC)
def clear_6d_74(m, b, *_): m.put(b + 0x6D, 1, 0); m.put(b + 0x74, 4, 0)


@lifted(0x2D3D240)
def not_4e8_20(m, b, *_): return int(m.vcall(b, 0x4E8) & 0xFFFFFFFF != 0x20)


@lifted(0x2D3D264)
def has_540_4(m, b, *_): return int(m.vcall(b, 0x540, 4) & 0xFF != 0)


@lifted(0x2D3E3D0)
def has_338(m, b, *_): return int(m.vcall(b, 0x338) & 0xFF != 0x12)


@lifted(0x2D3B764)
def clear_7c_78(m, b, *_): m.put(b + 0x7C, 1, 0); m.put(b + 0x78, 4, 0)


@lifted(0x2D3D168)
def set_flag_49e(m, b, i, *_):
    i &= 0xFFFFFFFF
    a = b + ((i >> 3) & 0xFF) + 0x49E
    m.put(a, 1, m.u8(a) | (1 << (i & 7)))


@lifted(0x2D3DC34)
def clear_flag_496(m, b, i, *_):
    i &= 0xFFFFFFFF
    a = b + ((i >> 3) & 0xFF) + 0x496
    m.put(a, 1, m.u8(a) & ~(1 << (i & 7)))


@lifted(0x2D3D884)
def clear_flag_49a(m, b, i, *_):
    i &= 0xFFFFFFFF
    a = b + ((i >> 3) & 0xFF) + 0x49A
    m.put(a, 1, m.u8(a) & ~(1 << (i & 7)))
    m.vcall_void(b, 0x500, i)


@lifted(0x2D3ECBC)
def set_6f8(m, b, v, w, *_): m.put(b + 0x6F8, 4, v); m.put(b + 0x6F4, 2, w)


@lifted(0x2D3E418)
def set_5e(m, b, v, *_): m.put(b + 0x5E, 2, v); m.put(b + 0x5C, 2, 0)


@lifted(0x80120C)
def first_of_30(m, o, *_):
    p = m.u64(o + 0x30)
    return m.u64(p) if p else 0


def _byte_3c2(m, b, i, *_):
    i &= 0xFF
    return m.u8(b + 0x3C2 + i) if i < m.u8(b + 0x3C1) else 0


lifted(0x2D3EBA0)(_byte_3c2)
lifted(0x2D3B874)(_byte_3c2)


@lifted(0x2D3E648)
def set_counter_5a8(m, b, i, v, *_):
    i &= 0xFF
    if i < 9:
        m.put(b + 0x5A8 + 4 * i, 4, v)


@lifted(0x2D3D798)
def set_484(m, b, v, *_):
    if v & 0xFF < 4:
        m.put(b + 0x484, 1, v)


def _slot_getter(off, size, default):
    def fn(m, b, i, *_):
        i &= 0xFF
        return m.u(b + off + MOVE_SLOT * i, size) if i < m.u8(b + MOVE_COUNT) else default
    return fn


lifted(0x2D3C960)(_slot_getter(0x433, 1, 0))
lifted(0x2D3C5FC)(_slot_getter(0x430, 2, 0xA5))
lifted(0x2D3C77C)(_slot_getter(0x438, 1, 0))


@lifted(0x2D3C654)
def move_435(m, b, i, *_):
    i &= 0xFF
    return int(i < m.u8(b + MOVE_COUNT) and m.u8(b + 0x435 + MOVE_SLOT * i) != 0)


@lifted(0x2D3C684)
def move_436(m, b, i, *_):
    i &= 0xFF
    return int(i < m.u8(b + MOVE_COUNT) and m.u8(b + 0x436 + MOVE_SLOT * i) != 0)


@lifted(0x2D3BF7C)
def hp_full(m, b, *_):
    return int(m.vcall(b, 0x108) & 0xFFFF == m.vcall(b, 0x110) & 0xFFFF)


@lifted(0x2D3E4A4)
def set_480(m, b, v, *_): m.put(b + 0x480, 2, v if v & 0xFFFF else 1)


@lifted(0x2D3E3A4)
def set_added_type(m, b, t, v, *_):
    t &= 0xFF
    if m.u8(b + 0x40A) != t and m.u8(b + 0x40B) != t:
        m.put(b + 0x40C, 1, t); m.put(b + 0x410, 4, v)


@lifted(0x2D3EAE4)
def set_6f2_and_610(m, b, v, *_):
    m.put(b + 0x6F2, 2, v)
    m.vcall_void(b, 0x610, 8)


@lifted(0x2D3E710)
def both_6c_clear(m, b, other, *_):
    return int(m.u8(b + 0x6C) == 0 and m.u8(other + 0x6C) == 0 and m.u16(other + 0x6F2) == 0)


@lifted(0x2D3E408)
def shift_5c(m, b, *_):
    v = m.u16(b + 0x5C); m.put(b + 0x5C, 2, 0); m.put(b + 0x5E, 2, v)


@lifted(0x2D3CBB8)
def knows_move(m, b, move, *_):
    move &= 0xFFFF
    return int(any(m.u16(b + 0x430 + MOVE_SLOT * i) == move for i in range(4)))


@lifted(0x2D3E61C)
def bump_5a0(m, b, i, *_):
    a = b + 0x5A0 + (i & 0xFFFFFFFF)
    if m.u8(a) != 0xFF:
        m.put(a, 1, m.u8(a) + 1)


@lifted(0x2D3ECC8)
def get_6f8(m, b, out1, out2, *_):
    if m.u32(b + 0x6F8):
        m.put(out1, 4, m.u32(b + 0x6F8)); m.put(out2, 2, m.u16(b + 0x6F4))
        return 1
    return 0


@lifted(0x2D3D42C)
def any_stage_below_6(m, b, *_):
    """Whether any of the seven stat stages (+0x414..+0x41a, 6 = neutral) is below neutral."""
    return int(any(m.s(b + 0x414 + i, 1) <= 5 for i in range(7)))


@lifted(0x2D3DB54)
def clear_turn_conditions(m, b, *_):
    m.put(b + 0x399, 1, 0); m.write(b + 0x90, bytes(0x50)); m.put(b + 0x110, 8, 0); m.put(b + 0x118, 8, 0)
    m.put(b + 0x391, 4, 0); m.put(b + 0x395, 1, 0)


@lifted(0x2D3B3B0)
def set_480_from_core(m, b, *_):
    v = m.vcall(_core(m, b), 0x180) & 0xFFFF
    m.put(b + 0x480, 2, v or 1)


@lifted(0x2D3B800)
def shown_id(m, b, *_):
    return m.vcall(b, 0x98) if m.u8(b + 0x6D) == 0 else m.u32(b + 0x74)


@lifted(0x2D3CA6C)
def mark_42c(m, b, i, *_):
    s = b + MOVE_SLOT * (i & 0xFF)
    if m.u8(s + 0x43A) == 0 and m.u8(s + 0x42C) == 0:
        m.put(s + 0x42C, 1, 1); m.put(b + 0x485, 1, m.u8(b + 0x485) + 1)


@lifted(0xF7FFE0)
def condition_value(m, pair, *_):
    """The value a condition entry carries (bits 9.. of its second word) for kinds 1 to 4."""
    w = m.u64(pair + 8)
    return w >> 9 if w & 7 in (1, 2, 3, 4) else 0


def _staged(base_slot, stage_off):
    from pokeldn.sv.battle.engine.battler import STAGE_RATIO

    def fn(m, b, *_):
        v = m.vcall(b, base_slot)
        stage = m.u8(b + stage_off)
        if stage >= 13:
            return v
        num, den = STAGE_RATIO[stage]
        return ((v * num) & 0xFFFF) // den & 0xFFFFFFFF
    return fn


# Attack, Defense, Sp. Atk, Sp. Def with their stages at +0x414..+0x417 (Speed is 0x2d3beb0).
for _addr, _slot, _off in ((0x2D3BD60, 0xC0, 0x414), (0x2D3BDB4, 0xC8, 0x415),
                           (0x2D3BE08, 0xD0, 0x416), (0x2D3BE5C, 0xD8, 0x417)):
    lifted(_addr)(_staged(_slot, _off))


@lifted(0x287A554)
def marker(m, *_):
    from pokeldn.sv.battle.engine.getters import static_46d3f08
    return static_46d3f08(m)


@lifted(0x2D3BB74)
def ability_unless(m, b, *_):
    if m.vcall(b, 0x220, 0x10) & 1 == 0 and m.vcall(b, 0x438) & 1 == 0:
        return m.vcall(b, 0xF0)
    return 0


@lifted(0x2D3ED14)
def is_47e_unless(m, b, v, *_):
    if m.vcall(b, 0x220, 0x10) & 1 == 0 and m.vcall(b, 0x438) & 1 == 0:
        return int(m.u16(b + 0x47E) == v & 0xFFFF)
    return 0


@lifted(0x2D3C99C)
def move_pp_full(m, b, i, base, *_):
    s = b + MOVE_SLOT * (i & 0xFF) + (0x426 if base & 1 else 0x430)
    return int(m.u16(s) != 0 and m.u8(s + 2) == m.u8(s + 3))


@lifted(0x2D3DB0C)
def count_condition_e8(m, b, *_):
    w = m.u64(b + 0xE8)
    kind, limit = w & 7, (w >> 3) & 0x3F
    if kind in (2, 4) and limit:
        t = (m.u8(b + 0x396) + 1) & 0xFF
        m.put(b + 0x396, 1, t)
        if limit <= t:
            return 1
    return 0


@lifted(0x2D3DB94)
def clear_condition(m, b, cond, *_):
    cond &= 0xFFFF
    if cond < 6:
        m.vcall_void(b, 0x608, cond)
        return
    m.put(b + 0x80 + 0x10 * cond, 8, 0); m.put(b + 0x88 + 0x10 * cond, 8, 0); m.put(b + 0x390 + cond, 1, 0)


@lifted(0x2D3C064)
def neither_19_nor_1a(m, b, *_):
    if m.vcall(b, 0x4D0, 0x19) & 1:
        return 0
    return ~m.vcall(b, 0x4D0, 0x1A) & 1


@lifted(0x2D3C624)
def base_move(m, b, i, *_):
    i &= 0xFF
    if i < 4:
        v = m.u16(b + 0x426 + MOVE_SLOT * i)
        return v if v else 0xA5
    return 0xA5


@lifted(0x2D3E570)
def turn_count_back(m, b, back, *_):
    back &= 0xFF
    if back < 3:
        i = m.u8(b + 0x6EF) - back
        return m.u8(b + 0x6EC + (i if i >= 0 else i + 3))
    return 0


@lifted(0x2D3EB18)
def take_6f2(m, b, want_ptr, *_):
    have, want = m.u16(b + 0x6F2), m.u16(want_ptr)
    left = have - want
    done = have <= want
    if done:
        left = 0
        m.put(want_ptr, 2, have)
    m.put(b + 0x6F2, 2, left)
    return int(done)


@lifted(0x2D3C198)
def condition_228_value(m, b, *_):
    w = m.u64(b + 0x228)
    kind, v = w & 7, (w >> 9) & 0xFFFFFFFF
    return v if kind in (1, 2) else 0


@lifted(0x2D3C918)
def move_byte_432_of(m, b, move, *_):
    move &= 0xFFFF
    for i in range(m.u8(b + MOVE_COUNT)):
        if m.u16(b + 0x430 + MOVE_SLOT * i) == move:
            return m.u8(b + 0x432 + MOVE_SLOT * i)
    return 0


@lifted(0x2D3EBC0)
def in_3c2(m, b, v, *_):
    v &= 0xFFFFFFFF
    return int(any(m.u8(b + 0x3C2 + i) == v for i in range(m.u8(b + 0x3C1))))


@lifted(0x2D3C4CC)
def base_move_count(m, b, *_):
    if m.u16(b + 0x426) == 0:
        return 0
    if m.u16(b + 0x43C) == 0:
        return 1
    if m.u16(b + 0x452) == 0:
        return 2
    return 4 if m.u16(b + 0x468) else 3


def _any_of(count_slot, test_slot):
    def fn(m, b, *_):
        n = m.vcall(b, count_slot) & 0xFF
        return int(any(m.vcall(b, test_slot, i) & 0xFF for i in range(n)))
    return fn


lifted(0x2D3C810)(_any_of(0x708, 0x670))
lifted(0x2D3C880)(_any_of(0x710, 0x678))


def _condition_value_of(cond, require):
    def fn(m, b, *_):
        if require and m.vcall(b, 0x220, cond) & 1 == 0:
            return 0
        from pokeldn.sv.battle.machine import Pair
        with m.frame(16) as pair:
            p = m.vcall(b, 0x240, cond)
            m.put(pair, 8, p[0]); m.put(pair + 8, 8, p[1])
            if not require and p[1] & 7 == 0:
                return 0
            return condition_value(m, pair)
    return fn


lifted(0x2899E98)(_condition_value_of(0x1C, False))
lifted(0x2899E38)(_condition_value_of(0x1B, True))


@lifted(0x2D3CA2C)
def use_pp(m, b, i, n, *_):
    s = b + MOVE_SLOT * (i & 0xFF)
    if m.u8(s + 0x43A):
        return
    left = m.u8(s + 0x428) - (n & 0xFF)
    m.put(s + 0x428, 1, left if left >= 0 else 0)
    return m.vcall(_core(m, b), 0x118, i, n)


@lifted(0x2D1D474)
def slot_38_is(m, o, a, value, *_):
    return 1 if m.vcall(o, 0x38, a, value) & 0xFFFF == value & 0xFFFF else 0


@lifted(0x2D3D098)
def slot_2a8_unless_0x13(m, b, record, *_):
    """Slot 0x2a8, unless the record's +0xbc is set or condition 0x13 holds (then 0)."""
    if m.u32(record + 0xBC) or m.vcall(b, 0x220, 0x13) & 1:
        return 0
    return m.vcall(b, 0x2A8)
