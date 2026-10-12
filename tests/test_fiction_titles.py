"""Проверки утверждений README о таблицах csv/vol_N.csv (см. tests_readme.md).

Дополняют test_data.py: нумерация записей, ссылки на строки txt-файлов, запись-заполнитель,
«Сводка» README, фамилии авторов по указателю имен (т. 7), воспроизводимость таблиц парсером.
"""
import csv
import re
import subprocess
import sys

import pytest

import dvcheck

ROOT = dvcheck.ROOT
VOLUMES = range(1, 7)
# README, «Формат данных», num: «Некоторые номера повторяются и могут быть снабжены буквенными
# индексами (1б), другие пропущены, в этих случаях вместо одного номера записи указан диапазон (101—102)»
NUM = re.compile(r"(\d+)([а-д]?)|(\d+)—(\d+)")
# README: «Если номер пропущен в самом источнике, в таблице есть строка с этим номером, где
# title = NOPARSE и tail = MISSING (единственный случай — т. 6, № 19080)»
PLACEHOLDERS = {(6, "19080")}
# Слитно в т. 7, но раздельно в самом источнике (сверено со сканами): (том, num, часть имени)
SPLIT_AS_IN_SOURCE = set()


def table(volume):
    return f"csv_vol_{volume}"


def txt_lines(volume):
    return (ROOT / f"txt/vol_{volume}.txt").read_text(encoding="utf-8").split("\n")


def is_placeholder(row):
    return row["tail"] == "MISSING"


def fail(problems, what):
    if problems:
        pytest.fail(dvcheck.report(problems, what), pytrace=False)


@pytest.mark.parametrize("volume", VOLUMES)
def test_numbering(volume):
    """Номера записей идут подряд с 1: буквенный индекс повторяет предыдущий номер или следующий за ним,
    диапазон a—b (a < b) продолжает нумерацию, после него идет b + 1."""
    problems = []
    last = 0
    for row in dvcheck.rows(table(volume)):
        num, single, suffix, first, end = row["num"], *NUM.fullmatch(row["num"]).groups()
        if single:
            base = int(single)
            expected = (last, last + 1) if suffix else (last + 1,)
            if base not in expected:
                problems.append(f"строка {row.row_number}: № {num} после № {last}")
            last = base
        else:
            first, end = int(first), int(end)
            if first != last + 1 or first >= end:
                problems.append(f"строка {row.row_number}: № {num} после № {last}")
            last = end
    fail(problems, f"нарушения нумерации — т. {volume}")


@pytest.mark.parametrize("volume", VOLUMES)
def test_line_numbers(volume):
    """start и end указывают на строки txt-файла: запись начинается со своего номера, записи идут
    подряд без пропусков и перекрытий, end не выходит за конец файла."""
    lines = txt_lines(volume)
    problems = []
    previous = None
    for row in dvcheck.rows(table(volume)):
        if is_placeholder(row):
            continue
        where = f"строка {row.row_number}, № {row['num']}"
        if row["end"] > len(lines):
            problems.append(f"{where}: end = {row['end']}, в txt {len(lines)} строк")
        # в txt индекс бывает латинским (22816a), а диапазон — через дефис; парсер их нормализует
        label = re.escape(row["num"]).replace("а", "[аa]").replace("б", "[бb]").replace("—", "[—-]")
        if not re.match(rf"\s*{label}\.", lines[row["start"] - 1]):
            problems.append(f"{where}: строка {row['start']} txt — {lines[row['start'] - 1][:60]!r}")
        if previous and row["start"] != previous["end"] + 1:
            problems.append(f"{where}: start = {row['start']}, предыдущая запись кончается на {previous['end']}")
        previous = row
    fail(problems, f"start/end не соответствуют txt/vol_{volume}.txt")


def test_placeholders():
    """NOPARSE в title стоит тогда и только тогда, когда tail = MISSING, и такая запись одна —
    т. 6, № 19080; ее start совпадает со start следующей записи."""
    found = set()
    problems = []
    for volume in VOLUMES:
        rows = list(dvcheck.rows(table(volume)))
        for i, row in enumerate(rows):
            if (row["title"] == "NOPARSE") != is_placeholder(row):
                problems.append(f"т. {volume}, № {row['num']}: title = {row['title']!r}, tail = {row['tail']!r}")
            if is_placeholder(row):
                found.add((volume, row["num"]))
                if i + 1 < len(rows) and rows[i + 1]["start"] != row["start"]:
                    problems.append(f"т. {volume}, № {row['num']}: start = {row['start']}, "
                                    f"у следующей записи {rows[i + 1]['start']}")
    problems += [f"т. {v}, № {n}: заполнитель не описан в README" for v, n in sorted(found - PLACEHOLDERS)]
    problems += [f"т. {v}, № {n}: заполнителя нет в таблице" for v, n in sorted(PLACEHOLDERS - found)]
    fail(problems, "записи-заполнители")


