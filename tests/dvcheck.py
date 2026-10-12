"""Базовые проверки данных по описанию datapackage.json (Frictionless Data Package v2).

Модуль входит в набор тестов датасета Репозитория открытых данных по русской литературе
и фольклору (https://dataverse.pushdom.ru). Для запуска нужны только `frictionless`
и `pytest` (см. requirements.txt); запуск из папки датасета (где лежит datapackage.json): `python -m pytest tests`.

- `missing_files()`: файлы из datapackage.json, которых нет в папке датасета;
- `errors(name)`: ошибки ресурса, найденные frictionless (типы, обязательные и уникальные
  значения, ограничения, первичные и внешние ключи, лишние и недостающие ячейки);
- `category_errors(name)`: значения вне списка `categories` поля (frictionless эту часть
  стандарта v2 пока не проверяет); для полей типа `list` проверяется каждый элемент;
- `whitespace_errors(name)`: ячейки с пробелами (в т.ч. неразрывными) в начале или в конце
  значения: frictionless их пропускает, а «Роман » и «Роман» в данных — разные значения;
- `list_reference_errors(...)`: элементы поля-списка, которых нет в другой таблице (внешний
  ключ на поле типа `list` frictionless не поддерживает: его нельзя указывать в foreignKeys);
- `table_names()`: таблицы пакета (ресурсы со схемой); остальные ресурсы — README, тесты,
  сканы, код — входят в публикацию, но проверяются только на наличие файла;
- `rows(name)`, `column(name, field)`: данные ресурса для собственных тестов датасета;
- `files_match(...)`: соответствие файлов корпуса (в папке или zip) значениям поля таблицы.
"""
import functools
import re
import zipfile
from pathlib import Path

from frictionless import Package, validate

__version__ = "1.2"

ROOT = Path(__file__).resolve().parent.parent
DESCRIPTOR = ROOT / "datapackage.json"
MAX_REPORT = 30


@functools.lru_cache(maxsize=None)
def package():
    return Package(str(DESCRIPTOR), basepath=str(ROOT))


def resource_names():
    """Все ресурсы пакета, т.е. все публикуемые файлы."""
    return [r.name for r in package().resources] if DESCRIPTOR.exists() else []


def table_names():
    """Ресурсы-таблицы: со схемой или с type: table."""
    if not DESCRIPTOR.exists():
        return []
    return [r.name for r in package().resources
            if r.to_descriptor().get("type") == "table" or "schema" in r.to_descriptor()]


def missing_files():
    """Файлы ресурсов, которых нет в папке датасета."""
    if not DESCRIPTOR.exists():
        return []
    out = []
    for r in package().resources:
        paths = r.to_descriptor().get("path", [])
        out += [f"{r.name}: {p}" for p in ([paths] if isinstance(paths, str) else paths) if not (ROOT / p).is_file()]
    return out


@functools.lru_cache(maxsize=None)
def _report():
    """Отчёт frictionless или текст исключения, если проверка не выполнилась."""
    try:
        return validate(str(DESCRIPTOR), basepath=str(ROOT))
    except Exception as e:
        return f"проверка frictionless не выполнилась: {type(e).__name__}: {e}"


def descriptor_errors():
    """Ошибки самого datapackage.json."""
    if not DESCRIPTOR.exists():
        return [f"нет файла {DESCRIPTOR.name}"]
    report = _report()
    return [report] if isinstance(report, str) else [e.message for e in report.errors]


def errors(name):
    """Ошибки ресурса `name` по проверке frictionless, в виде строк."""
    report = _report()
    if isinstance(report, str):
        return [report]
    out = []
    for task in report.tasks:
        if task.name != name:
            continue
        for e in task.errors:
            where = []
            if getattr(e, "row_number", None):
                where.append(f"строка {e.row_number}")
            if getattr(e, "field_name", None):
                where.append(f"поле {e.field_name}")
            out.append(f"{', '.join(where) or name}: {e.title}" + (f" ({e.note})" if e.note else ""))
    return out


