"""Unreleased titles stay out of a packaged release: the packaged app is frozen and carries no .git
(scripts/pack_app.py copies bin/, pokeldn/, docs/, config/ and gui/assets/ only)."""
from pathlib import Path

from pokeldn.app import preview


def test_a_release_hides_and_a_checkout_shows(tmp_path):
    checkout = tmp_path / "repo"
    (checkout / ".git").mkdir(parents=True)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    assert preview.enabled({}, frozen=False, root=checkout)
    assert not preview.enabled({}, frozen=True, root=checkout)
    assert not preview.enabled({}, frozen=False, root=bundle)    # the Android and iOS bundles
    assert preview.enabled({"POKELDN_PREVIEW": "1"}, frozen=True, root=bundle)
    assert not preview.enabled({"POKELDN_PREVIEW": "0"}, frozen=False, root=checkout)


def test_the_packer_never_copies_the_git_folder():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "pack_app.py").read_text()
    assert ".git" not in source.replace(".github", "")
