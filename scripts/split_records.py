#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import regex as re
import csv
import argparse
import sys
from collections import OrderedDict


AUTHOR_KEY = r"""
((?<key>
((\p{Lu}[.]\s*|и\s+){2,4}|-\p{Lu}{2,4})\s+[(]\p{Lu}+[^)]+[)]                  # В. Л. Т. (РАСШИФРОВКА)
|
  \p{Lu}+([’']?(\p{Lu}+|\s+\p{Lu}+|-|\s+\p{Lu}[.](?=\s*(\p{Lu}[.]|\p{Lu}{2}|[(]\p{Lu}))){1,9}|[*]{1,5}\p{Lu}{0,3}|[.][.][.]+\s*\p{Lu}{0,3}|—\p{Lu}{1,6})\s* # ФАМИЛИЯ или ПСЕВДОНИМ M*** БАЗ...В
  (\[!\]\s*)?                                              # [!] иногда
  (,(\s+\p{Lu}\p{Ll}{0,2}[.]|\s+\p{Lu}\p{Ll}+-\p{Lu}\p{Ll}+|\s+\p{Lu}[\p{Ll}-]+|\s+д[’']|\s+(кызы|оглы|ибн|братья|графиня|граф|князь|княгиня|барон|баронесса|инфанта|г-жа|младший|старший|сотник|имп[.]|аф|делле|делла|дель|де|ди|да|дю|ла|ле|ван|фон|дер|и)(?!\p{L})|\s+[(](отец|сын)[)]){1,5}\s*)?  # имена или инициалы, частицы
  (\[!\]\s*)?                                              # [!] иногда
    ( # раскрытие автора в круглых или квадратных скобках
      ([(]\p{Lu}+[^)]+[)]\s*){0,2}| # (НАСТ имя)
      (\[\p{Lu}+[^]]*\])? # [АВТОР ...]
    )
|
О[.]\s*ГЕНРИ                                            # О. ГЕНРИ
|
Имя\s+авт([.]|ора)\s+не\s+установлено # Имя авт. не установлено
) # 
[.]?\s*)
"""

TITLE_AUX = r"""
(В\s+кн[.]:?\s+(?<in>.+)|
Изд.\s+также\s+под\s+загл.\p{Ll}*[:;]?\s+(?<alt_title>.+)|
На\s+тит.\s+л.\s+загл[.]:?\s+(?<alt_title>.+)|
Загл[.]\s+обл[.]:?\s+(?<alt_title>.+))
"""

# \p{Lu}(\p{Lu}+- |\p{Lu}+ |\P{Lu}\.\s*|\p{Lu}+)+\p{Lu}\s*,

class BibItem(object):
    """A class to hold a sequential bibliographic number.  In contrast to
    the standard integer it can have a letter suffix for the items
    inserted in the list. The class provides methods for comparison of
    standard and suffixed numbers for correct item numebering and
    alignment.  Supports operations with integers: comparison,
    addition, subtraction. These result in integers in all cases.
    Similar operations with two BibItems result in a BibItem.
    """
    def __init__(self, num=0, suffix=0, span=0, string=None):
        if string is None:
            self.num = num
            self.suffix = suffix
            self.span = span
        elif string == 0:
            self.num = 0
            self.suffix = 0
            self.span = 0
        else:
            m = re.match(r"(?<num>[1-9][0-9]*)(—(?<span>[1-9][0-9]*))?(?<suffix>[aабвгд])?$", string)
            suffixdict = {None: 0, 'a': 1, 'а': 1, 'б': 2, 'в': 3, 'г': 4, 'д': 5}
            try:
                self.num = int(m.group('num'))
                self.suffix = suffixdict[m.group('suffix')]
                if m.group('span'):
                    self.span = int(m.group('span'))
                else:
                    self.span = 0
            except AttributeError:
                raise ValueError("Incorrect value for BibItem: %s" % string)
        self.value = (self.num, self.suffix, self.span)
        if self.span:
            self.last = self.span
        else:
            self.last = self.num

    def __str__(self):
        numtosuf = {0: '', 1: 'а', 2: 'б', 3: 'в', 4: 'г', 5: 'д'}
        if self.span:
            return '—'.join([str(self.num), str(self.span)])
        else:
            return ''.join([str(self.num), numtosuf[self.suffix]])

    def __eq__(self, other):
        if isinstance(other, int):
            return self.last + self.suffix == other
        else:
            return self.value == other.value

    def __lt__(self, other):
        if isinstance(other, int):
            return self.last + self.suffix < other
        else:
            return self.value < other.value

    def __gt__(self, other):
        if isinstance(other, int):
            return self.last + self.suffix > other
        else:
            return self.value > other.value

    def __add__(self, other):
        if isinstance(other, int):
            return self.last + self.suffix + other
        else:
            return self.last + other.last + self.suffix + other.suffix

    def __sub__(self, other):
        if isinstance(other, int):
            return self.last + self.suffix - other
        else:
            return self.last + self.suffix - other.last - other.suffix


