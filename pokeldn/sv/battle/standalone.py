"""A raid battle's server state built from nothing but the game's own image and tables (`game.Game`) and
the battle bootstrap: the heap (`arena`), the "Application" allocator, the weak-handle table, the five
data tables, the session as the game makes it and N's start states (docs/sv_raid.md, Reproducing a
round). The result is what `engine.server.Server` serves from.

    g = game.load(cache)
    m, n = standalone.battle(g, bootstrap, slot=0)
"""

import struct

import pokeldn.sv.battle.engine  # noqa: F401  (registers every lifted function)
from pokeldn import gen9
from pokeldn.sv import raid_partners
from pokeldn.sv.battle.engine import arena, session

PARTY_RECORD = 0x158


class Standalone(arena.Arena):
    """The arena with the console's clock and CSPRNG answered as the replays answer them."""
    ticks = 0x18A0000000

    def random_bytes(self, n):
        return bytes(n)

    def tick(self):
        self.ticks += 0x100
        return self.ticks


def generated_partners(bootstrap, count=raid_partners.HOSTED):
    """-> the NPC partners' records from the bootstrap alone: the RaidPoint's randSeed and unlock stage
    draw the trainers (raid_partners.draw) and seed their records (raid_partners.record), at four
    fifths of the level of the Pokemon in slot 0."""
    point = 5 * PARTY_RECORD
    seed, stage = struct.unpack_from("<QI", bootstrap, point + 0x3D8)
    level = int(0.8 * gen9.read(gen9.decrypt(bytes(bootstrap[:PARTY_RECORD])))["level"])
    return [raid_partners.record(seed, stage, i, level) for i in raid_partners.draw(seed, stage, count)]


def build(game, bootstrap, partners=None, slot=None, machine=Standalone):
    """-> (machine, allocator, N): the session built up to N, before its start states. `partners`
    defaults to generated_partners; `slot` is the console slot (session.raid_setup)."""
    m = machine(game.static_page)
    arena.build(m)
    app = session.application_allocator(m)
    session.build_handles(m, app)
    session.build_tables(m, app, game.tables)
    if partners is None:
        partners = generated_partners(bootstrap)
    n = session.build_session(m, app, bootstrap, partners, slot)
    return m, app, n


def battle(game, bootstrap, partners=None, slot=None, machine=Standalone):
    """-> (machine, N) after N's start states: the server's battle state, ready to serve."""
    m, _app, n = build(game, bootstrap, partners, slot, machine)
    session.start_states(m, n)
    return m, n
