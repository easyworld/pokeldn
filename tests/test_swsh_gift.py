"""The Wonder Card record and the beacon transport that carries it, pinned to what a retail Sword
showed (docs/swsh_gift.md)."""
import struct
from pathlib import Path

import pytest

from pokeldn.swsh import beacon, wc8


def test_record_checksum_is_ccitt_false_over_the_zeroed_field():
    rec = wc8.build(card_id=0x270F)
    assert len(rec) == 0x2D0 and wc8.sealed(rec)
    bad = bytearray(rec)
    bad[0x2CC] ^= 1
    assert not wc8.sealed(bad)
    # CRC-16/CCITT-FALSE of "123456789" is 0x29B1; the routine zeroes +0x2CC first
    probe = bytearray(0x2D0)
    probe[:9] = b"123456789"
    assert wc8.record_crc(probe) != 0x29B1     # the 0x2C7 trailing zeros are part of the sum


def test_names_go_where_the_console_read_them():
    rec = wc8.pokemon_card(25, level=30, nickname="POKELDN", ot="POKELDN")
    fields = wc8.read(rec)
    assert (fields["nickname"], fields["ot"]) == ("POKELDN", "POKELDN")
    assert rec[0x030:0x03E] == "POKELDN".encode("utf-16-le")
    assert rec[0x12C:0x13A] == "POKELDN".encode("utf-16-le")
    for i in range(9):                                     # every language slot carries the same name
        assert rec[0x030 + i * 0x1C:0x030 + i * 0x1C + 14] == "POKELDN".encode("utf-16-le")


def test_date_bitfield_matches_the_three_album_readings():
    # 18 October 2018 16:26 UTC showed 18/10/2018 18:26: absolute, UTC, month 1-based.
    rec = wc8.build(date=1539879960)
    assert wc8.unpack_date(rec) == (2018, 10, 18, 16, 26, 0)
    v = struct.unpack_from("<Q", rec, 0)[0]
    assert (v >> 26) & 0x3FFF == 2018 and (v >> 22) & 0xF == 10 and (v >> 17) & 0x1F == 18
    # The probe 01 02 .. 08 packs month 0 of year 321 and showed December of the year before.
    v = struct.unpack("<Q", bytes(range(1, 9)))[0]
    assert ((v >> 26) & 0x3FFF, (v >> 22) & 0xF, (v >> 17) & 0x1F) == (321, 0, 1)


def test_pokemon_fields_as_the_retail_console_showed_them():
    rec = wc8.pokemon_card(25, level=45, moves=(84, 45, 86, 98), nickname="POKELDN", ot="POKELDN",
                           tid=12345, sid=54321, ball=1, held_item=236, gender=1, nature=10,
                           ability_type=2, shiny_type=3, dynamax_level=10, gigantamax=1,
                           iv_hp=31, iv_atk=31, iv_def=31, iv_spe=31, iv_spa=31, iv_spd=31)
    f = wc8.read(rec)
    assert f["kind"] == 1 and f["species"] == 25 and f["level"] == 45 and f["met_level"] == 45
    assert (f["move1"], f["move2"], f["move3"], f["move4"]) == (84, 45, 86, 98)
    assert (f["tid"], f["sid"]) == (12345, 54321) and (54321 << 16 | 12345) % 1000000 == 993401
    assert (f["ball"], f["held_item"], f["gender"], f["nature"]) == (1, 236, 1, 10)
    assert (f["ability_type"], f["shiny_type"], f["dynamax_level"], f["gigantamax"]) == (2, 3, 10, 1)
    assert f["ribbons"] == () and rec[0x24C:0x26C] == b"\xff" * 0x20
    assert rec[0x26C:0x272] == bytes([31] * 6)
    assert f["region_mask"] == 0xFFFF and f["dedup"] == 0 and f["sealed"]


def test_unknown_field_is_refused():
    with pytest.raises(KeyError):
        wc8.pokemon_card(25, colour=1)


