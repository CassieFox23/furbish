# Working on furbish

Read this before changing anything; the README says what the program is.

## Layout

The whole program is one file, `furbish.py`. It uses the Python standard library only.

| Part | Holds |
|---|---|
| `furbish.py` | the command line (`check`, `set`, `fix`, `split`, `--help` and `--version`), the prose reader (`read_prose`, `ari`, and `_sentences`, which also says where each sentence sits in the file), the config loader (`find_config`, `load_config`, `pick_profile`), the outside-checker runner (`run_external`, and `harper_edits` for the Harper fixes `fix` makes) and the `set` guards (`set_sentence`) the `fix` edits (`fix_text`) and the `split` suggestions (`split_suggestions`) |
| `tests/` | offline unit tests, on made-up drafts only; the drafts are in `tests/drafts/` |
| `data/` | word lists borrowed from proselint (BSD-3-Clause), write-good's too-wordy and weasel-words lists (MIT), GNU diction (GPL-3.0-or-later) and vale-ai-tells (MIT), each in its own folder as `words.tsv` beside its upstream licence; `data/NOTICE` says where each came from |

## Rules

1. **GitHub posts only.** furbish checks GitHub pull request and issue text: comments, reviews, PR and issue bodies. Not Discord, chat or email.
2. **Drafts are hostile.** A draft is untrusted text. furbish never runs, fetches or opens anything a draft names. It runs only the commands the user's own config names.
3. **Never the network.** furbish reads the draft, the config and its own `data/`. It writes only with `--write`, and it never sends anything.
4. **Standard library only.** Python 3.11 or newer, for tomllib. The only outside programs are the optional ones a user's config names (hunspell, vale, harper-cli).
5. **Speed.** Word lists are set or dict lookups, never one giant alternation regex. A 262 KB draft, GitHub's comment ceiling, must check in under 1 second (`check` has its timing test; each new command gets one).
6. **Synthetic fixtures only.** Test drafts are made up. Never a real person's post, and never a copy of one.
7. **No personal details.** No personal paths, usernames, hostnames or email addresses anywhere in the tree, in a commit message or in a commit's author or committer address.
8. **Style.** Match the file: no comments, no docstrings. The why of a change goes in the commit message.
9. **Commits.** One per piece of work, staged by named path, message says what and why. Never push.
10. **A human owner.** Every change belongs to a named person who answers for it ([AI_POLICY.md](AI_POLICY.md)). Leave the pull request template's "Human owner" part for them, and never tick it yourself.
11. **Plain for everyone.** Anything furbish prints should make sense to someone who has never seen it. Say what to do in plain words, spell keys out, and skip jargon.

## Checking your work

```sh
python3 -I -m py_compile furbish.py
python3 -I -m unittest discover -s tests -v
```
