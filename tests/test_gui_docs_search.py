"""Chinese search results and scrolling must refer to the same translated document sections."""
import asyncio
import os
import re
from types import SimpleNamespace

import pytest

ft = pytest.importorskip("flet")


def test_translated_docs_keep_all_original_heading_ids_and_fragment_links():
    from gui.views import docs
    from gui.views.widgets import HEADING, MarkdownDocument, fenced_blocks, heading_sections
    keys, bodies = {}, {}
    for name in os.listdir(docs.DOCS):
        if not name.endswith(".md"):
            continue
        body, reference = docs.document_text(name)
        assert reference is not None, name
        levels = lambda text: [len(re.match(r" *#+", m[0])[0].strip())
                               for block, code in fenced_blocks(text) if code is None
                               for m in HEADING.finditer(block)]
        assert levels(body) == levels(reference), name
        original = [key for key, title, _ in heading_sections(reference) if title]
        translated = list(heading_sections(body, reference=reference))
        assert [key for key, title, _ in translated if title] == original, name
        assert "".join(source for _, _, source in translated) == body
        document = MarkdownDocument(None, None)
        document.set_value(body, reference=reference)
        keys[name] = {c.key.value for c in document.control.controls if isinstance(c.key, ft.ScrollKey)}
        assert set(original) <= keys[name], name
        bodies[name] = body
    missing = [(name, f"{target}#{fragment}") for name, body in bodies.items()
               for target, fragment in re.findall(r"\]\((?!https?://)([^)#\s]*)#([^)\s]+)\)", body)
               if (os.path.basename(target) or name) in keys
               and fragment not in keys[os.path.basename(target) or name]]
    assert missing == []


def test_search_indexes_chinese_pages_and_the_app_guide():
    from gui.views import docs
    sections = docs.index(docs.pages(), "入门指南")
    watchdog = docs.search(sections, "主机看门狗")[0]
    assert (watchdog.file, watchdog.anchor, watchdog.heading) == (
        "hardware_esp32.md", "the-host-watchdog", "主机看门狗")
    assert watchdog.page == "ESP32 无线通信"
    assert any(s.file == "guide" and s.page == "入门指南" for s in sections)
    assert any(s.file == "gui.md" and s.anchor == "the-docs-page" for s in docs.search(sections, "文档页面"))
    assert all("主机看门狗" in (s.heading + s.page + s.text) and "ALIVE" in (s.heading + s.page + s.text)
               for s in docs.search(sections, "主机看门狗 ALIVE"))


def test_search_result_labels_are_chinese_but_navigation_keeps_original_ids():
    from gui.views.docs import DocsView, Section
    view = object.__new__(DocsView)
    view.query, view.file = "看门狗", "guide"
    view.sections = [Section("hardware_esp32.md", "ESP32 无线通信", "主机看门狗", "the-host-watchdog",
                             "主机看门狗会检测连接是否仍然有效。")]
    opened = []
    view._open = lambda file, anchor: opened.append((file, anchor))
    rows = view.result_rows()
    assert rows[0].content.controls[0].value == "主机看门狗"
    assert rows[0].content.controls[1].value == "ESP32 无线通信"
    assert any(s.text == "看门狗" and s.style.weight == ft.FontWeight.W_600
               for s in rows[0].content.controls[2].spans)
    rows[0].on_click(None)
    assert opened == [("hardware_esp32.md", "the-host-watchdog")]
    view.query = "完全不存在的关键词"
    assert view.result_rows()[0].content.value == "没有匹配的文档。"


@pytest.mark.parametrize("query,expected", [("宏", True), ("朱", True), ("USB", True),
                                          ("a", False), (" ", False)])
def test_search_accepts_single_chinese_characters(query, expected):
    from gui.views.docs import searchable
    assert searchable(query) is expected


def test_chinese_excerpt_keeps_matched_words_when_ascii_spaces_are_nearby():
    from gui.views.docs import snippet
    source = "甲" * 55 + "USB 关键词" + "乙" * 100
    runs = snippet(source, ["关键词"], width=50)
    assert ("关键词", True) in runs
    assert "".join(part for part, _ in runs).startswith("...")


def test_translated_heading_keys_skip_code_examples_and_handle_repeated_headings():
    from gui.views.widgets import heading_sections
    original = "# Setup\n\n## Settings\n```text\n## Not a heading\n```\n## Settings\n"
    chinese = "# 设置\n\n## 设置\n```text\n## Not a heading\n```\n## 设置\n"
    sections = list(heading_sections(chinese, reference=original))
    assert [key for key, title, _ in sections if title] == ["setup", "settings", "settings-1"]
    assert "".join(source for _, _, source in sections) == chinese
    assert [key for key, title, _ in heading_sections(chinese) if title] == ["设置", "设置-1", "设置-2"]


def test_document_links_keep_fragments_and_scroll_decodes_chinese_anchors(monkeypatch):
    from gui.views import docs
    view = object.__new__(docs.DocsView)
    opened, scrolled = [], []
    view._open = lambda file, anchor: opened.append((file, anchor))

    async def scroll_to(**kwargs):
        scrolled.append(kwargs)

    async def no_wait(seconds):
        pass

    monkeypatch.setattr(docs.asyncio, "sleep", no_wait)
    view.scroll = SimpleNamespace(scroll_to=scroll_to)
    asyncio.run(view._link(SimpleNamespace(data="hardware_esp32.md#the-host-watchdog")))
    assert opened == [("hardware_esp32.md", "the-host-watchdog")]
    asyncio.run(view._link(SimpleNamespace(data="#%E8%AE%BE%E7%BD%AE")))
    assert [call["scroll_key"] for call in scrolled] == ["设置", "设置"]