def test_a_card_is_three_fragments_sharing_one_pia_header():
    rec = wc8.pokemon_card(25, level=25, nickname="POKELDN", ot="POKELDN")
    blobs = beacon.build_message(rec)
    assert len(blobs) == 3 and all(len(b) == 0x180 for b in blobs)
    heads = {b[:0x18] for b in blobs}
    assert len(heads) == 1
    head = heads.pop()
    assert head[4:8] == bytes(4) and head[8:10] == bytes((5, 0x18)) and head[0x10:] == bytes(8)
    assert head[:4] != bytes(4) and head[0xC:0x10] != bytes(4)
    for i, b in enumerate(blobs):
        d = beacon.decode(b)
        assert d["stored_crc"] == d["computed_crc"] and d["network_id"] == 0xD70
        pl = d["payload"]
        assert pl[0] == 1 and struct.unpack_from("<IH", pl, 1) == (0, 0x2D0)
        assert (pl[7], pl[8]) == (3, i)
        assert struct.unpack_from("<H", pl, 9)[0] == beacon.crc16(rec)
    assert beacon.reassemble(blobs) == rec
    assert beacon.reassemble(blobs[::-1] + blobs[:1]) == rec        # order and repeats do not matter


def test_reassembly_refuses_what_the_console_refuses():
    rec = wc8.build()
    blobs = beacon.build_message(rec)
    with pytest.raises(ValueError, match="missing"):
        beacon.reassemble(blobs[:2])
    with pytest.raises(ValueError, match="checksum"):
        beacon.reassemble(beacon.build_message(rec, checksum=0))
    with pytest.raises(ValueError, match="fit"):
        beacon.build_message(b"")


def test_two_records_are_five_fragments():
    blobs = beacon.build_message(wc8.build() + wc8.build(card_id=2))
    assert len(blobs) == 5
    assert len(beacon.reassemble(blobs)) == 2 * 0x2D0


SWORD_IMAGE = "scratchpad/swsh/main.bin"
VALIDATOR = 0x010b5de0  # the game's Wonder Card check: 0 sealed, 0x80000001 checksum


def validate(record):
    """-> the game's validator's answer for `record`, run under unicorn from the user's own image."""
    from nso_run import SCRATCH, Runner
    r = Runner(SWORD_IMAGE)
    card, header, rec = SCRATCH + 0x1000, SCRATCH + 0x3000, SCRATCH + 0x4000
    r.write(card, bytes(0x3A8))
    r.write(header, bytes(0x68))
    r.write(rec, record)
    return r.call(VALIDATOR, (0, card, header, rec, len(record)))[0]


@pytest.mark.skipif(not __import__("os").path.exists(SWORD_IMAGE),
                    reason="needs Sword's extracted main NSO")
def test_the_host_sends_only_what_the_games_own_validator_accepts(tmp_path, monkeypatch, capsys):
    """The game's validator 0x010b5de0 runs under unicorn: a built card passes, one flipped byte
    returns the checksum error, and the host then refuses before it writes or sends anything."""
    import swsh_gift_host
    rec = wc8.pokemon_card(25, level=25, nickname="POKELDN", ot="POKELDN")
    assert validate(rec) == 0
    bad = bytearray(rec)
    bad[0x10] ^= 1
    assert validate(bytes(bad)) == 0x80000001

    (tmp_path / "bad.bin").write_bytes(bad)
    out = tmp_path / "out.bin"
    monkeypatch.setattr("sys.argv", ["swsh_gift_host.py", "--record", str(tmp_path / "bad.bin"),
                                     "--dump", str(out)])
    assert swsh_gift_host.main() == 1
    assert not out.exists()


def _sword_with_a_player(runner, gender):
    """Stand-ins for the objects the kind-4 and kind-5 code reaches through [[0x2610798]]: the player
    status (+0x1e8, gender byte +0x105), the wardrobe (+0x218) and the money holder (+0x208), each
    with lock slots that return at once."""
    from nso_run import SCRATCH
    ret, game, vtable = 0x01424c24, SCRATCH + 0x10000, SCRATCH + 0x12000
    objects = {"status": SCRATCH + 0x11000, "wardrobe": SCRATCH + 0x13000, "money": SCRATCH + 0x15000}
    runner.write(struct.unpack_from("<Q", runner.img, 0x2610798)[0], struct.pack("<Q", game))
    runner.write(vtable, struct.pack("<4Q", ret, ret, ret, ret))
    for at, name in ((0x1e8, "status"), (0x218, "wardrobe"), (0x208, "money")):
        runner.write(game + at, struct.pack("<Q", objects[name]))
        runner.write(objects[name], bytes(0x800))
        runner.write(objects[name] + 0x48, struct.pack("<Q", vtable))
    runner.write(objects["status"] + 0x105, bytes([gender]))
    return objects


