"""Shared by the Test Kit's scripts; importing it checks that a plugin's own modules load."""
import contextlib

PREFIX = "[test-kit]"


def say(text: str) -> None:
    print(f"{PREFIX} {text}", flush=True)


class KitFactory:
    """Stands where a real radio's factory would; any use says the radio carries nothing."""

    def __getattr__(self, name):
        raise RuntimeError("The Test Kit radio carries nothing. Pick the board again on the Plugins page.")


def install_radio(arg: str, log) -> None:
    from ldn import wlan

    @contextlib.asynccontextmanager
    async def factory():
        yield KitFactory()

    log(f"{PREFIX} Test Kit radio installed (argument {arg!r}); it carries nothing.")
    wlan.set_factory(factory)
