"""Translation must preserve table structure and literal technical data."""
import re
from collections import Counter
from pathlib import Path

import pytest


DOCS = Path(__file__).resolve().parents[1] / "docs"
LOCALIZED = sorted((DOCS / "zh-Hans").glob("*.md"))
SEPARATOR = re.compile(r"\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?")


def cells(line):
    parts = re.split(r"(?<!\\)\|", line.strip())
    if not parts[0].strip():
        parts = parts[1:]
    if not parts[-1].strip():
        parts = parts[:-1]
    return [part.strip() for part in parts]


def tables(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    found = []
    for index, line in enumerate(lines):
        if not SEPARATOR.fullmatch(line.strip()):
            continue
        header = cells(lines[index - 1])
        assert len(header) == len(cells(line)), f"{path.name}:{index}: malformed header"
        rows = [header]
        cursor = index + 1
        while cursor < len(lines) and lines[cursor].startswith("|"):
            rows.append(cells(lines[cursor]))
            cursor += 1
        found.append(rows)
    return found


def literal(cell):
    if cell in ("TRUE", "FALSE", "u8", "u16", "u32", "u64", "s8", "s16", "s32", "s64"):
        return True
    remainder = re.sub(r"`[^`]+`", "", cell)
    if re.search(r"[^\d\sxa-fA-F.,:;/%+*<>=\-~()\[\]\\|]", remainder):
        return False
    return bool(re.search(r"\d", remainder)) or not remainder.strip(" ,:;/+*<>=-~()[]\\|")


def numbers(cell):
    # CJK punctuation is harmless; duplicated values or ordinal prefixes are not.
    plain = re.sub(r"`[^`]+`", "", cell)
    return re.findall(r"0x[\da-fA-F]+|[+-]?\d+(?:[.,]\d+)*", plain)


@pytest.mark.parametrize("localized", LOCALIZED, ids=lambda path: path.name)
def test_translated_tables_keep_rows_columns_and_literal_values(localized):
    original = tables(DOCS / localized.name)
    translated = tables(localized)
    assert len(translated) == len(original), localized.name
    for table_index, (source, target) in enumerate(zip(original, translated)):
        assert len(target) == len(source), (localized.name, table_index)
        for row_index, (before, after) in enumerate(zip(source, target)):
            assert len(after) == len(before), (localized.name, table_index, row_index)
            if row_index == 0:
                continue
            for column, (a, b) in enumerate(zip(before, after)):
                if literal(a):
                    where = (localized.name, table_index, row_index, column, a, b)
                    assert numbers(a) == numbers(b), where
                    assert re.findall(r"`([^`]+)`", a) == re.findall(r"`([^`]+)`", b), where
                    if a in ("TRUE", "FALSE", "u8", "u16", "u32", "u64", "s8", "s16", "s32", "s64"):
                        assert a == b, where
                    if not a:
                        assert not b, where


@pytest.mark.parametrize("localized", LOCALIZED, ids=lambda path: path.name)
def test_indented_examples_are_not_merged_into_translated_prose(localized):
    def example_lines(path):
        return Counter(line for line in path.read_text(encoding="utf-8").splitlines()
                       if line.startswith("    ") and line.strip())

    assert example_lines(localized) == example_lines(DOCS / localized.name), localized.name


@pytest.mark.parametrize("localized", LOCALIZED, ids=lambda path: path.name)
def test_localized_prose_has_no_deferred_translation_notices_or_known_mistranslations(localized):
    text = localized.read_text(encoding="utf-8")
    prose = re.sub(r"(`+).*?\1", "", text, flags=re.S)
    for phrase in ("本节已随上游更新", "暂保留英文", "墨盒", "盒式磁带", "董事会",
                   "西班牙火红", "电动汽车", "粉蝶巴基斯坦", "究极球球男"):
        assert phrase not in prose, (localized.name, phrase)
