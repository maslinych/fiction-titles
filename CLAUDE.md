# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A dataset project, not an application: OCR'd text of the 7-volume Soviet bibliography «Указатель заглавий произведений художественной литературы, 1801–1975» is parsed into CSV tables (one row per title). Published on the Russian literature open data repository (DOI 10.31860/openlit-2022.12-B012); `README.md` is the dataset's user-facing description (in Russian) and is rendered to PDF for the dataverse release.

## Commands

```sh
make split                                  # regenerate csv/vol_N.csv from txt/vol_N.txt (vols 1–6)
make csv/vol_3.csv                          # regenerate a single volume
python3 scripts/split_records.py txt/vol_3.txt csv/vol_3.csv   # same, directly
make stats                                  # summary table for README.md (scripts/stats.py)
make README.tex README.pdf                  # pandoc + xelatex (PT fonts via fontspec); README.md is the source
```

The parser needs the third-party `regex` module (not stdlib `re`) — it relies on `\p{Lu}`, named groups like `(?<name>...)`, and `regex.V1`. There are no tests; verify changes by regenerating CSVs and inspecting `git diff csv/`.

## Data flow and workflow

`pdf/vol_N.pdf` (scans) → `txt/vol_N.txt` (OCR text, hand-corrected) → `scripts/split_records.py` → `csv/vol_N.csv`.

The work is iterative: run the parser, find bad rows (`title == NOPARSE`, `tail == MISSING`, junk in `tail`), then fix either the **source txt** (OCR errors, broken numbering) or the parser regexes, and re-run. Commits typically touch `txt/vol_N.txt` and `csv/vol_N.csv` together. Prefer fixing the txt source over hand-editing CSVs, since CSVs get overwritten on re-parse.

Only the tracked files (`git ls-files`) are part of the project; the many untracked files in the root (`vol_*.csv`, `*~`, `OR/`, `dataverse_files.zip`, LaTeX build artifacts, etc.) are scratch/draft material — don't treat them as canonical.

## `scripts/split_records.py` architecture

1. `extract_section_to_process` — only lines between `<div class="titles">` and `</div>` in the txt are parsed; a line starting with `#END` stops processing.
2. `numbered_lines` / `extract_number` — detects lines beginning with an item number like `123.`, `12а.`, or a range `101—102.` (em dash; Cyrillic/Latin letter suffixes а–д).
3. `iter_records` — groups lines into records by relying on **sequential numbering** (`BibItem` handles suffixes and ranges for ordering). Unnumbered lines and lines whose number is lower than the current item are appended to the current record. A jump larger than `k` (default 101) is treated as an accidental number inside text (a year, print run); a smaller gap emits placeholder records with `tail = 'MISSING'` for the skipped numbers.
4. `extract_title_author` — splits the record text into `title`, `author`, `alt_title`, `in`, `tail` using the `AUTHOR_KEY` regex (author surnames are in ALL CAPS in the source) and `TITLE_AUX` (`В кн.:`, `Изд. также под загл.`, `На тит. л. загл.`, `Загл. обл.`). Fallback: initials-only author. Otherwise `title = 'NOPARSE'`.
   - **Manual override:** if a record in the txt contains `#`, everything before it is the title and everything after is the author (may be empty). An `@` after the author ends it; what follows is matched against `TITLE_AUX` (→ `in`/`alt_title`) or goes to `tail`. Without `@`, a trailing `TITLE_AUX` phrase is still split off. Insert `#` into the txt to fix records the regex can't split.

5. Post-processing in `main()`: `split_tail_aux` (an alt title / «В кн.:» phrase left in the tail → `alt_title`/`in`), `split_note` (remarks «Ошибочно приписывалось…», «Предполагаемое имя авт.…» → `note`), `normalize_values`; `Record.serialize` collapses whitespace in all fields.

CSV columns: `start,end` (line numbers in `txt/vol_N.txt`), `num`, `title`, `author`, `alt_title`, `in`, `note`, `tail` — see README.md for semantics.

## Other files

- `scripts/ukasatel.py` — separate, standalone parser (pandas/tqdm, stdlib `re`) for volume 7's author index (`УКАЗАТЕЛЬ ИМЕН АВТОРОВ…`), producing `authors_clean.csv`. Hardcodes input path `vol_7.txt` relative to CWD. Not wired into the Makefile.
- `Makefile`'s `sourcefiles` omits `vol_7.txt` (vol 7 is the index volume, not handled by `split_records.py`; it is used as a lexicon by `fix_hyphenation.py`).
- Correction scripts (each logs every change; run on txt, then `make split`): `txt_rules.py RULE` (named regex rules), `fix_author_period.py`, `fix_hyphenation.py` (all volumes at once), `remove_ocr_junk.py`, `backport_csv_edits.py` (one-off: CSV hand edits → txt).
