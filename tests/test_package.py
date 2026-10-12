"""Общие проверки всех таблиц датасета по описанию datapackage.json (см. dvcheck.py).

Этот файл одинаков во всех датасетах Репозитория; проверки, специфичные для датасета,
находятся в соседних файлах test_*.py.
"""
import pytest

import dvcheck


def test_descriptor():
    """datapackage.json читается и соответствует стандарту."""
    if dvcheck.descriptor_errors():
        pytest.fail(dvcheck.report(dvcheck.descriptor_errors(), "ошибки datapackage.json"), pytrace=False)


def test_files():
    """Все файлы, перечисленные в datapackage.json, на месте."""
    missing = dvcheck.missing_files()
    if missing:
        pytest.fail(dvcheck.report(missing, "нет файлов"), pytrace=False)


@pytest.mark.parametrize("name", dvcheck.table_names())
def test_resource(name):
    """Таблица соответствует схеме: типы, обязательные поля, ключи, ограничения."""
    problems = dvcheck.errors(name)
    if problems:
        pytest.fail(dvcheck.report(problems, f"ошибки в {name}"), pytrace=False)


@pytest.mark.parametrize("name", dvcheck.table_names())
def test_categories(name):
    """Категориальные поля содержат только значения из списка categories."""
    problems = dvcheck.category_errors(name)
    if problems:
        pytest.fail(dvcheck.report(problems, f"значения вне категорий в {name}"), pytrace=False)


@pytest.mark.parametrize("name", dvcheck.table_names())
def test_whitespace(name):
    """В ячейках нет пробелов в начале и в конце значения."""
    problems = dvcheck.whitespace_errors(name)
    if problems:
        pytest.fail(dvcheck.report(problems, f"лишние пробелы в {name}"), pytrace=False)
