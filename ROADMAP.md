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

## Next: the core

- **Reading prose out of a draft:** skip fenced code, inline code, tables, `<details>` summaries and the footer; number every sentence (S1, S2, …); grade each one with the Automated Readability Index
- **Config:** the file and per-repo profiles described in [CONFIG.md](CONFIG.md), plus a `first_line_prefix` rule for repos that want posts to start a set way
- **`check`:** the built-in rules (reading grade with `--post`, template lines exempt, commit shas in backticks, links in backticks, blank lines in `<details>`, SPDX licence ids, `@` mentions outside code, a TL;DR on long posts with its word threshold and sentence cap from config, the footer, banned phrases, private paths such as a home folder), printing only the problems
- **Outside checkers:** `lines` mode (a command and a fail regex) and `json` mode (Vale first)
- **`set`:** replace one sentence by its id, behind two guards a rewrite must pass: it keeps every number, commit sha and inline-code span of the old sentence, and a sentence under a heading listed in `keep_negation` (a "Not run" list, say) keeps its negation, so a step that never ran can't be reworded into one that did
- **`fix`:** safe mechanical edits shown as a diff, written only with `--write`, idempotent, never touching code, quotes, tables, link text or the footer. One opt-in exception to the quotes rule, per repo: `code_names` turns a quoted test name, a listed CI check name or a CI state (`passed`, `failed`, `skipped`) into inline code
- **`split`:** suggest where long sentences can break, only when both halves read easier
- **Tests:** made-up drafts only, plus a timing test: a 262 KB draft, GitHub's comment ceiling, checked in under 1 second

## Later

- **Borrowed word lists,** each kept beside its licence with a NOTICE: proselint (BSD-3-Clause) for redundancy, hedging, weasel words, clichés and jargon; write-good (MIT) for weasel words, a leading "So", "there is/are" and wordy phrases; AI-tell phrase lists (MIT). Only one-to-one replacement pairs may be applied by `fix`; the rest are flags.
- **Harper** (Apache-2.0) as an optional grammar and spelling checker through `harper-cli`, pinned to a version; `fix` applies only the kinds of suggestion a config allows. hunspell is the fallback for spelling.
- **A measuring-only experiment** with a tiny local editing model (CoEdIT-small or CoEdIT-base, Apache-2.0, run on the CPU): does it shorten hard sentences without losing code, numbers, issue refs or commit shas? Nothing gets wired in unless the numbers are good.

## Ideas, not decided

- a length rule: fail a body over GitHub's 65,536-character limit, or a comment over its byte limit, before it is posted

## Not planned

- other platforms: Discord, chat, email
- anything that posts for you
- network features
