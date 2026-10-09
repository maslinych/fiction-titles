#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print a summary table of the dataset (Markdown) for README.md.

Usage: stats.py csv/vol_1.csv ... csv/vol_6.csv
"""

import csv
import os
import sys

LETTERS = {
    'vol_1.csv': 'А–Г',
    'vol_2.csv': 'Д–З',
    'vol_3.csv': 'И–Л',
    'vol_4.csv': 'М–О',
    'vol_5.csv': 'П–С (Сек.)',
    'vol_6.csv': 'С (Сел.)–Я, A–Z',
}

COLUMNS = ['Файл', 'Буквы', 'Записей', 'alt_title', 'in', 'note',
           'Непустой tail', 'MISSING']


def pct(n, total):
    return '{} ({:.1f}%)'.format(n, 100 * n / total)


def count(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    missing = sum(r['tail'] == 'MISSING' for r in rows)
    recs = [r for r in rows if r['tail'] != 'MISSING']
    return {
        'Записей': len(recs),
        'alt_title': sum(bool(r['alt_title']) for r in recs),
        'in': sum(bool(r['in']) for r in recs),
        'note': sum(bool(r['note']) for r in recs),
        'Непустой tail': sum(bool(r['tail']) for r in recs),
        'MISSING': missing,
    }


def main():
    rows = []
    total = dict.fromkeys(COLUMNS[2:], 0)
    for path in sys.argv[1:]:
        name = os.path.basename(path)
        c = count(path)
        for k in total:
            total[k] += c[k]
        rows.append([name, LETTERS.get(name, ''), str(c['Записей']),
                     str(c['alt_title']), str(c['in']), str(c['note']),
                     pct(c['Непустой tail'], c['Записей']), str(c['MISSING'])])
    rows.append(['**Всего**', '', '**{}**'.format(total['Записей']), str(total['alt_title']),
                 str(total['in']), str(total['note']),
                 pct(total['Непустой tail'], total['Записей']), str(total['MISSING'])])
    # separator lengths proportional to the content: pandoc uses them
    # as relative column widths for wide tables
    widths = [max(len(r[i]) for r in rows + [COLUMNS]) for i in range(len(COLUMNS))]
    widths[0] += 3
    print('| ' + ' | '.join(COLUMNS) + ' |')
    print('|' + '|'.join('-' * w if i < 2 else '-' * (w - 1) + ':'
                         for i, w in enumerate(widths)) + '|')
    for r in rows:
        print('| ' + ' | '.join(r) + ' |')


if __name__ == '__main__':
    main()