def readme_summary():
    """Строки таблицы «Сводка» README: {файл: [Записей, alt_title, in, note, Непустой tail, MISSING]}."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    section = text.split("## Сводка", 1)[1].split("\n## ", 1)[0]
    out = {}
    for line in section.splitlines():
        cells = [c.strip(" *") for c in line.strip().strip("|").split("|")]
        if len(cells) == 8 and (cells[0].startswith("vol_") or cells[0] == "Всего"):
            out[cells[0]] = [int(c.split()[0]) for c in cells[2:]]
    return out


def counts(volume):
    """Те же числа, что считает scripts/stats.py: заполнитель не входит в «Записей»."""
    rows = list(dvcheck.rows(table(volume)))
    records = [r for r in rows if not is_placeholder(r)]
    return [len(records)] + [sum(bool(r[f]) for r in records) for f in ("alt_title", "in", "note", "tail")] \
        + [len(rows) - len(records)]


def test_summary():
    """Числа в таблице «Сводка» README совпадают с данными (по томам и в строке «Всего»)."""
    summary = readme_summary()
    columns = ["Записей", "alt_title", "in", "note", "Непустой tail", "MISSING"]
    actual = {f"vol_{v}.csv": counts(v) for v in VOLUMES}
    actual["Всего"] = [sum(c) for c in zip(*actual.values())]
    problems = []
    for name, values in actual.items():
        if name not in summary:
            problems.append(f"{name}: нет строки в «Сводке»")
            continue
        problems += [f"{name}, {col}: в README {r}, в данных {a}"
                     for col, r, a in zip(columns, summary[name], values) if r != a]
    fail(problems, "«Сводка» README расходится с данными")


def vol7_headwords():
    """Заглавные слова указателя имен (т. 7): текст в начале строки до первой запятой."""
    out = set()
    for line in txt_lines(7):
        m = re.match(r"([А-ЯЁA-Z][^,\d]*?),", line)
        if m:
            out.add(normalize(m.group(1)))
    return out


def normalize(name):
    return name.lower().replace("ё", "е")


def test_author_surname_not_split():
    """Фамилия автора не разорвана пробелом, если указатель имен (т. 7) пишет ее слитно
    («И КРАМОВ» при «Икрамов» в т. 7)."""
    headwords = vol7_headwords()
    problems = []
    for volume in VOLUMES:
        for row in dvcheck.rows(table(volume)):
            for part in re.split(r"[,()]", row["author"] or ""):
                part = part.strip()
                if " " not in part or not re.fullmatch(r"[А-ЯЁ' -]+", part):
                    continue
                joined = normalize(part.replace(" ", ""))
                if (joined in headwords and normalize(part) not in headwords
                        and (volume, row["num"], part) not in SPLIT_AS_IN_SOURCE):
                    problems.append(f"т. {volume}, строка {row.row_number}, № {row['num']}: "
                                    f"{part!r} (в т. 7 {joined.capitalize()})")
    fail(problems, "фамилии, разорванные пробелом")


@pytest.mark.parametrize("volume", VOLUMES)
def test_parser_reproduces_table(volume, tmp_path):
    """Парсер scripts/split_records.py порождает из txt/vol_N.txt в точности опубликованную таблицу
    (README: «таблицы данных целиком порождаются парсером»). Нужен модуль regex."""
    pytest.importorskip("regex")
    out = tmp_path / f"vol_{volume}.csv"
    subprocess.run([sys.executable, str(ROOT / "scripts/split_records.py"),
                    str(ROOT / f"txt/vol_{volume}.txt"), str(out)], check=True)
    with open(ROOT / f"csv/vol_{volume}.csv", encoding="utf-8") as f:
        published = list(csv.reader(f))
    with open(out, encoding="utf-8") as f:
        generated = list(csv.reader(f))
    problems = [f"строка {i}: опубликовано {p}, парсер дает {g}"
                for i, (p, g) in enumerate(zip(published, generated), 1) if p != g]
    if len(published) != len(generated):
        problems.append(f"строк: опубликовано {len(published)}, парсер дает {len(generated)}")
    fail(problems, f"csv/vol_{volume}.csv не совпадает с результатом парсера")
