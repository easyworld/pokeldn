"""Check rendered controls, since a translated catalog alone cannot prevent English UI leaks."""
import asyncio
from types import SimpleNamespace

import pytest

ft = pytest.importorskip("flet")


def controls(control):
    yield control
    for child in [*(getattr(control, "controls", None) or []), getattr(control, "content", None)]:
        if isinstance(child, ft.Control):
            yield from controls(child)


def texts(control):
    return [c.value for c in controls(control) if isinstance(c, ft.Text)]


def test_empty_more_options_label_and_set_count_are_chinese():
    from gui.views.pokemon import OfferOptions
    options = OfferOptions(SimpleNamespace(value={}))
    options._label()
    assert options.label.value == "随机"
    options.chosen["nature"] = 3
    options._label()
    assert options.label.value == "1 项已设置"
    options.chosen.clear()
    options._label()
    assert options.label.value == "随机"


def test_doc_navigation_translates_every_title_without_changing_the_tree():
    from gui.localization import translate
    from gui.views.docs import DocsView, pages
    view = object.__new__(DocsView)
    view.tree = pages()

    def flatten(items):
        for page in items:
            yield page
            yield from flatten(page.children)

    original = [(p.file, p.title, p.parent) for p in flatten(view.tree)]
    view.file = "guide"
    view.query = ""
    view.open_parents = {file for file, _, _ in original}
    view.nav = ft.Column()
    view.render_nav()
    rendered = texts(view.nav)
    assert len(original) >= 40
    for _, title, _ in original:
        assert translate(title) != title
        assert translate(title) in rendered and title not in rendered
    assert [(p.file, p.title, p.parent) for p in flatten(view.tree)] == original


@pytest.mark.parametrize("state,release,expected", [
    ("current", None, "当前已是最新版本（{version}）。"),
    ("available", "0.31.0-rc.1", "pokeldn 0.31.0-rc.1 已发布。"),
    ("available", None, ""),
    ("checking", None, "正在检查…"),
    ("offline", None, "GitHub 未响应，请检查网络连接。"),
])
def test_update_status_uses_chinese_and_preserves_version(state, release, expected):
    from gui.views.settings import SettingsView
    from pokeldn import __version__
    view = SimpleNamespace(app=SimpleNamespace(update_state=state,
                           update=SimpleNamespace(version=release) if release else None), update_state=ft.Text())
    SettingsView._update_text(view)
    assert view.update_state.value == expected.format(version=__version__)


def test_macro_summary_play_import_and_step_errors_are_chinese(tmp_path, monkeypatch):
    from gui.views import controller
    from gui.views.controller import ControllerView
    from pokeldn.pad.macro import Macro
    view = object.__new__(ControllerView)
    view.macro = Macro(name="Eevee")
    assert view._summary().value == "宏中没有步骤"
    messages = []
    view._say = lambda message, color: messages.append(message)
    view.play()
    assert messages == ["宏中没有步骤"]

    invalid = tmp_path / "Eevee.pokemacro"
    invalid.write_text("{}", encoding="utf-8")

    async def pick_files(**kwargs):
        return [SimpleNamespace(path=str(invalid))]

    dialogs = []
    view.app = SimpleNamespace(picker=SimpleNamespace(pick_files=pick_files),
                               page=SimpleNamespace(show_dialog=dialogs.append))
    asyncio.run(view._import(None))
    assert messages[-1] == "Eevee.pokemacro: 不是有效的宏文件"
    monkeypatch.setattr(ft.Text, "update", lambda self: None)
    steps = [{"wait": -1}]
    view._edit(steps, 0)
    dialogs[-1].actions[-1].on_click(None)
    assert any("毫秒" in value and "must be" not in value for value in texts(dialogs[-1].content))
    assert steps == [{"wait": -1}]

    target = str(tmp_path / "Eevee.pokemacro")
    failure = FileNotFoundError(2, "No such file", target)

    async def save_file(**kwargs):
        return target

    def failed_open(*args, **kwargs):
        raise failure

    view.app.picker.save_file = save_file
    monkeypatch.setattr(controller, "open", failed_open, raising=False)
    asyncio.run(view._export(None))
    assert messages[-1] == str(failure) and "Eevee.pokemacro" in messages[-1]


def test_renaming_a_macro_refreshes_its_list_with_chinese_labels():
    from gui.views.controller import ControllerView
    saved, refreshed, names = [], [], []
    view = SimpleNamespace(save=lambda: saved.append(True), refresh_list=lambda: refreshed.append(True),
                           list=SimpleNamespace(update=lambda: None))
    field = ControllerView._text_field(view, "名称", "Pikachu", names.append, rename=True)
    box = next(c for c in controls(field) if isinstance(c, ft.TextField))
    box.value = "Eevee"
    box.on_blur(SimpleNamespace(control=box))
    assert saved == refreshed == [True]
    assert names == ["Eevee"] and box.value == "Eevee"


@pytest.mark.parametrize("command", ["brew install arm-none-eabi-binutils", None])
def test_assembler_installation_hint_translates_prose_but_keeps_command(monkeypatch, command):
    from gui.views import gifts
    monkeypatch.setattr(gifts.custom_code, "toolchain", lambda: None)
    monkeypatch.setattr(gifts.custom_code, "install_hint", lambda: (command, "https://developer.arm.com/"))
    builder = SimpleNamespace(app=SimpleNamespace(page=SimpleNamespace(run_task=lambda *a: None)))
    rendered = texts(gifts.GiftBuilder._toolchain_status(builder))
    assert any("免费的 GNU Arm 汇编器" in text and "预编译的 .bin 文件" in text for text in rendered)
    assert not any("Typing assembly" in text for text in rendered)
    if command:
        assert command in rendered


def test_raid_event_errors_use_the_existing_chinese_translation():
    from gui.views.raid_event import RaidEventPicker
    view = SimpleNamespace(busy=ft.Container(), bar=ft.ProgressBar(), status=ft.Text(), actions=ft.Row(),
                           control=SimpleNamespace(update=lambda: None))
    RaidEventPicker._failed(view, "the event gallery is not downloaded", lambda: None)
    assert view.status.value == "尚未下载活动库"
    assert not view.busy.visible and not view.bar.visible


@pytest.mark.parametrize("source,expected", [
    ("unknown button 'Eevee'", "未知按键：'Eevee'"),
    ("loop[0]: unknown field 'Pikachu'", "loop[0]：未知字段 'Pikachu'"),
    ("not a macro file: invalid 'Eevee'", "不是有效的宏文件：invalid 'Eevee'"),
    ("unrecognized failure in Eevee.pokemacro", "unrecognized failure in Eevee.pokemacro"),
    ("Pikachu is not in that game.", "该游戏中不存在 皮卡丘。"),
])
def test_error_translation_preserves_literal_diagnostics(source, expected):
    from gui.localization import error_message
    assert error_message(ValueError(source)) == expected