class Record(OrderedDict):
    def __init__(self, tail='', start=0, end=0):
        super(Record, self).__init__()
        self.tail = tail
        self.start = start
        self.end = end

    def serialize(self):
        out = {}
        out['start'] = self.start
        out['end'] = self.end
        for k, v in self.items():
            out[k] = normalize_space(str(v))
        out['tail'] = normalize_space(self.tail)
        return out


def normalize_space(s):
    """Collapse runs of whitespace and strip"""
    return re.sub(r'\s+', ' ', s).strip()


def extract_number(line):
    """Detect if a line matches a pattern for a numbered bibliography item
    Return a tuple with a number and a text line. If a line doesn't have the
    number return zero and full line as output.
    """
    num = re.match(r'\s*(?<num>[1-9][0-9]*([—-][1-9][0-9]*)?[aабвгд]?)\.\s+(?<tail>.+)', line)
    if num:
        # normalize ranges written with a hyphen to the em dash form (101—102)
        return (num.group('num').replace('-', '—'), num.group('tail'))
    else:
        return (0, line)


def extract_section_to_process(infile):
    """Extract section containing numbered items from a scanned text file. 
    The section should be delimited with the <div>-style markup.
    Yields (lineno, line) tuples, lineno being the line number in the file.
    """
    inside = False
    for lineno, line in enumerate(infile, start=1):
        if re.match(r'\s*<div class="titles">', line):
            inside = True
            continue
        elif re.match(r'\s*</div>', line) and inside:
            inside = False
            continue
        if inside:
            yield (lineno, line)


def numbered_lines(lines):
    """Generator producing numbered lines as tuples
    (lineno, number, text without number, full line)"""
    for lineno, line in lines:
        line = line.strip()
        if line.startswith('#END'):
            break
        if line:
            num, tail = extract_number(line)
            yield (lineno, num, tail, line)


def iter_records(numlines, k=101):
    """Join a series of numbered lines into a list of sequentially
numbered items (Record instances with a defined 'num' key, tail
attribute and start and end line numbers)
    """
    itemno = 0
    stack = []
    startline = 0
    for lineno, n, txt, line in numlines:
        if n == 0:
            num = 0
        else:
            num = BibItem(string=n)
        if num > itemno:
            if num - itemno == 1:
                # we have a regular next item
                if stack:
                    rec = Record(tail = ' '.join(stack))
                    rec['num'] = itemno
                    rec.start = startline
                    rec.end = lineno - 1
                    yield rec
                    stack = []
                startline = lineno
            else:
                if num - itemno > k:
                    # gap in numbers is too large, unlikely to be the next
                    # number, treat as a regular textual line (with an
                    # accidental number in the beginning, like a year or
                    # a printrun figure)
                    stack.append(line)
                    continue
                # we have a moderate gap in numbering, treat as next item
                rec = Record(tail = ' '.join(stack))
                rec['num'] = itemno
                rec.start = startline
                rec.end = lineno - 1
                yield rec
                stack = []
                itemno += 1
                startline = lineno
                while num > itemno:
                    if num.num > itemno:
                        rec = Record(tail = 'MISSING', start = startline, end = lineno - 1)
                        rec['num'] = itemno
                        yield rec
                    itemno += 1
            itemno = num
            stack.append(txt)
        elif num == 0 and itemno > 0:
            # non-numbered line, collect as a continuation of a curent item
            stack.append(txt)
        elif num < itemno:
            # a lesser number, not a next item, treat as an item continuation
            stack.append(line)
    else:
        # end of file: yield a final record
        rec = Record(tail = ' '.join(stack))
        rec['num'] = str(itemno)
        rec.start = startline
        rec.end = lineno
        yield rec


