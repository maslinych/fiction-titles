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
