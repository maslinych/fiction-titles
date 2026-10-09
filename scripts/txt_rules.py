#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply named, regex-based corrections to the source txt files.

Each rule is a list of (pattern, replacement) pairs applied line by line
to the titles section (<div class="titles">) of a txt file only.  Every
changed line is reported as "file:lineno: old -> new", so a run of a
rule is fully reproducible and reviewable.

Usage: txt_rules.py RULE [--dry-run] txt/vol_1.txt [txt/vol_2.txt ...]
       txt_rules.py --list
"""

import argparse
import sys

import regex as re


RULES = {}


def rule(name, doc, *subs):
    RULES[name] = (doc, [(re.compile(p, re.V1), r) for p, r in subs])


rule('imya-avt',
     'OCR variants of «Имя авт. не установлено.»: Ймя → Имя, Не → не, '
     'missing or garbled final period.',
     (r'\bЙмя(\s+авт)', r'Имя\1'),
     (r'(Имя\s+авт\.\s+)Не(\s+установлено)', r'\1не\2'),
     (r'(Имя\s+авт(?:\.|ора)\s+не\s+установлено)(?:\.-|1\.|,\s*у|,)?\s*$',
      r'\1.'),
     )


rule('izd',
     'OCR Й for И in «Изд. также под загл.»: Йзд. → Изд.',
     (r'\bЙзд\.', r'Изд.'),
     )


HOMOGLYPHS = str.maketrans('ABCEHKMOPTXYaceopxy', 'АВСЕНКМОРТХУасеорху')
ROMAN = re.compile(r'M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})')


def cyrillic_homoglyphs(m):
    return m.group(0).translate(HOMOGLYPHS)


def caps_homoglyphs(m):
    w = m.group(0)
    return w if ROMAN.fullmatch(w) else w.translate(HOMOGLYPHS)


rule('homoglyphs',
     'Latin letters looking like Cyrillic ones (A, B, C, E, H, K, M, O, P, T, X, '
     'Y, a, c, e, o, p, x, y) in words that also contain Cyrillic letters '
     '(HEXАЙ → НЕХАЙ), and Latin-only words in capitals next to a Cyrillic word '
     'in capitals or starting a continuation line before a comma '
     '(БРЕЙТ-/MAH, → БРЕЙТ-/МАН,); roman numerals are left alone.',
     (r'\p{L}*\p{Cyrillic}\p{L}*', cyrillic_homoglyphs),
     (r'(?<=[\p{Cyrillic}&&\p{Lu}][-\s]+)[ABCEHKMOPTXY]{2,}(?!\p{L})'
      r'|(?<!\p{L})[ABCEHKMOPTXY]{2,}(?=[-\s]+[\p{Cyrillic}&&\p{Lu}])'
      r'|^\s*[ABCEHKMOPTXY]{2,}(?=,)', caps_homoglyphs),
     )


def titles_section(lines):
    """Yield indices of the lines inside the titles section"""
    inside = False
    for i, line in enumerate(lines):
        if re.match(r'\s*<div class="titles">', line):
            inside = True
        elif re.match(r'\s*</div>', line) and inside:
            inside = False
        elif inside:
            yield i


def apply_rule(name, path, dry_run=False):
    doc, subs = RULES[name]
    with open(path) as f:
        lines = f.readlines()
    changed = 0
    for i in titles_section(lines):
        old = lines[i].rstrip('\n')
        new = old
        for pat, repl in subs:
            new = pat.sub(repl, new)
        if new != old:
            changed += 1
            print('{}:{}: {} -> {}'.format(path, i + 1, old.strip(), new.strip()))
            lines[i] = new + '\n'
    if not dry_run:
        with open(path, 'w') as f:
            f.writelines(lines)
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rule', nargs='?', choices=sorted(RULES))
    ap.add_argument('files', nargs='*')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--list', action='store_true', help='list available rules')
    args = ap.parse_args()
    if args.list or not args.rule:
        for name, (doc, _) in sorted(RULES.items()):
            print('{}\n    {}'.format(name, doc))
        return
    total = 0
    for path in args.files:
        total += apply_rule(args.rule, path, args.dry_run)
    print('# {}: {} lines changed'.format(args.rule, total), file=sys.stderr)


if __name__ == '__main__':
    main()
