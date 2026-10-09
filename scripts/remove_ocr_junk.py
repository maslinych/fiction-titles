#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove OCR noise left over at the end of the records.

Specks on the scans were often recognized as stray characters at the
ends of lines ("Николаевич.        w", a line with a single «‘»).  The
parser puts them into the tail.  This script parses a txt file with
split_records.py and, for every record whose tail (after alternative
titles, «В кн.:» and notes have been taken out of it) consists only of
noise at the very end of the record, deletes exactly those characters
from the txt.

Noise: at most 8 characters without digits, brackets, quotes or "***",
and with no letter except one lowercase letter not followed by a period
or an apostrophe ("w", "м", "*", "_", "^", "•", ".", ","…).  Tails with
digits, capitals or lowercase initials (often a garbled initial: "З."
read as "3.", "М." as "м.", "д'" as "д\\") are left alone.  Every
deletion is reported.

Usage: remove_ocr_junk.py [--dry-run] txt/vol_N.txt
"""

import argparse
import os
import sys

import regex as re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_records as sr  # noqa: E402
from backport_csv_edits import records_with_map, apply_edits  # noqa: E402

JUNK = re.compile(r'^(?!.*[*]{3})[^\p{L}\d()\[\]«»"„“]*'
                  r'(\p{Ll}(?![.\'’\\])[^\p{L}\d()\[\]«»"„“]*)?$')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('txt')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with open(args.txt) as f:
        lines = f.readlines()
    n = 0
    for rec, charmap in records_with_map(lines):
        if charmap is None:
            continue
        text = rec.tail
        sr.extract_title_author(rec)
        if rec['title'] == 'NOPARSE':
            continue
        raw_tail = rec.tail
        sr.split_note(sr.split_tail_aux(rec))
        junk = rec.tail.strip()
        if not junk or len(junk) > 8 or not JUNK.match(junk):
            continue
        start = text.find(junk, len(text) - len(raw_tail))
        assert start >= 0, (rec.start, text, junk)
        if start + len(junk) != len(text.rstrip()):
            continue  # noise between the author and «Изд. также…» etc. is a separator
        apply_edits(lines, charmap, [(start, start + len(junk), '')])
        n += 1
        print('{}:{}: {!r}'.format(args.txt, charmap[start][0], junk))
    if not args.dry_run:
        with open(args.txt, 'w') as f:
            f.writelines(lines)
    print('# {}: {} junk tails removed'.format(args.txt, n), file=sys.stderr)


if __name__ == '__main__':
    main()
