#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix author names cut off by an OCR period instead of a comma.

OCR often reads the comma after an author's surname as a period
("СБИТНЕВ. Юрий Николаевич." instead of "СБИТНЕВ, Юрий Николаевич."),
so the parser stops the author at the surname and the given names end
up in the tail.  This script parses a txt file with split_records.py,
finds records whose author ends with a surname in capitals followed by
a period and whose tail starts with a personal name, and replaces that
period with a comma at its exact position in the txt.  Every change is
reported.

Usage: fix_author_period.py [--dry-run] txt/vol_N.txt
"""

import argparse
import os
import sys

import regex as re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_records as sr  # noqa: E402
from backport_csv_edits import records_with_map  # noqa: E402

# words that start auxiliary remarks rather than given names
STOPWORDS = {'Изд', 'Загл', 'На', 'В', 'Ошибочно', 'Предполагаемое', 'Подлинное',
             'Имя', 'Пер', 'Сост', 'Ред', 'Сюжет', 'Кн', 'Ч', 'Т', 'Вып', 'Соч'}

SURNAME_END = re.compile(r'\p{Lu}{2,}[.]\s*$')
GIVEN_NAME = re.compile(r'^(?<name>\p{Lu}\p{Ll}+)(?:[-\s]\p{Lu}\p{Ll}+){0,2}'
                        r'(?:\s+(?:де|фон|ван|дер|оглы|кызы|ибн|ди|да|дю|ла|ле))*'
                        r'(?:[.,]|\s+[(]|\s+\p{Lu}[.])')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('txt')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with open(args.txt) as f:
        lines = f.readlines()
    edits = []
    for rec, charmap in records_with_map(lines):
        if charmap is None:
            continue
        text = rec.tail
        sr.extract_title_author(rec)
        author, tail = rec.get('author', ''), rec.tail.strip()
        if not SURNAME_END.search(author):
            continue
        m = GIVEN_NAME.match(tail)
        if not m or m.group('name') in STOPWORDS:
            continue
        pos = text.find(author, len(rec['title'])) + len(author.rstrip()) - 1
        assert text[pos] == '.', (rec.start, text)
        ln, col = charmap[pos]
        edits.append((ln, col))
        print('{}:{}: {} {} -> {}, {}'.format(args.txt, ln, author.strip(), tail[:40],
                                             author.strip()[:-1], tail[:40]))
    for ln, col in edits:
        line = lines[ln - 1]
        lines[ln - 1] = line[:col] + ',' + line[col + 1:]
    if not args.dry_run:
        with open(args.txt, 'w') as f:
            f.writelines(lines)
    print('# {}: {} authors fixed'.format(args.txt, len(edits)), file=sys.stderr)


if __name__ == '__main__':
    main()