def parse_author(rec, match_obj):
    pass


def parse_title(rec):
    if rec['title'] == 'NOPARSE':
        return rec


def extract_title_author(rec, verbose=False):
    if '#' in rec.tail:
        # manual markup: title # author [@ auxiliary information]
        has_diez = re.match(r'^(?<title>[^#]+?)\s*[#]\s*(?<author>[^@]*?)\s*(@\s*(?<rest>.*))?$',
                            rec.tail, re.U)
        rec['title'] = has_diez.group('title')
        author = has_diez.group('author')
        rest = has_diez.group('rest') or ''
        if not rest:
            # auxiliary information not separated with @
            aux = re.match(r'^(?<author>.*?)\s+(?=' + TITLE_AUX + ')(?<rest>.*)$',
                           author, re.U | re.VERBOSE | re.V1)
            if aux:
                author, rest = aux.group('author'), aux.group('rest')
        rec['author'] = author
        rec['alt_title'] = ''
        rec['in'] = ''
        rec.tail = rest
        has_aux = re.match('^' + TITLE_AUX + '$', rest, re.U | re.VERBOSE | re.V1)
        if has_aux:
            rec['alt_title'] = has_aux.group('alt_title') or ''
            rec['in'] = has_aux.group('in') or ''
            rec.tail = ''
        return rec
    # the initial of О. ГЕНРИ belongs to the author, not to the title
    author_key = re.compile(r"^(?<title>.*[.?!\]»])(?!(?<=(?<!\p{L})О[.])\s+ГЕНРИ)\s+(?<author>" + AUTHOR_KEY + r'(,\s+' + AUTHOR_KEY + '){0,4})' +
                            '(@?' + TITLE_AUX + ')?' + "(?<tail>.*?)$", re.U | re.VERBOSE | re.V1)
    has_author_key = author_key.match(rec.tail)
    initials = re.compile(r'^(?<title>.+?)\s+(?<author>(\p{Lu}[.]\s*){1,5})(?<tail>.*)$', re.U)
    has_initials = initials.match(rec.tail)
    if has_author_key:
        rec['title'] = has_author_key.group('title')
        rec['author'] = has_author_key.group('author')
        rec['alt_title'] = has_author_key.group('alt_title') or ''
        rec['in'] = has_author_key.group('in') or ''
        rec.tail = has_author_key.group('tail')
    elif has_initials:
        rec['title'] = has_initials.group('title')
        rec['author'] = has_initials.group('author')
        rec['alt_title'] = ''
        rec.tail = has_initials.group('tail')
    else:
        rec['title'] = 'NOPARSE'
        rec['author'] = ''
    return rec


def parse_arguments():
    parser = argparse.ArgumentParser(description='Split scanned txt file into numbered records (CSV)', epilog=""" The idea is to rely on the sequentially numbered items. The script
identifies all lines that look like a numbered item. All non-itemlike
lines are joined to the previous numbered line, until the next tem in
a sequence is encountered. When an expected next item is missing, a
'MISSING' tag is printed in the output CSV file.""")
    parser.add_argument('infile', nargs='?', help='Input file (txt)',
                        type=argparse.FileType('r'), default=sys.stdin)
    parser.add_argument('outfile', nargs='?', help='Output file (csv)',
                        type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('-v', '--verbose', help='Show regex debugging output',
                        action='store_true')
    return parser.parse_args()


def main():
    """main processing"""
    args = parse_arguments()
    csv_writer = csv.DictWriter(args.outfile, fieldnames=['start', 'end', 'num', 'title', 'author', 'alt_title', 'in', 'tail'],
                                lineterminator='\n')
    # author = None               
    lines = extract_section_to_process(args.infile)
    csv_writer.writeheader()
    for rec in iter_records(numbered_lines(lines)):
        row = extract_title_author(rec, verbose=args.verbose)
        csv_writer.writerow(row.serialize())
        # row = extract_author(rec, author, verbose=args.verbose)
        # author = row['author']
        # csv_writer.writerow(row.serialize())


if __name__ == '__main__':
    main()
