<p align="center"><img src="docs/wordmark.png" alt="furbish" width="492"></p>

Checks and tidies GitHub PR and issue drafts before they're posted: plain words, house rules, safe fixes. Script-first and offline.

> [!IMPORTANT]
> **Status: early.** `check`, `set`, `fix`, `split`, `--help` and `--version` all work, and so do the borrowed word lists. The optional grammar checker on the [roadmap](ROADMAP.md) doesn't exist yet.

## What it does

- `furbish check DRAFT [--repo owner/name] [--kind NAME] [--post] [--text]`: prints only the problems, with the line and sentence id (like S12). Silent on a pass. A draft over GitHub's limit of 65,536 characters fails. Exit 0 pass, 1 problems found, 2 could not run. Reading-grade checks run only with `--post`. It needs no config, but the footer, TL;DR, banned phrases, private text, word lists and first-line rules come from [your config](CONFIG.md), which can also name outside checkers such as Vale to run on the draft. `--kind NAME` picks a kind inside the repo profile, for another type of post with its own rules (see CONFIG.md).
- `furbish fix DRAFT [--repo owner/name] [--kind NAME] [--write]`: safe mechanical edits, shown as a diff unless `--write`. It takes the backticks off a commit sha or URL that sits alone in them, puts the blank lines GitHub needs inside `<details>`, and, if your config turns on `code_names`, puts quoted test names, CI check names and CI states in inline code, and with `word_swaps` makes the one-for-one swaps from your word lists, such as "in order to" to "to". It never touches code blocks, comments, tables, quotes, link text, headings, checkboxes, template lines or the footer, and a second run changes nothing. A paragraph that holds something furbish can't read safely (a stray backtick, a table row, a link or quote that runs over several lines, indented code, a comment on one of its lines) is left alone whole. Exit 0 done (and silent when there is nothing to fix), 1 refused, 2 could not run.
- `furbish set DRAFT S12 "text" [--repo owner/name] [--kind NAME] [--write]`: replaces one sentence by its id, the id `check` prints. The new sentence must keep every number, commit sha and inline-code span of the old one, and under a heading your config lists in `keep_negation` it must keep its negation, so a step that never ran can't be reworded into one that did. It shows the change as a diff and writes the file only with `--write`. Exit 0 done, 1 refused, 2 could not run.
- `furbish split DRAFT [--repo owner/name] [--kind NAME]`: for each sentence that reads at grade 10 or harder, suggests where to cut it in two, but only when both halves read easier. It cuts at a semicolon, a spaced dash, or a comma before and, but, so, or or yet, never inside code, links, URLs or quotes, never inside a bracket or emphasis left open, and never in a sentence where a quote starts or ends outside it. It only suggests and never changes the draft; apply a suggestion with `set`. Silent when it has nothing to suggest. Exit 0, or 2 when it could not run.

It covers GitHub pull request and issue text only: comments, reviews, and bodies. Not Discord, chat or email. Rules come from your own config, so nothing about one project is built in. It never touches the network.

## Needs

- Python 3.11 or newer, standard library only
- Optional outside programs (hunspell, vale, harper-cli), run only if your config names them

## Install

Nothing to install yet. Clone the repo and run `furbish.py` with Python 3:

```bash
git clone https://github.com/CassieFox23/furbish.git
cd furbish
```

## Use

`check` reads a draft file and prints one line per problem. It prints nothing when the draft passes:

```bash
python3 furbish.py check draft.md
```

```
draft.md:3: @someone is an @ mention, which pings that person
draft.md:5: c1217e711 is a commit sha in backticks; write it bare, because GitHub only links a bare sha
```

Add `--post` just before a post goes up to grade the reading level too, `--text` to print each flagged sentence under its problem, and `--repo owner/name` to pick a profile from your [config](CONFIG.md). `--help` and `--version` work too.

`split` prints the id of a hard sentence and the two sentences it would make:

```bash
python3 furbish.py split draft.md
```

```
draft.md:5: S3: reading grade 15. As two sentences it would read at grade 9 and 5:
    The loader reads every key and reports each mistake with the path of the file.
    And the command line prints only the problems that it finds in the draft.
```

`fix` shows what it would change in the same way, and changes the file only with `--write`:

```bash
python3 furbish.py fix draft.md
python3 furbish.py fix draft.md --write
```

```
--- draft.md
+++ draft.md
@@ -4,1 +4,1 @@
-Fixed in `c1217e711`.
+Fixed in c1217e711.
```

`set` changes one sentence. Without `--write` it only shows what would change:

```bash
python3 furbish.py set draft.md S2 "It took 12 seconds."
python3 furbish.py set draft.md S2 "It took 12 seconds." --write
```

```
--- draft.md
+++ draft.md
@@ -3,1 +3,1 @@
-It took 12 s and it was slow.
+It took 12 seconds.
```

The new text must be one plain line: no tabs, hidden characters or comments. A sentence that wraps over several lines becomes one line, and `set` refuses a sentence it can't change without losing something in front of it, such as a list marker. With `--write` it also refuses a read-only draft and a draft with more than one name (a hard link), and a draft that is a symlink is changed where the link points. A refusal prints one line per reason, like `draft.md:3: S2: the new sentence drops the number 12`, and writes nothing. If the new text starts with a dash, put `--` before it, and put any option such as `--write` before the `--`: `furbish set draft.md S2 --write -- "-odd one."`.

## Help

Questions and bug reports go in [GitHub issues](https://github.com/CassieFox23/furbish/issues).

## Contributing

- Issues and pull requests: [CONTRIBUTING.md](CONTRIBUTING.md)
- AI tools are fine when you say so: [AI_POLICY.md](AI_POLICY.md)

## Licence

GPL-3.0-only. Copyright Cassie_Fox. See [LICENSE](LICENSE).
