#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Join author surnames split by a space ("ГОРЬ КИЙ" -> "ГОРЬКИЙ").

Candidates are found the same way as tests/test_fiction_titles.py
(test_author_surname_not_split) does: a part of the `author` value of
csv/vol_N.csv in capitals with a space inside that, with the spaces
removed, is a headword of the vol. 7 author index, and with them is
not.  The part is then joined in the record's lines of txt/vol_N.txt
(start..end of the CSV row).  Line breaks inside the part are moved
after the joined word, so that line numbers do not change.

Exceptions (spelled separately in the source) are taken from
SPLIT_AS_IN_SOURCE of the test.

Every change is printed; candidates not found in the txt are reported
as SKIP.

Usage: fix_split_surnames.py [--dry-run] N ...   (volume numbers)
"""

import argparse
import csv
import os
import sys

import regex as re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tests'))
from test_fiction_titles import SPLIT_AS_IN_SOURCE, normalize, vol7_headwords  # noqa: E402


def candidates(volume, headwords):
    with open(os.path.join(ROOT, f'csv/vol_{volume}.csv')) as f:
        for row in csv.DictReader(f):
            for part in re.split(r'[,()]', row['author']):
                part = part.strip()
                if ' ' not in part or not re.fullmatch(r"[А-ЯЁ' -]+", part):
                    continue
                joined = normalize(part.replace(' ', ''))
                if (joined in headwords and normalize(part) not in headwords
                        and (volume, row['num'], part) not in SPLIT_AS_IN_SOURCE):
                    yield row, part


def join(m):
    """The joined word; line breaks inside it are kept after it."""
    text = m.group(0)
    return re.sub(r'\s+', '', text) + '\n' * text.count('\n')


def fix_volume(volume, headwords, dry_run):
    path = os.path.join(ROOT, f'txt/vol_{volume}.txt')
    with open(path) as f:
        lines = f.read().split('\n')
    for row, part in candidates(volume, headwords):
        start, end = int(row['start']), int(row['end'])
        chunk = '\n'.join(lines[start - 1:end])
        tokens = part.split()
        pattern = r'(?<![\p{L}-])' + r'\s+'.join(map(re.escape, tokens)) + r'(?![\p{L}-])'
        found = re.findall(pattern, chunk)
        if len(found) != 1:
            print(f'SKIP\tvol_{volume}\t{row["num"]}\t{part!r}: {len(found)} matches in txt {start}-{end}')
            continue
        new_lines = re.sub(pattern, join, chunk).split('\n')
        assert len(new_lines) == end - start + 1, (volume, row['num'], new_lines)
        print(f'JOIN\tvol_{volume}\t{row["num"]}\t{part!r} -> {part.replace(" ", "")!r}')
        lines[start - 1:end] = new_lines
    if not dry_run:
        with open(path, 'w') as f:
            f.write('\n'.join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('volumes', nargs='+', type=int)
    args = ap.parse_args()
    headwords = vol7_headwords()
    for volume in args.volumes:
        fix_volume(volume, headwords, args.dry_run)


if __name__ == '__main__':
    main()
