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
- the prose reader: `read_prose` skips fenced and indented code, comments, tables (with or without a leading pipe), `<details>` summaries and the footer, reads a raw HTML block (such as `<div>`, up to the next blank line) the way GitHub does, leaves a footnote's `[^1]:` label out of its sentence, and numbers every sentence (S1, S2, …). Grading is a separate step, `_cleaned` and `_hard`, that `check` and `split` share. `check`, `set`, `fix` and `split` all read a draft through it
- the config loader: `find_config`, `load_config` and `pick_profile` read and check the file and per-repo profiles described in [CONFIG.md](CONFIG.md), and report a mistake with the file's path and the key at fault. `check` reads it
- **`check`:** `furbish check DRAFT [--repo owner/name] [--post] [--text]` prints only the problems, one per line with its line number and sentence id, and nothing on a pass. The built-in rules: length (a draft over 65,536 characters, the limit GitHub's own error message gives, fails on the line where it goes over; whether GitHub counts bytes instead is not checked), reading grade with `--post` (grade 10 or more is too hard; headings of every kind, checkboxes, template lines and sentences under three words, counted by the spaces between them, are exempt), the `first_line_prefix`, commit shas in backticks (an upper-case one is told to go lower case too, since GitHub links only a lower-case sha), URLs in backticks, blank lines in `<details>` (not inside a `<pre>`, `<script>`, `<style>` or `<textarea>` block, which GitHub shows as it is), informal licence names instead of SPDX ids, `@` mentions (after any punctuation; not in code, links, URLs or an email address), a TL;DR on long posts (`**TL;DR:**` or `**TL;DR**:`) with its word threshold and sentence cap from config, the footer, banned phrases and private text. A 262 KB draft checks in well under a second
- the outside checkers: `check` runs each `external` entry from the profile after its own rules. `lines` mode reports the output lines matching a fail regex, `json` mode reads Vale's `--output=JSON`, and `harper` mode reads Harper's. A checker is stopped after 60 seconds or 64 MB of output, along with every program it started. Both modes are covered by tests with stand-in checkers, and the real Vale was run through them
- **`set`:** `furbish set DRAFT S12 "text"` replaces one sentence by the id `check` prints, at its exact place in the file (a wrapped sentence becomes one line, line endings and everything around it are kept). It refuses a rewrite that drops a number, commit sha or inline-code span of the old sentence, or the negation of a sentence under a `keep_negation` heading, or that would change how the rest of the draft reads. It shows a diff and writes only with `--write`, atomically. A 262 KB draft takes about half a second
- **`fix`:** `furbish fix DRAFT` shows the safe mechanical edits as a diff and writes them only with `--write`: the backticks off a lone lower-case commit sha or URL, the blank lines GitHub needs inside `<details>` (again not inside a `<pre>` or the like), and, with `code_names` in the profile, quoted test names, CI check names and CI states as inline code. It never touches code, comments, tables, quotes, raw HTML blocks, link text, headings, checkboxes, template lines or the footer, a second run changes nothing, and it refuses a change that would alter the draft's blocks. Informal licence names are not fixed: `GPLv2` can mean more than one SPDX id, so `check` flags them and a person picks
- **`split`:** `furbish split DRAFT` looks at every sentence that reads at grade 10 or harder and prints where it could be cut in two, only when both halves read at least a whole grade easier. The cuts are a semicolon, a spaced dash, and a comma before and, but, so, or or yet; never inside code, links, URLs, tags or quotes, never with a bracket or emphasis left open, not in a sentence where a quote starts or ends outside it, and not in a sentence over 2,000 characters. It only suggests; `set` applies a suggestion
- **Word lists:** borrowed from proselint (BSD-3-Clause), write-good's too-wordy list (MIT) and vale-ai-tells (MIT), each in its own folder under `data/` beside its licence, with a NOTICE. A profile turns them on by name with `words`; `check` flags what it finds in the prose, and with `word_swaps` `fix` makes the one-for-one swaps, never one near a negation or one that breaks "a" or "an". Lookups are dictionary lookups on the first two words, so the whole `check` command takes about 0.2 to 0.25 s on a 262 KB draft with every list on (hyperfine). Only plain phrases were taken, not regular expressions. write-good's weasel-word list is not included: its licence file was not read
- **Harper** (Apache-2.0), the grammar and spelling checker, through `harper-cli` (tested with 3.2.0) in its own `harper` mode, which reads `harper-cli lint --format json`. `fix` applies only the rules a profile lists in the entry's `fix`, and only where Harper offers one suggestion; hunspell stays the plain spelling fallback through `lines` mode
- **Tests:** made-up drafts only, and a timing test for each command on a 262 KB draft, GitHub's comment ceiling, checked in under 1 second, with hostile floods beside it, and random-draft tests that every command keeps the draft's shape and that `fix` is idempotent
- **Reviews:** each command was read blind by another model, and the whole project once by a stronger one. Every finding was reproduced before it was fixed and is pinned by a test. The last round found that the readers had drifted apart, so there is now one reader and one grader for every command

## Known gaps

Things furbish does not do yet, or does in a way a person might not expect. None is a crash or a way to lose text.

- **`<pre>` in a list item or a quote:** the details rule knows a `<pre>`, `<script>`, `<style>` or `<textarea>` block only when it starts at the left margin. Inside a list item or a quote, `check` still asks for blank lines around a `<details>` summary in one, and in a list item `fix` adds them, where GitHub would show them as empty lines
- **Speed:** `set` reads the draft twice, once to find the sentence and once more to make sure the rest still reads the same, and `split` grades both halves of up to six cuts for each hard sentence. Timed with hyperfine on a Ryzen 9 5900X, the whole command takes about 0.75 s for the worst hostile draft found for `set` (52,000 one-word lines) and 0.6 s for `split` (200 long sentences full of places to cut), against 0.17 s for a realistic 262 KB draft. GitHub's CI runners are about twice as slow. A profile found no one slow spot: the time is spread over the shared reader and grader, and the second read is the guard

## Later

- **A measuring-only experiment** with a tiny local editing model (CoEdIT-small or CoEdIT-base, Apache-2.0, run on the CPU): does it shorten hard sentences without losing code, numbers, issue refs or commit shas? Nothing gets wired in unless the numbers are good.

## Not planned

- other platforms: Discord, chat, email
- anything that posts for you
- network features
