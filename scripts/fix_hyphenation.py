#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve line-break hyphenation left in the records.

Two kinds of candidates are looked for in the text of every record
(as assembled by split_records.py):

1. a hyphen followed by a space ("Ро- ман", "ВО- РОБЬЕВ", "Ванюха-
   Перстень", "1- м"): a hyphen at the end of a printed line, the space
   is always an artifact;
2. a hyphen inside a word in capitals ("ШАГИ-НЯН", "ПАЗУ-ХИН"): a word
   break whose line break was lost in OCR, or a genuine double name
   (НОВИКОВ-ПРИБОЙ, БИЧЕР-СТОУ).

For each candidate L-R the script decides whether to join the parts
(LR) or to keep the hyphen (L-R), using
- the author indexes (txt/vol_7.txt and the names-index sections of
  vols 1-6, typeset independently, with different line breaks): one
  form must outnumber the other at least 3:1 there, and the records
  must not contradict it;
- otherwise the frequency of both forms in the parsed records of all
  volumes (the candidate occurrence itself excluded); for words in
  capitals one form must outnumber the other at least 2:1.
Hyphens after a digit ("1- м") are kept.  Candidates of kind 2 are
only joined on evidence; otherwise they are left alone.  Candidates of
kind 1 without any evidence are reported as SKIP and left unchanged.

Every decision is printed with its evidence.

Usage: fix_hyphenation.py [--dry-run] txt/vol_1.txt ... txt/vol_6.txt
(all volumes must be given together: the lexicon is built from them)
"""

import argparse
import collections
import itertools
import os
import sys

import regex as re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_records as sr  # noqa: E402
from backport_csv_edits import records_with_map, apply_edits  # noqa: E402

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'txt', 'vol_7.txt')

# a hyphenated token; hyphens may be followed by whitespace (line breaks)
TOKEN = re.compile(r'(?<![\p{L}\d-])[\p{L}\d]+(?:-\s*\p{L}+)+(?![\p{L}\d])')
WORD = re.compile(r'\p{L}+(?:-\p{L}+)*')


def index_lines(paths):
    """Lines of the author indexes: vol 7 and names-index sections"""
    with open(INDEX) as f:
        yield from f
    for path in paths:
        inside = False
        with open(path) as f:
            for line in f:
                if '<div class="names-index">' in line:
                    inside = True
                elif inside and line.startswith('</div>'):
                    inside = False
                elif inside:
                    yield line


def build_lexicons(paths, parsed):
    index = collections.Counter()
    for line in index_lines(paths):
        for w in WORD.findall(line):
            if w[0].isupper():  # names only
                index[w.upper()] += 1
    corpus = collections.Counter()
    for recs in parsed.values():
        for rec, charmap in recs:
            for w in WORD.findall(rec.text):
                corpus[w.upper() if w.isupper() else w.lower()] += 1
    return index, corpus


def evidence(form, caps, index, corpus):
    norm = form.upper() if caps else form.lower()
    return index[form.upper()], corpus[norm]


def dominant(scores, ratio, minimum=1):
    """Index of the score that outnumbers all others ratio:1, or None"""
    best = max(range(len(scores)), key=lambda i: scores[i])
    rest = max([s for i, s in enumerate(scores) if i != best], default=0)
    if scores[best] >= minimum and scores[best] >= ratio * rest:
        return best
    return None


def resolve(segs, seps, index, corpus):
    """Decide for each hyphen of a token: '' (join), '-' (keep hyphen,
    drop the space) or None (leave as is).  Returns (states, evidence)."""
    spaced = [bool(sep.strip('-')) for sep in seps]
    caps = all(seg.isupper() for seg in segs)
    free = []
    for i, sep in enumerate(seps):
        left, right = segs[i], segs[i + 1]
        if left[-1].isdigit() or (len(left) == 1 and len(right) == 1):
            continue  # 1- м, К- К: never joined
        if not spaced[i] and not (caps and len(left) > 1 and len(right) > 1):
            continue  # an ordinary hyphen
        free.append(i)
    states = ['-' if spaced[i] else None for i in range(len(seps))]
    for i in range(len(seps)):
        if i not in free and spaced[i] and (segs[i][-1].isdigit()):
            states[i] = '-'
        elif i not in free and spaced[i]:
            states[i] = None
    if not free:
        return states, 'fixed'
    combos = []
    for bits in itertools.product(('-', ''), repeat=len(free)):
        st = ['-'] * len(seps)
        for i, b in zip(free, bits):
            st[i] = b
        form = segs[0] + ''.join(st[i] + segs[i + 1] for i in range(len(seps)))
        combos.append((st, form) + evidence(form, caps, index, corpus))
    # the token itself is counted once in the corpus if it had no spaces
    if not any(spaced):
        st, form, i_n, c_n = combos[0]
        combos[0] = (st, form, i_n, c_n - 1)
    ev = ' '.join('{}:{}/{}'.format(form, i_n, c_n) for st, form, i_n, c_n in combos)
    i_scores = [c[2] for c in combos]
    c_scores = [c[3] for c in combos]
    best = None
    if any(i_scores):
        # the author indexes decide, if one form clearly dominates there
        # and the records do not contradict it
        best = dominant(i_scores, 3)
        if best is not None and c_scores[best] < max(c_scores):
            best = None
    elif caps:
        best = dominant(c_scores, 2, minimum=2)
    else:
        best = dominant(c_scores, 1.01)
    if best is not None:
        st = combos[best][0]
        return [st[i] if (i in free or states[i]) else None for i in range(len(seps))], ev
    if any(i_scores) or any(c_scores):
        return [None] * len(seps), ev
    # no evidence at all: a lowercase continuation after a line break
    # is a plain word break
    out = []
    for i in range(len(seps)):
        if i in free and spaced[i] and segs[i + 1][0].islower():
            out.append('')
        else:
            out.append(None)
    return out, ev + ' lowercase'


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('txt', nargs='+')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    files, parsed = {}, {}
    for path in args.txt:
        with open(path) as f:
            files[path] = f.readlines()
        recs = []
        for rec, charmap in records_with_map(files[path]):
            if charmap is not None:
                rec.text = rec.tail
                recs.append((rec, charmap))
        parsed[path] = recs
    index, corpus = build_lexicons(args.txt, parsed)

    stats = collections.Counter()
    for path in args.txt:
        for rec, charmap in parsed[path]:
            text, edits = rec.text, []
            for m in TOKEN.finditer(rec.text):
                parts = re.split(r'(-\s*)', m.group(0))
                segs, seps = parts[0::2], parts[1::2]
                states, ev = resolve(segs, seps, index, corpus)
                pos = m.start() + len(segs[0])
                new = segs[0]
                for i, sep in enumerate(seps):
                    spaced = bool(sep.strip('-'))
                    st = states[i]
                    if st == '':
                        edits.append((pos, pos + len(sep), ''))
                        stats[('spaced' if spaced else 'caps', 'join')] += 1
                    elif st == '-' and spaced:
                        edits.append((pos + 1, pos + len(sep), ''))
                        stats[('spaced', 'keep')] += 1
                    elif spaced:
                        stats[('spaced', 'skip')] += 1
                    new += (sep if st is None else st) + segs[i + 1]
                    pos += len(sep) + len(segs[i + 1])
                if new != m.group(0) or any(sep.strip('-') for sep in seps):
                    action = 'SKIP' if new == m.group(0) else 'FIX'
                    print('{}\t{}:{}\t{} -> {}\t{}'.format(
                        action, path, charmap[m.start()][0],
                        re.sub(r'\s+', ' ', m.group(0)), new, ev))
            if edits:
                apply_edits(files[path], charmap, edits)
        if not args.dry_run:
            with open(path, 'w') as f:
                f.writelines(files[path])
    for (kind, action), n in sorted(stats.items()):
        print('# {} {}: {}'.format(kind, action, n), file=sys.stderr)


if __name__ == '__main__':
    main()
