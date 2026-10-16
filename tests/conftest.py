"""Each test starts with this fork's default language, independent of pack-selection tests."""
import pytest


@pytest.fixture(autouse=True)
def app_language():
    from pokeldn.app import i18n
    previous = i18n._selected
    i18n.select(i18n.BUILTIN_CHINESE)
    yield
    i18n.select(previous)
