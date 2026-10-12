"""Which radio carries the LDN calls: POKELDN_RADIO=SCHEME:ARG. `esp32` is the board; a plugin
adds others (pokeldn.plugins). Unset, the calls go to a Linux card through nl80211."""
import os

BUILTIN = ("esp32",)


def selected() -> str | None:
    """The scheme POKELDN_RADIO names, or None for the kernel's nl80211."""
    spec = os.environ.get("POKELDN_RADIO", "")
    return spec.split(":", 1)[0] if ":" in spec else None


def use_from_environment(log=print) -> None:
    """Installs the radio POKELDN_RADIO names before the first LDN call (ldn.wlan.create_factory)."""
    scheme = selected()
    if scheme is None:
        return
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
