<p align="center"><img src="docs/wordmark.png" alt="furbish" width="492"></p>

furbish reads a GitHub pull request or issue draft before you post it. It tells you what to fix, and it can make the safe fixes for you. furbish itself never goes online.

> [!IMPORTANT]
> **Early days.** Everything below works, but names and options may still change. What's next is in the [roadmap](ROADMAP.md).

## What it does

furbish has four commands. Each one reads a draft saved as a Markdown file.

| Command | What it does |
|---|---|
| `check` | Lists the problems in a draft, one per line. Prints nothing if there are none. |
| `fix` | Shows the safe fixes it can make, and makes them when you add `--write`. |
| `split` | Points at hard sentences and shows where each could be cut in two. |
| `set` | Swaps one sentence for wording you give it, and refuses if a number, commit id or bit of code would go missing. |

A typical run: `check`, then `fix`, then `check --post` and `split` just before you post, using `set` for any sentence you reword.

With no config at all, `check` looks for:

- a draft longer than GitHub allows (65,536 characters)
- @ mentions, which ping people
- a commit id (sha) or a web address inside backticks, where GitHub won't turn it into a link
- a collapsed `<details>` section missing the blank line GitHub needs after its summary
- a loose GPL, Apache or BSD licence name, like `Apache 2.0` where the standard SPDX id is `Apache-2.0`
- with `--post`, sentences that read at grade 10 or harder

The grade is worked out from word and sentence length, and it's roughly the school year a reader needs (the Automated Readability Index). Headings, checkboxes and sentences under three words are left out.

## Config

The config is optional. It's a TOML file, usually `~/.config/furbish/config.toml`, with a set of rules for each repo:

- a footer, or a TL;DR line at the top
- words that must never appear, and private text such as your home folder
- word lists that flag wordy phrases, vague words, clichés and words that sound AI-written
- outside checkers: Vale (a style checker), Harper (a grammar checker) or hunspell (a spell checker), which run as their own programs

[CONFIG.md](CONFIG.md) has the details. Every command takes `--repo owner/name` to pick a repo's rules, and `--kind NAME` for a set of rules inside it, such as one for release notes.

## Getting it

You need Python 3.11 or newer, and nothing else unless your config names an outside checker. Download the repo and run the file with Python, keeping it beside its `data/` folder:

```bash
git clone https://github.com/CassieFox23/furbish.git
cd furbish
python3 furbish.py --help
```

It only handles GitHub pull requests and issues: their bodies, comments and reviews. Not Discord, chat or email.

## Using it

### check

```bash
python3 furbish.py check draft.md
```

```
draft.md:3: @someone is an @ mention, which pings that person
draft.md:5: c1217e711 is a commit sha in backticks; write it bare, because GitHub only links a bare sha
```

Each line gives the file, the line number and the problem. Add `--post` just before you post, to grade each sentence too. Those lines also give the sentence's number, like `S1`, which `set` uses:

```
draft.md:1: S1: the reading grade is 13, which is too hard; every sentence should be under grade 10
```

Add `--text` to print the sentence itself under each problem that has one.

### fix

`fix` shows what it would change. Nothing is saved until you add `--write`, and it keeps no backup, so commit or copy the draft first:

```bash
python3 furbish.py fix draft.md
python3 furbish.py fix draft.md --write
```

```
--- draft.md
+++ draft.md
@@ -4,3 +4,3 @@
 
-Fixed in `c1217e711`.
+Fixed in c1217e711.
 
```

Lines starting with `-` are the old text and `+` the new. Without `--write` it also says that nothing was written.

On its own it does two things. It takes the backticks off a lone commit id (in lower case) or web address, and it adds the blank line GitHub needs after a `<details>` summary. Your config can ask for more:

- test names, CI check names and CI results such as `passed`, put in code formatting
- a wordy phrase swapped for a shorter one, such as "exact same" to "same"
- the Harper fixes you allow

It leaves code, comments, tables, quoted text, link text, headings, checkboxes, your template's lines and the footer alone. The one exception: with quoted test names turned on, `"test_open_file"` becomes code. It also skips a paragraph it can't read safely, such as one with a stray backtick, a table row or a comment in it. If an edit would change how the draft is laid out, it changes nothing at all. A second run finds nothing more to do, except that Harper may spot something new in the fixed text.

### split

```bash
python3 furbish.py split draft.md
```

```
draft.md:1: S1: reading grade 13. As two sentences it would read at grade 6 and 5:
    The loader reads every key and reports each mistake with the path of the file.
    And the command line prints only the problems that it finds in the draft.
```

It cuts only at a semicolon, a dash with spaces around it, or a comma before "and", "but", "so", "or" or "yet". It never cuts inside code, links or quotes, and only cuts when both halves read easier. It never changes the file. To take a suggestion, give `set` the sentence number and both new sentences in one quoted string.

### set

Sentences are numbered from the top, S1, S2 and so on, leaving out code, tables and the like. `check --post` and `split` print the number of each sentence they flag.

```bash
python3 furbish.py set draft.md S4 "It took 12 seconds."
python3 furbish.py set draft.md S4 "It took 12 seconds." --write
```

```
--- draft.md
+++ draft.md
@@ -7,1 +7,1 @@
-It took 12 s and it was slow.
+It took 12 seconds.
```

The new wording has to keep every number, commit id and bit of code from the old sentence. If it doesn't, `set` says why and saves nothing:

```
draft.md:7: S4: the new sentence drops the number 12
```

Your config can mark some headings with `keep_negation`. Under one, a sentence that says no must keep saying it, so "the test did not run" can't become "the test ran". The new text goes on one line. If it starts with a dash and has no spaces, like `-O2.`, put `--` before it, after any options: `python3 furbish.py set draft.md S2 --write -- "-O2."`. A `set` that makes two sentences moves the numbers after it, so run `check` again before the next one.

## Exit codes

| Code | Means |
|---|---|
| 0 | all good, or done |
| 1 | `check` found problems, or `fix` or `set` refused a change |
| 2 | furbish couldn't run: a mistake in the config, a missing file or a sentence number that isn't there |

## Help

Questions and bug reports go in [GitHub issues](https://github.com/CassieFox23/furbish/issues). Security problems don't: see [SECURITY.md](SECURITY.md).

## Contributing

- How issues and pull requests work: [CONTRIBUTING.md](CONTRIBUTING.md)
- AI tools are fine if you say you used them: [AI_POLICY.md](AI_POLICY.md)

## Licence

GPL-3.0-only. Copyright Cassie_Fox. See [LICENSE](LICENSE).