def _missing_values(resource):
    schema = resource.to_descriptor().get("schema", {})
    return set(schema.get("missingValues", [""]))


def _cells(resource):
    """Сырые значения ячеек: (номер строки файла, {поле: строка})."""
    with resource:
        header = None
        for n, cells in enumerate(resource.read_cells(), start=1):
            if header is None:
                header = [str(c) for c in cells]
                continue
            yield n, {h: ("" if c is None else str(c)) for h, c in zip(header, cells)}


def category_errors(name):
    """Значения полей с `categories`, которых нет в списке категорий."""
    resource = package().get_resource(name)
    fields = resource.to_descriptor()["schema"]["fields"]
    allowed = {}
    for f in fields:
        if "categories" in f:
            values = [c["value"] if isinstance(c, dict) else c for c in f["categories"]]
            allowed[f["name"]] = ({str(v) for v in values}, f.get("delimiter", ",") if f.get("type") == "list" else None)
    if not allowed:
        return []
    missing = _missing_values(resource)
    out = []
    for n, row in _cells(resource):
        for field, (values, sep) in allowed.items():
            cell = row.get(field, "")
            if cell in missing:
                continue
            for item in (cell.split(sep) if sep else [cell]):
                if item not in values:
                    out.append(f"строка {n}, поле {field}: {item!r} нет среди категорий")
    return out


def whitespace_errors(name):
    """Ячейки, значение которых начинается или кончается пробельным символом."""
    out = []
    for n, row in _cells(package().get_resource(name)):
        for field, cell in row.items():
            if cell != cell.strip():
                out.append(f"строка {n}, поле {field}: {cell!r}")
    return out


def list_reference_errors(name, field, ref_name, ref_field):
    """Элементы поля-списка `field` таблицы `name`, которых нет в поле `ref_field` таблицы `ref_name`."""
    resource = package().get_resource(name)
    spec = next(f for f in resource.to_descriptor()["schema"]["fields"] if f["name"] == field)
    sep = spec.get("delimiter", ",")
    known = {"" if v is None else str(v) for v in column(ref_name, ref_field)}
    missing = _missing_values(resource)
    out = []
    for n, row in _cells(resource):
        cell = row.get(field, "")
        if cell in missing:
            continue
        for item in cell.split(sep):
            if item not in known:
                out.append(f"строка {n}, поле {field}: {item!r} нет в {ref_name}.{ref_field}")
    return out


def rows(name):
    """Строки ресурса как словари с типизированными значениями."""
    return package().get_resource(name).read_rows()


def column(name, field):
    return [row[field] for row in rows(name)]


def files_match(name, field, location, pattern="{}"):
    """Файлы корпуса и значения поля таблицы: (нет файла для значения, файл без строки в таблице).

    `location`: папка или zip относительно папки датасета; `pattern` строит имя файла
    из значения, например "{}.txt". Подпапки внутри location не учитываются.
    """
    path = ROOT / location
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            names = {Path(i.filename).name for i in z.infolist() if not i.is_dir() and "__MACOSX" not in i.filename}
    else:
        names = {p.name for p in path.rglob("*") if p.is_file()}
    expected = {pattern.format(v) for v in column(name, field) if v is not None}
    regex = re.compile(re.escape(pattern).replace(re.escape("{}"), ".+"))
    unlisted = {n for n in names if regex.fullmatch(n)} - expected
    return sorted(expected - names), sorted(unlisted)


def report(problems, what=""):
    """Сообщение для assert: первые MAX_REPORT проблем."""
    lines = [f"{what}: {len(problems)}" if what else f"проблем: {len(problems)}"]
    lines += [f"  {p}" for p in problems[:MAX_REPORT]]
    if len(problems) > MAX_REPORT:
        lines.append(f"  … и ещё {len(problems) - MAX_REPORT}")
    return "\n".join(lines)
