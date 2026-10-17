"""Ruby, Sapphire and Emerald, prepared ahead of a Switch release from pret/pokeemerald and
pret/pokeruby (docs/rse.md). The link, trade and Mystery Gift wire is FireRed's, so the launchers
are bin/frlg_*; this package holds what differs: Emerald's numbers and its own gifts.

    .constants  Emerald's flags, vars, specials, items and save layout; the game codes
    .scripts    an assembler for the field-script macros Emerald's gift scripts use
    .gifts      Emerald's official Mystery Gift scripts and composed gifts, and their payload
    .gift_file  the .pokegift adapter for game "rse"
    .gift_builder  the app's presets
"""
