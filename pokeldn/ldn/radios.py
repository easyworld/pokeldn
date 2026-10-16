"""Radio selection: esp32, the Windows ldnrs daemon, or a plugin (docs/hardware_adapters.md).
Unset, the calls go to a Linux card through nl80211.
"""
import os
import sys
from dataclasses import dataclass

BUILTIN = ("esp32", "ldnrs")


@dataclass(frozen=True)
class Choice:
    scheme: str
    label: str


def choices():
    from pokeldn import plugins
    return ([Choice("ldnrs", "USB Wi-Fi (Windows, ldnrs)")] if sys.platform == "win32" else []) + plugins.radios()


def radio(scheme):
    return next((r for r in choices() if r.scheme == scheme), None)


def join_timeout(seconds):
    # RTL8822BU driver setup can take 30 s before LDN authentication (docs/hardware_adapters.md).
    return max(seconds, 90) if selected() == "ldnrs" else seconds


def selected() -> str | None:
    """The scheme POKELDN_RADIO names, or None for the kernel's nl80211."""
    spec = os.environ.get("POKELDN_RADIO", "")
    return spec.split(":", 1)[0] if ":" in spec else None


def use_from_environment(log=print) -> None:
    """Installs the radio POKELDN_RADIO names before the first LDN call (ldn.wlan.create_factory)."""
    scheme = selected()
    if scheme is None:
        return
    if scheme == "ldnrs":
        raise RuntimeError("ldnrs uses pokeldn.ldn.api, not the nl80211 factory")
    if scheme == "esp32":
        from pokeldn.ldn.esp32_wlan import use_from_environment as esp32
        esp32(log=log)
        return
    from pokeldn import plugins
    radio = plugins.radio(scheme)
    if radio is None:
        raise RuntimeError(f"POKELDN_RADIO={scheme}:... names no radio; a plugin adds it, and it must be "
                           f"enabled in Settings or named in POKELDN_PLUGINS")
    radio.install(os.environ["POKELDN_RADIO"].split(":", 1)[1], log)
