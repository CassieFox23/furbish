# Roadmap

What is planned, in order, and what is not coming. Finished work is in [CHANGELOG.md](CHANGELOG.md). Dates are not promised. This is a hobby project.

## Aims

- standard library only
- script first
- no network
- quiet output: nothing on a pass
- any model optional and tiny

## Done

- the repo base: docs, CI on Python 3.11 to 3.14, and a stub that answers `--help` and `--version`
- the prose reader: `read_prose` skips code, comments, tables, `<details>` summaries and the footer, numbers every sentence (S1, S2, …) and grades each with the Automated Readability Index. `check` uses it
- the config loader: `find_config`, `load_config` and `pick_profile` read and check the file and per-repo profiles described in [CONFIG.md](CONFIG.md), and report a mistake with the file's path and the key at fault. `check` reads it
- **`check`:** `furbish check DRAFT [--repo owner/name] [--post]` prints only the problems, one per line with its line number and sentence id, and nothing on a pass. The built-in rules: reading grade with `--post` (grade 10 or more is too hard; headings, checkboxes, template lines and sentences under three words are exempt), the `first_line_prefix`, commit shas in backticks, URLs in backticks, blank lines in `<details>`, informal licence names instead of SPDX ids, `@` mentions outside code, a TL;DR on long posts with its word threshold and sentence cap from config, the footer, banned phrases and private text. A 262 KB draft checks in well under a second
- the outside checkers: `check` runs each `external` entry from the profile after its own rules. `lines` mode reports the output lines matching a fail regex, and `json` mode reads Vale's `--output=JSON`. Both are covered by tests with stand-in checkers, and the real Vale was run through them

## Next: the core

- **`set`:** replace one sentence by its id, behind two guards a rewrite must pass: it keeps every number, commit sha and inline-code span of the old sentence, and a sentence under a heading listed in `keep_negation` (a "Not run" list, say) keeps its negation, so a step that never ran can't be reworded into one that did
- **`fix`:** safe mechanical edits shown as a diff, written only with `--write`, idempotent, never touching code, quotes, tables, link text or the footer. One opt-in exception to the quotes rule, per repo: `code_names` turns a quoted test name, a listed CI check name or a CI state (`passed`, `failed`, `skipped`) into inline code
- **`split`:** suggest where long sentences can break, only when both halves read easier
- **Tests:** made-up drafts only, and a timing test for each command on a 262 KB draft, GitHub's comment ceiling, checked in under 1 second (`check` has its own)

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
