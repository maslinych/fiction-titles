"""Проверки таблиц csv/vol_N.csv, специфичные для этого датасета (см. tests_readme.md)."""
import re

import pytest

import dvcheck

TEXT_FIELDS = ("title", "author", "alt_title", "in", "note", "tail")
# латинские буквы, неотличимые на вид от кириллических
LATIN_LOOKALIKES = set("ABCEHKMOPTX")


def problems(name, check):
    """Строки таблицы, для которых check(row) возвращает описание проблемы."""
    out = []
    for row in dvcheck.rows(name):
        problem = check(row)
        if problem:
            out.append(f"строка {row.row_number}, № {row['num']}: {problem}")
    return out


def text(row, field):
    return row[field] or ""


def no_markup(row):
    """Разметка txt-файлов (<letter>, # и @ ручного разбора) не попадает в данные."""
    for field in TEXT_FIELDS:
        if re.search(r"<letter>|[#@]", text(row, field)):
            return f"{field} = {text(row, field)!r}"


def no_ocr_junk(row):
    """Знаки ^ и <, оставшиеся от распознавания."""
    for field in TEXT_FIELDS:
        if re.search(r"[\^<]", text(row, field)):
            return f"{field} = {text(row, field)!r}"


def tail_has_text(row):
    """Непустой tail содержит хотя бы одну букву или цифру."""
    tail = text(row, "tail")
    if tail and not re.search(r"\w", tail):
        return f"tail = {tail!r}"


def author_final_period(row):
    """Завершающая точка записи снята: author не кончается на «).», «].», «..», « .»."""
    author = text(row, "author")
    if re.search(r"[)\]]\s*\.$|(?<!\.)\.\s*\.$|\s\.$", author) or author == "Имя авт. не установлено.":
        return f"author = {author!r}"


def author_no_latin_lookalikes(row):
    """В кириллическом имени нет латинских букв, похожих на русские (X вместо Х)."""
    author = text(row, "author")
    latin = set(re.findall(r"[A-Za-z]", author))
    if latin and latin <= LATIN_LOOKALIKES:
        return f"author = {author!r}"


def line_range(row):
    """end ≥ start; у записи-заполнителя (MISSING) end = start − 1."""
    if text(row, "tail") == "MISSING":
        if row["end"] != row["start"] - 1:
            return f"заполнитель: start = {row['start']}, end = {row['end']}"
    elif row["end"] < row["start"]:
        return f"start = {row['start']}, end = {row['end']}"


CHECKS = [no_markup, no_ocr_junk, tail_has_text, author_final_period, author_no_latin_lookalikes, line_range]


@pytest.mark.parametrize("check", CHECKS, ids=[c.__name__ for c in CHECKS])
@pytest.mark.parametrize("name", dvcheck.table_names())
def test_values(name, check):
    found = problems(name, check)
    if found:
        pytest.fail(dvcheck.report(found, f"{check.__doc__.strip()} — {name}"), pytrace=False)
