# furbish

Checks and tidies GitHub PR and issue drafts before they're posted: plain words, house rules, safe fixes. Script-first and offline.

> [!IMPORTANT]
> **Status: early, being built.** Only `--help` and `--version` work today. Everything marked planned below doesn't run yet.

## What it will do

- `furbish check DRAFT` (planned): prints only the problems, with the line and sentence id (like S12). Silent on a pass. Exit 0 pass, 1 fail, 2 usage error. Reading-grade checks run only with `--post`.
- `furbish fix DRAFT [--write]` (planned): safe mechanical edits, shown as a diff unless `--write`. Never touches code, quotes, tables or the footer.
- `furbish set DRAFT S12 "text"` (planned): replaces one sentence by its id.
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

Only `--help` and `--version` work today:

```bash
python3 furbish.py --version
```

```
furbish 0.1.0.dev0
```

## Help

Questions and bug reports go in [GitHub issues](https://github.com/CassieFox23/furbish/issues).

## Contributing

- Issues and pull requests: [CONTRIBUTING.md](CONTRIBUTING.md)
- AI tools are fine when you say so: [AI_POLICY.md](AI_POLICY.md)

## Licence

GPL-3.0-only. Copyright Cassie_Fox. See [LICENSE](LICENSE).
