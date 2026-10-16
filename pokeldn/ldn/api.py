"""LDN calls selected by the radio; constants and parameter types come from the bundled library."""
import ldn

from pokeldn.ldn import radios


def __getattr__(name):
    if name in ("scan", "connect", "create_network") and radios.selected() == "ldnrs":
        from pokeldn.ldn import ldnrs
        return getattr(ldnrs, name)
    return getattr(ldn, name)
