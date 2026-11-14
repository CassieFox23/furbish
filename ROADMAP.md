# Roadmap

This file lists what furbish does, what it gets wrong or doesn't do yet, and what is not coming. What changed, and when, is in [CHANGELOG.md](CHANGELOG.md). Dates are not promised. This is a personal tool.

## Aims

furbish tidies GitHub pull request and issue text before it is posted. It is built to:

- use the Python standard library only
- do the job with scripts first; a model is optional and small
- never touch the network
- stay quiet: nothing printed on a pass

## Rules for anything new

- a test on a made-up draft, never a real post
- a 262 KB draft, GitHub's comment ceiling, still checks in under 1 second
- anything furbish prints makes sense to someone who has never seen it
- a word list comes with its licence, read before anything is copied

## Done

The detail of each piece is in [CHANGELOG.md](CHANGELOG.md).

- [x] The reader: finds the sentences in a draft the way GitHub reads it, skipping code, comments, tables, fold titles and the footer, and numbers them S1, S2 and so on. Every command reads a draft the same way.
- [x] Config: rules per repo, and per kind of post inside a repo, in one file ([CONFIG.md](CONFIG.md)). A mistake names the file and the setting.
- [x] `check`: prints only the problems. It covers length, reading grade, shas and links in backticks, blank lines in folds, loose licence names, @ mentions, the TL;DR, the footer, and banned or private words.
- [x] Outside checkers: Vale, Harper, or any tool that prints one problem per line. Each is stopped after 60 seconds or 64 MB of output.
- [x] `set`: swaps one sentence by its id, and refuses a rewrite that drops a number, sha, code or a "not" that has to stay.
- [x] `fix`: only safe, mechanical edits, shown first and written only with `--write`. A second run changes nothing.
- [x] `split`: suggests where a hard sentence could be cut in two.
- [x] Word lists from proselint, write-good, GNU diction and vale-ai-tells, off unless a profile turns them on.
- [x] Harper's grammar checks, with only the fixes a profile allows.
- [x] Tests on made-up drafts, with a timing test for each command. Every command was read blind by another model, and the whole project once by a stronger one.

## Known gaps

Things furbish gets wrong or doesn't check yet. None of them crashes or loses text.

- [ ] Text straight after `</details>` with no blank line shows as raw Markdown on GitHub, and nothing checks for it.
- [ ] A fold with no `<summary>` shows its body as raw Markdown on GitHub, and nothing checks for it.
- [ ] An empty fold (a summary and nothing else) is asked for a blank line it doesn't need.
- [ ] A fold inside a quote is flagged even when its `>` line is blank, and `fix` can't clear it.
- [ ] A `<pre>`, `<script>`, `<style>` or `<textarea>` block is only seen when it starts at the left margin. In a list item or a quote, the fold rule still asks for a blank line inside it, where GitHub would show it as an empty line.
- [ ] A fold, then a `<script>` holding `<!--`, then a second fold: `fix` needs two runs to finish.
- [ ] The licence rule reads names inside links and file names (`COPYING.GPLv3`), and takes "Apache 2.4", the web server, for the Apache 2.0 licence.
- [ ] Speed: on the worst made-up drafts found, `set` takes about 0.75 s and `split` about 0.6 s on a fast desktop, against 0.17 s for a normal 262 KB draft (hyperfine, 14 Nov 2026). GitHub's CI runners are about twice as slow. No single slow spot was found.

## Ideas, not decided

- A small local model to reword hard sentences. CoEdIT-small and CoEdIT-base were measured on 14 Nov 2026 on 50 made-up hard sentences. They dropped the backticks from every bit of code, lowered the reading grade by only 0.5 to 1.2, and got at most 1 sentence under grade 10 with everything kept. Not good enough to use; `split`, `set` and a person stay the way to fix a hard sentence.

## Not coming

- Discord, chat or email. furbish is for GitHub posts only.
- Posting anything for you.
- Anything that needs the network.
