"""The engine's versions of Scarlet 4.0.0's battle server functions, each registered under the game
address it reproduces (`pokeldn.sv.battle.machine.lifted`)."""

import importlib
import os

from pokeldn.sv.battle.engine import accessors, actions, battler, battler_methods, containers, data, flow, getters, handlers, heap, libc, messages, pokemon, queue, random, slots, triggers  # noqa: F401

# Batches being lifted in parallel; POKELDN_LIFT_BATCHES="0" loads only lift0 (dev isolation).
for _k in os.environ.get("POKELDN_LIFT_BATCHES", "0123"):
    importlib.import_module(f"pokeldn.sv.battle.engine.lift{_k}")
