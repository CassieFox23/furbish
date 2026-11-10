# Changelog

Format after [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- The repo base: docs, CI, and a stub CLI that answers `--help` and `--version`. No checks work yet.
- The prose reader (`read_prose`): reads the sentences out of a draft, numbers them S1, S2, …, and grades each with the Automated Readability Index. It skips fenced code, comments, tables, `<details>` summaries and the footer, and it stays fast on hostile text. `check` uses it.
- The config loader (`find_config`, `load_config`, `pick_profile`): finds the file in the order `CONFIG.md` describes, checks every key and value, and reports a mistake with the file's path and the key at fault instead of crashing. `check` reads it.
- `furbish check DRAFT [--repo owner/name] [--post]`: prints only the problems in a draft, one per line as `path:line: message` with the sentence id where one applies, and nothing when it passes. Exits 0 on a pass, 1 on problems and 2 when it cannot run. Rules: reading grade (with `--post`, where a sentence at grade 10 or more is too hard), the `first_line_prefix`, commit shas and URLs in backticks, blank lines in `<details>`, informal licence names, `@` mentions, the TL;DR, the footer, banned phrases and private text. A 262 KB draft checks in well under a second.
- Outside checkers: `check` runs each `external` entry from the profile (`run_external`) after its own rules. `lines` mode reports the output lines that match a regex; `json` mode reads Vale's `--output=JSON`. The draft's path is the last argument, nothing runs through a shell, a checker is stopped after 60 seconds, and a checker that can't do its job ends the run with exit 2. Printed text has control characters replaced.
- `furbish set DRAFT ID TEXT [--repo owner/name] [--write]`: replaces one sentence by the id `check` prints, at its exact place in the file. The new sentence must keep every number, commit sha and inline-code span of the old one, and a sentence under a `keep_negation` heading must keep its negation; the change is also refused if the sentences around it would no longer read the same. It prints a diff, and writes the file only with `--write`, keeping its line endings and mode. Exits 0 when done, 1 when refused and 2 when it cannot run.

### Changed

- The prose reader is faster on drafts of many short lines: about 40% on a 260 KB draft of one-word lines, measured on one machine.
