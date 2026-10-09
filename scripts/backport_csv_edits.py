#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backport corrections made directly in a CSV file into the source txt.

Some corrections (dehyphenated author names, ИИ→ИЙ, removed OCR junk etc.)
were made by hand in csv/vol_N.csv and never reached txt/vol_N.txt, so
re-running split_records.py would lose them.  This script parses the txt
with split_records.py, aligns the resulting records with the reference
CSV by item number, computes a character-level diff for every field that
differs and applies the edits to the exact positions in the txt lines.

When an edit removes the space that split_records.py inserts between
two joined lines (e.g. "БЕ- ЛЯЕВСКАЯ" -> "БЕЛЯЕВСКАЯ"), the lines are
merged and the emptied line is left blank, so that line numbers of the
following records do not change.

Differences that are not in-place text edits (a value moved to another
field, records that the parser cannot split) are not applied and are
listed in the report for manual inspection.

Usage: backport_csv_edits.py txt/vol_N.txt reference.csv [--dry-run]
"""

import argparse
import collections
import csv
import difflib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_records as sr  # noqa: E402

FIELDS = ['title', 'author', 'alt_title', 'in', 'tail']
JOIN = -1  # tag for a space inserted by split_records when joining lines


def norm_num(num):
    return num.strip().rstrip('.').replace('-', '—')


def records_with_map(lines):
    """Parse lines with split_records and yield (record, charmap) pairs.
    charmap[k] is (lineno, col) of the k-th character of the record text
    in the file, or JOIN for a space inserted between joined lines."""
    numlines = list(sr.numbered_lines(sr.extract_section_to_process(lines)))
    bylineno = {ln: (num, txt, line) for ln, num, txt, line in numlines}
    for rec in sr.iter_records(iter(numlines)):
        if rec.tail == 'MISSING':
            yield rec, None
            continue
        charmap = []
        first = True
        for ln in range(rec.start, rec.end + 1):
            if ln not in bylineno:
                continue
            num, txt, line = bylineno[ln]
            seg = txt if first and num else line
            raw = lines[ln - 1]
            col = raw.find(line) + len(line) - len(seg)
            if not first:
                charmap.append(JOIN)
            charmap.extend((ln, col + i) for i in range(len(seg)))
            first = False
        assert len(charmap) == len(rec.tail), (rec.start, rec.tail)
        yield rec, charmap


def field_edits(text, values, ref):
    """Return a list of (i, j, replacement) edits on text that turn
    field values into the reference values, or None if a field cannot
    be located in the text."""
    edits = []
    cursor = 0
    for f in FIELDS:
        u = values.get(f, '') if f != 'tail' else values['tail']
        v = ref[f]
        if not u.strip():
            if v.strip():
                return None
            continue
        pos = text.find(u, cursor)
        if pos < 0:
            return None
        cursor = pos + len(u)
        us, vs = u.strip(), v.strip()
        if us == vs:
            continue
        if not vs:
            return None
        pos += len(u) - len(u.lstrip())
        sm = difflib.SequenceMatcher(None, us, vs, autojunk=False)
        if sm.ratio() < 0.6:
            return None
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op != 'equal':
                edits.append((pos + i1, pos + i2, vs[j1:j2]))
    return edits


def span_edits(text, values, ref):
    """Fallback for records where text moved between fields (typically
    the end of an author name left in the tail).  Applies when the
    reference record has nothing in alt_title, in and tail: the text
    from the first differing field to the end of the record is diffed
    against the concatenated reference values."""
    if any(ref[f].strip() for f in ('alt_title', 'in', 'tail')) or \
       any(values.get(f, '').strip() for f in ('alt_title', 'in')):
        return None
    if values['title'].strip() != ref['title'].strip():
        start, target = 0, ref['title'].strip() + ' ' + ref['author'].strip()
    elif values['author'].strip() != ref['author'].strip():
        start = text.find(values['author'], len(values['title']))
        target = ref['author'].strip()
    else:
        start, target = len(text) - len(values['tail']), ''
    if start < 0:
        return None
    region = text[start:]
    pos = start + len(region) - len(region.lstrip())
    region = region.strip()
    sm = difflib.SequenceMatcher(None, region, target, autojunk=False)
    if target and sm.ratio() < 0.6:
        return None
    return [(pos + i1, pos + i2, target[j1:j2])
            for op, i1, i2, j1, j2 in sm.get_opcodes() if op != 'equal']


def apply_edits(lines, charmap, edits):
    """Apply edits (on record text coordinates) to file lines in place."""
    # segments: one per joined line, as (lineno, start col, end col)
    segs = []
    segidx = []
    for c in charmap:
        if c == JOIN:
            segidx.append(JOIN)
            continue
        if not segs or segidx[-1] == JOIN:
            segs.append([c[0], c[1], c[1] + 1])
        segs[-1][2] = c[1] + 1
        segidx.append(len(segs) - 1)
    # output groups: each is (set of segments covered, list of chars)
    groups = [(set(), [])]

    def keep(k):
        if segidx[k] == JOIN:
            groups.append((set(), []))
        else:
            ln, col = charmap[k]
            groups[-1][0].add(segidx[k])
            groups[-1][1].append(lines[ln - 1][col])

    k = 0
    for i, j, repl in sorted(edits):
        for m in range(k, i):
            keep(m)
        groups[-1][0].update(s for s in segidx[i:j] if s != JOIN)
        groups[-1][1].extend(repl)
        k = j
    for m in range(k, len(charmap)):
        keep(m)
    for covered, chars in groups:
        first, last = segs[min(covered)], segs[max(covered)]
        newline = lines[first[0] - 1][:first[1]] + ''.join(chars) + lines[last[0] - 1][last[2]:]
        for s in range(min(covered) + 1, max(covered) + 1):
            lines[segs[s][0] - 1] = '\n'
        lines[first[0] - 1] = newline


def aligned(records, refrows):
    ref = {}
    seen = collections.Counter()
    for row in refrows:
        n = norm_num(row['num'])
        seen[n] += 1
        ref[(n, seen[n])] = row
    seen = collections.Counter()
    for rec, charmap in records:
        n = norm_num(str(rec['num']))
        seen[n] += 1
        yield rec, charmap, ref.get((n, seen[n]))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('txt')
    ap.add_argument('refcsv')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with open(args.txt) as f:
        lines = f.readlines()
    with open(args.refcsv) as f:
        refrows = list(csv.DictReader(f))

    stats = collections.Counter()
    pending = []
    for rec, charmap, ref in aligned(records_with_map(lines), refrows):
        if charmap is None:
            continue
        if ref is None:
            stats['not in reference'] += 1
            continue
        text = rec.tail
        values = sr.extract_title_author(rec)
        values = dict(values, tail=rec.tail)
        if all(values.get(f, '').strip() == ref[f].strip() for f in FIELDS):
            continue
        if values['title'] == 'NOPARSE' or ref['title'] == 'NOPARSE':
            stats['skipped: NOPARSE'] += 1
            print('SKIP NOPARSE\t{}\t{}'.format(rec.start, ref['num']))
            continue
        edits = field_edits(text, values, ref)
        if edits is None:
            edits = span_edits(text, values, ref)
        if edits is None:
            stats['skipped: not an in-place edit'] += 1
            print('SKIP MOVED\t{}\t{}'.format(rec.start, ref['num']))
            continue
        if edits:
            stats['records edited'] += 1
            pending.append((charmap, edits))
            for i, j, repl in edits:
                print('EDIT\t{}\t{}\t{!r} -> {!r}'.format(
                    rec.start, ref['num'], text[max(0, i - 15):j + 15],
                    text[max(0, i - 15):i] + repl + text[j:j + 15]))

    for charmap, edits in pending:
        apply_edits(lines, charmap, edits)
    if not args.dry_run:
        with open(args.txt, 'w') as f:
            f.writelines(lines)
    for k, v in sorted(stats.items()):
        print('# {}: {}'.format(k, v), file=sys.stderr)


if __name__ == '__main__':
    main()
