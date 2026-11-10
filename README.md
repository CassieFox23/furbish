# furbish

Checks and tidies GitHub PR and issue drafts before they're posted: plain words, house rules, safe fixes. Script-first and offline.

> [!IMPORTANT]
> **Status: early, being built.** `check`, `set`, `--help` and `--version` work today. Everything marked planned below doesn't run yet.

## What it does

- `furbish check DRAFT [--repo owner/name] [--post]`: prints only the problems, with the line and sentence id (like S12). Silent on a pass. Exit 0 pass, 1 problems found, 2 could not run. Reading-grade checks run only with `--post`. It needs no config, but the footer, TL;DR, banned phrases, private text and first-line rules come from [your config](CONFIG.md), which can also name outside checkers such as Vale to run on the draft.
- `furbish fix DRAFT [--write]` (planned): safe mechanical edits, shown as a diff unless `--write`. Never touches code, quotes, tables or the footer.
- `furbish set DRAFT S12 "text" [--repo owner/name] [--write]`: replaces one sentence by its id, the id `check` prints. The new sentence must keep every number, commit sha and inline-code span of the old one, and under a heading your config lists in `keep_negation` it must keep its negation, so a step that never ran can't be reworded into one that did. It shows the change as a diff and writes the file only with `--write`. Exit 0 done, 1 refused, 2 could not run.
- `furbish split DRAFT` (planned): suggests where to split long sentences.

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

Add `--post` just before a post goes up to grade the reading level too, and `--repo owner/name` to pick a profile from your [config](CONFIG.md). `--help` and `--version` work too.

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

A sentence that wraps over several lines becomes one line. A refusal prints one line per reason, like `draft.md:3: S2: the new sentence drops the number 12`, and writes nothing. If the new text starts with a dash, put `--` before it.

## Help

Questions and bug reports go in [GitHub issues](https://github.com/CassieFox23/furbish/issues).

## Contributing

- Issues and pull requests: [CONTRIBUTING.md](CONTRIBUTING.md)
- AI tools are fine when you say so: [AI_POLICY.md](AI_POLICY.md)

## Licence

GPL-3.0-only. Copyright Cassie_Fox. See [LICENSE](LICENSE).
