# Roadmap

What is done, what is known to be missing, what is planned and what is not coming. What changed, and when, is in [CHANGELOG.md](CHANGELOG.md). Dates are not promised. This is a hobby project.

## Aims

- standard library only
- script first
- no network
- quiet output: nothing on a pass
- any model optional and tiny

## Done

- the repo base: docs, CI on Python 3.11 to 3.14, and a stub that answers `--help` and `--version`
- the prose reader: `read_prose` skips fenced and indented code, comments, tables (with or without a leading pipe), `<details>` summaries and the footer, and numbers every sentence (S1, S2, …). Grading is a separate step, `_cleaned` and `_hard`, that `check` and `split` share. `check`, `set`, `fix` and `split` all read a draft through it
- the config loader: `find_config`, `load_config` and `pick_profile` read and check the file and per-repo profiles described in [CONFIG.md](CONFIG.md), and report a mistake with the file's path and the key at fault. `check` reads it
- **`check`:** `furbish check DRAFT [--repo owner/name] [--post] [--text]` prints only the problems, one per line with its line number and sentence id, and nothing on a pass. The built-in rules: reading grade with `--post` (grade 10 or more is too hard; headings of every kind, checkboxes, template lines and sentences under three words are exempt), the `first_line_prefix`, commit shas in backticks (an upper-case one is told to go lower case too, since GitHub links only a lower-case sha), URLs in backticks, blank lines in `<details>`, informal licence names instead of SPDX ids, `@` mentions (after any punctuation; not in code, links, URLs or an email address), a TL;DR on long posts (`**TL;DR:**` or `**TL;DR**:`) with its word threshold and sentence cap from config, the footer, banned phrases and private text. A 262 KB draft checks in well under a second
- the outside checkers: `check` runs each `external` entry from the profile after its own rules. `lines` mode reports the output lines matching a fail regex, and `json` mode reads Vale's `--output=JSON`. Both are covered by tests with stand-in checkers, and the real Vale was run through them
- **`set`:** `furbish set DRAFT S12 "text"` replaces one sentence by the id `check` prints, at its exact place in the file (a wrapped sentence becomes one line, line endings and everything around it are kept). It refuses a rewrite that drops a number, commit sha or inline-code span of the old sentence, or the negation of a sentence under a `keep_negation` heading, or that would change how the rest of the draft reads. It shows a diff and writes only with `--write`, atomically. A 262 KB draft takes about half a second
- **`fix`:** `furbish fix DRAFT` shows the safe mechanical edits as a diff and writes them only with `--write`: the backticks off a lone lower-case commit sha or URL, the blank lines GitHub needs inside `<details>`, and, with `code_names` in the profile, quoted test names, CI check names and CI states as inline code. It never touches code, comments, tables, quotes, link text, headings, checkboxes, template lines or the footer, a second run changes nothing, and it refuses a change that would alter the draft's blocks. Informal licence names are not fixed: `GPLv2` can mean more than one SPDX id, so `check` flags them and a person picks
- **`split`:** `furbish split DRAFT` looks at every sentence that reads at grade 10 or harder and prints where it could be cut in two, only when both halves read at least a whole grade easier. The cuts are a semicolon, a spaced dash, and a comma before and, but, so, or or yet; never inside code, links, URLs, tags or quotes, never with a bracket or emphasis left open, not in a sentence where a quote starts or ends outside it, and not in a sentence over 2,000 characters. It only suggests; `set` applies a suggestion
- **Tests:** made-up drafts only, and a timing test for each command on a 262 KB draft, GitHub's comment ceiling, checked in under 1 second, with hostile floods beside it, and random-draft tests that every command keeps the draft's shape and that `fix` is idempotent
- **Reviews:** each command was read blind by another model, and the whole project once by a stronger one. Every finding was reproduced before it was fixed and is pinned by a test. The last round found that the readers had drifted apart, so there is now one reader and one grader for every command

## Known gaps

Things furbish does not do yet, or does in a way a person might not expect. None is a crash or a way to lose text.

- **Outside checkers:** a checker's output is held in memory with no size cap, and a timeout stops the checker but not a program it started
- **A task item inside a block quote** is still graded
- **Raw HTML blocks** such as `<div>`: `fix` can put backticks in them, which GitHub shows as plain text. Footnote definitions are read as prose
- **Word counts:** the "under three words" exemption counts whitespace-separated tokens, so a sentence of two words and an ellipsis is graded, while `split` counts only real words
- **Speed:** `set` reads the draft twice (once to find the sentence, once to check the result), and `split` grades each hard sentence again for each cut it tries, so on a slow machine the worst hostile drafts take about a second. A realistic 262 KB draft takes a tenth of that

## Later

- **Borrowed word lists,** each kept beside its licence with a NOTICE: proselint (BSD-3-Clause) for redundancy, hedging, weasel words, clichés and jargon; write-good (MIT) for weasel words, a leading "So", "there is/are" and wordy phrases; AI-tell phrase lists (MIT). Only one-to-one replacement pairs may be applied by `fix`; the rest are flags.
- **Harper** (Apache-2.0) as an optional grammar and spelling checker through `harper-cli`, pinned to a version, once its output format is read (`json` mode reads only Vale's shape today); `fix` applies only the kinds of suggestion a config allows. hunspell is the fallback for spelling.
- **A measuring-only experiment** with a tiny local editing model (CoEdIT-small or CoEdIT-base, Apache-2.0, run on the CPU): does it shorten hard sentences without losing code, numbers, issue refs or commit shas? Nothing gets wired in unless the numbers are good.

## Ideas, not decided

- a length rule: fail a body over GitHub's 65,536-character limit, or a comment over its byte limit, before it is posted

## Not planned

- other platforms: Discord, chat, email
- anything that posts for you
- network features