def _redeem(runner, record, redemption):
    """The validator fills the 0x68-byte header, then the redemption runs on header + record."""
    import swsh_gift_host
    from nso_run import SCRATCH
    card, header, rec, pair = SCRATCH + 0x1000, SCRATCH + 0x3000, SCRATCH + 0x4000, SCRATCH + 0x14000
    runner.write(card, bytes(0x3A8))
    runner.write(header, bytes(0x68))
    runner.write(rec, record)
    assert runner.call(VALIDATOR, (0, card, header, rec, len(record)))[0] == 0
    runner.write(pair, bytes(runner.uc.mem_read(header, 0x68)) + record)
    runner.call(redemption, (pair,))


@pytest.mark.skipif(not __import__("os").path.exists(SWORD_IMAGE),
                    reason="needs Sword's extracted main NSO")
@pytest.mark.parametrize("gender", (0, 1))
def test_a_clothing_card_puts_its_outfit_for_the_players_gender_in_the_wardrobe(gender):
    """The game's own kind-4 redemption 0x01015eb0 under unicorn sets one wardrobe bit per pair
    (0x0143a450: 0x80 bytes per category from +0x68), the first six pairs for gender byte 0 and the
    last six otherwise; an index of -1 sets nothing."""
    from nso_run import Runner
    from pokeldn.swsh import gift_builder as swsh
    runner = Runner(SWORD_IMAGE)
    for preset in (p for p in swsh.PRESETS if p.state["kind"] == "clothing"):
        wardrobe = _sword_with_a_player(runner, gender)["wardrobe"]
        _redeem(runner, swsh.record(preset.state), 0x01015eb0)
        bits = bytes(runner.uc.mem_read(wardrobe + 0x68, 15 * 0x80))
        got = sorted((n // 0x80, n % 0x80 * 8 + k) for n, b in enumerate(bits) for k in range(8) if b >> k & 1)
        outfits = [swsh.OUTFIT[k] for k in preset.state["outfits"]]
        assert got == sorted(pair for o in outfits for pair in (o.female if gender else o.male)), preset.key


@pytest.mark.skipif(not __import__("os").path.exists(SWORD_IMAGE),
                    reason="needs Sword's extracted main NSO")
def test_a_money_card_adds_its_amount_up_to_the_games_cap():
    from nso_run import Runner
    from pokeldn.swsh import gift_builder as swsh
    runner = Runner(SWORD_IMAGE)
    for start, after in ((0, 100_000), (9_950_000, 9_999_999)):
        money = _sword_with_a_player(runner, 0)["money"]
        runner.write(money + 0x64, struct.pack("<I", start))
        _redeem(runner, swsh.record(swsh.PRESET["money"].state), 0x010160b0)
        assert struct.unpack("<I", bytes(runner.uc.mem_read(money + 0x64, 4)))[0] == after


def test_a_card_refuses_outfits_that_overflow_six_pieces_and_unknown_ones():
    from pokeldn.swsh import gift_builder as swsh
    with pytest.raises(ValueError, match="6 pieces"):
        swsh.record(swsh.blank(kind="clothing", outfits=["pikachu-uniform", "leon-cap-tights"]))
    with pytest.raises(ValueError, match="Unknown outfit"):
        swsh.record(swsh.blank(kind="clothing", outfits=["cape"]))
    with pytest.raises(ValueError, match="Money is 1"):
        swsh.record(swsh.blank(kind="money", money=10_000_000))


def test_every_official_event_card_is_sealed_and_puts_no_dummy_item_in_the_bag():
    """A ★ name or an id past the 1.3.2 table aborts the bag screen [docs/swsh_gift.md]."""
    from pokeldn import pokemon
    from pokeldn.swsh import events, gift_builder
    names = {n["id"]: n["name"] for n in pokemon.SERVICE.names("swsh", "items")}
    cards = events.load()
    assert len({c["key"] for c in cards}) == len(cards) and {c["group"] for c in cards} == set(events.GROUPS)
    for card in cards:
        assert wc8.sealed(card["record"]), card["key"]
        for item in events.item_ids(card["record"]):
            assert 0 < item <= gift_builder.MAX_ITEM and not names[item].startswith("★"), card["key"]


def test_the_pokemon_home_group_holds_one_card_per_home_gift_and_pkhex_takes_every_card():
    """Card ids from 9000 are the community's cards of Pokemon HOME's gifts, the latest revision of each;
    the 9013 Bulbasaur gives a Gigantamax factor its Venusaur uses [docs/swsh_gift.md, Official event cards]."""
    from pokeldn import pokemon
    from pokeldn.swsh import events
    cards = events.load()
    home = [c for c in cards if c["group"] == events.HOME]
    assert sorted(struct.unpack_from("<H", c["record"], 0x08)[0] for c in home) == [*range(9000, 9015), 9029]
    assert all(events.from_home(c["record"]) == (c["group"] == events.HOME) for c in cards)
    for card in home:                          # the first revision fixed every PID at 0
        fields = wc8.read(card["record"])
        assert fields["shiny_type"] != 4 or fields["pid"], card["key"]
    for card in cards:
        pokemon.SERVICE.validate_gift(card["record"])


@pytest.mark.skipif(not __import__("os").path.exists(SWORD_IMAGE),
                    reason="needs Sword's extracted main NSO")
def test_the_app_sends_an_official_event_with_a_date_and_the_game_accepts_every_one(tmp_path, monkeypatch):
    """Every shipped card passes the game's validator 0x010b5de0; one per group goes from the app's
    event mode through the launcher's PKHeX and validator checks to the bytes it would send."""
    import swsh_gift_host
    from nso_run import SCRATCH, Runner
    from pokeldn.app import catalog, gift_builder
    from pokeldn.swsh import events
    runner = Runner(SWORD_IMAGE)
    card, header, rec = SCRATCH + 0x1000, SCRATCH + 0x3000, SCRATCH + 0x4000
    for event in events.load():
        runner.write(card, bytes(0x3A8))
        runner.write(header, bytes(0x68))
        runner.write(rec, event["record"])
        assert runner.call(VALIDATOR, (0, card, header, rec, 0x2D0))[0] == 0, event["key"]

    tool = next(t for g in catalog.GAMES for t in g.tools if t.key == "swsh-gift")
    monkeypatch.setattr(gift_builder, "output", lambda tool: str(tmp_path / "gift.pokegift"))
    for group in events.GROUPS:
        event = next(e for e in events.load() if e["group"] == group)
        value = {"mode": "event", "event": event["key"]}
        assert gift_builder.problem(tool, value) == ""
        gift_builder.prepare(tool, value)
        out = tmp_path / f"{event['key']}.bin"
        assert swsh_gift_host.main([*gift_builder.args(tool, value), "--dump", str(out)]) == 0
        sent = out.read_bytes()
        assert sent[8:wc8.CHECKSUM_AT] == event["record"][8:wc8.CHECKSUM_AT]
        assert wc8.sealed(sent) and sent[:8] != bytes(8)
        if event["record"][:8] != bytes(8):
            assert sent == event["record"]


def _receipt(runner, taken, record):
    """The game's receipt check 0x00ff1a30 on a save whose album bitmap (album+0x60+0x1450) holds the
    card ids in `taken`: 1 refuses the card [docs/swsh_gift.md, What the menu refuses]."""
    from nso_run import SCRATCH
    ret, game, album, vtable, rec = 0x01424c24, SCRATCH + 0x10000, SCRATCH + 0x20000, SCRATCH + 0x12000, SCRATCH + 0x4000
    runner.write(struct.unpack_from("<Q", runner.img, 0x2610798)[0], struct.pack("<Q", game))
    runner.write(vtable, struct.pack("<4Q", ret, ret, ret, ret))
    runner.write(game + 0x210, struct.pack("<Q", album))
    bitmap = bytearray(0x100)
    for number in taken:
        bitmap[number >> 3] |= 1 << (number & 7)
    runner.write(album, bytes(0x1800))
    runner.write(album + 0x48, struct.pack("<Q", vtable))
    runner.write(album + 0x60 + 0x1450, bytes(bitmap))
    runner.write(rec, record)
    return runner.call(0x00ff1a30, (0, rec))[0]


@pytest.mark.skipif(not __import__("os").path.exists(SWORD_IMAGE),
                    reason="needs Sword's extracted main NSO")
def test_a_shiny_galarian_bird_given_another_card_id_reaches_a_save_that_took_another_bird(tmp_path, monkeypatch):
    """The three 2022 shiny Galarian birds all carry card id 1, once per id: a save that took one
    refuses the others. From the app's event mode with card id 2, the launcher sends the official record
    with its date filled and its id and checksum changed; the game's validator and receipt check take it."""
    import swsh_gift_host
    from nso_run import Runner
    from pokeldn import pokemon
    from pokeldn.app import catalog, gift_builder
    from pokeldn.swsh import events
    birds = [e for e in events.load() if "galar-2022" in e["key"]]
    assert {events.card_id(e["record"]) for e in birds} == {1} and len(birds) == 6
    key = next(e["key"] for e in birds if e["key"].startswith("crown-shiny-articuno"))
    assert any("Zapdos" in label for label in events.sharing(key)) and events.sharing(key, 2) == []

    tool = next(t for g in catalog.GAMES for t in g.tools if t.key == "swsh-gift")
    monkeypatch.setattr(gift_builder, "output", lambda tool: str(tmp_path / "gift.pokegift"))
    value = {"mode": "event", "event": key, "event_ids": {key: 2}}
    assert gift_builder.problem(tool, value) == ""
    gift_builder.prepare(tool, value)
    out = tmp_path / "sent.bin"
    assert swsh_gift_host.main([*gift_builder.args(tool, value), "--dump", str(out)]) == 0
    sent, official = out.read_bytes(), events.by_key()[key]["record"]
    assert wc8.sealed(sent) and events.card_id(sent) == 2
    assert [i for i in range(8, wc8.CHECKSUM_AT) if sent[i] != official[i]] == [8]
    assert sent[:8] != bytes(8)
    pokemon.SERVICE.validate_gift(sent)

    runner = Runner(SWORD_IMAGE)
    assert (_receipt(runner, {1}, official), _receipt(runner, {1}, sent), _receipt(runner, {1, 2}, sent)) == (1, 0, 1)
    with pytest.raises(ValueError, match="1 to 2047"):
        events.record(key, 2048)      # past the 2048-bit bitmap the check reads the block beyond it


def test_the_event_list_loads_where_text_defaults_to_cp1252(monkeypatch):
    """Windows opens text as cp1252; the list carries Japanese and Korean names."""
    import pathlib
    from pokeldn.swsh import events
    read = pathlib.Path.read_text
    monkeypatch.setattr(pathlib.Path, "read_text",
                        lambda self, encoding=None, errors=None: read(self, encoding or "cp1252", errors))
    events.load.cache_clear()
    events.by_key.cache_clear()
    try:
        assert len(events.load()) == 189
    finally:
        events.load.cache_clear()
        events.by_key.cache_clear()


@pytest.mark.parametrize("dated", [False, True], ids=["empty-date", "distributor-date"])
def test_imported_event_gets_a_receipt_date_only_when_absent(tmp_path, monkeypatch, dated):
    import swsh_gift_host
    from pokeldn import gifts
    from pokeldn.swsh import events, gift_file

    raw = next(e["record"] for e in events.load() if e["record"][:8] == bytes(8))
    if dated:
        original = bytearray(raw)
        original[:8] = wc8.pack_date(1539879960)
        raw = wc8.seal(original)
    source = tmp_path / "event.pokegift"
    gifts.save(source, gift_file.from_record(raw))
    monkeypatch.setattr(wc8.time, "time", lambda: 1609459200)  # 1 Jan 2021 UTC
    monkeypatch.setattr(swsh_gift_host.pokemon.SERVICE, "validate_gift", lambda data: None)
    output = tmp_path / "out.wc8"
    assert swsh_gift_host.main(["--record", str(source), "--dump", str(output)]) == 0
    sent = output.read_bytes()
    assert wc8.unpack_date(sent) == ((2018, 10, 18, 16, 26, 0) if dated else (2021, 1, 1, 0, 0, 0))
    assert sent[8:wc8.CHECKSUM_AT] == raw[8:wc8.CHECKSUM_AT]
    assert wc8.sealed(sent)
    assert beacon.reassemble([Path(str(output) + f".frag{i}").read_bytes() for i in range(3)]) == sent
    exported = tmp_path / "export.pokegift"
    assert swsh_gift_host.main(["--record", str(source), "--export-gift", str(exported)]) == 0
    assert gift_file.record(gifts.load(exported)) == raw
    assert gift_file.record(gifts.load(source)) == raw
