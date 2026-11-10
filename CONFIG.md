# Configuring furbish

Planned: furbish doesn't read a config file yet. This is the shape it will have. The key names may still change.

furbish looks for the file in this order: `$FURBISH_CONFIG`, then `$XDG_CONFIG_HOME/furbish/config.toml`, then `~/.config/furbish/config.toml`.

Each target repo has its own profile, `[repo."owner/name"]`. Pick one with `--repo owner/name`, or set `default_repo` to use it every time. The example uses made-up names:

```toml
default_repo = "example-org/example"

[repo."example-org/example"]
pr_template = "/path/to/example/pull_request_template.md"
issue_template = "/path/to/example/issue_template.md"
footer = "^-- Sent from the made-up example footer$"
tldr = "required"
tldr_words = 100
tldr_max_sentences = 3
banned = ["circle back", "synergy"]
private = ["/home/", "/Users/", "example-hostname"]
keep_negation = ["Not run"]

[repo."example-org/example".code_names]
quoted_tests = true
checks = ["Example lint", "Example unit tests"]
states = ["passed", "failed", "skipped"]

[[repo."example-org/example".external]]
name = "example-lines"
mode = "lines"
command = ["example-checker", "--plain"]
fail = "^FAIL"

[[repo."example-org/example".external]]
name = "example-json"
mode = "json"
command = ["example-json-checker"]
```

What each part is for:

- `pr_template` and `issue_template` hold the repo's templates. Their lines are exempt from grading.
- `footer` is a regex for the footer line. `fix` never touches it.
- `tldr` sets the TL;DR rule for the repo. `tldr_words` is the length in words from which a post needs one, and `tldr_max_sentences` caps it.
- `banned` lists phrases to flag.
- `private` lists strings that must never reach a post, such as a home folder path or a machine name. `check` fails a draft that holds one.
- `keep_negation` names headings whose sentences must stay negative: `set` refuses a rewrite of a sentence under one of them that drops its negation.
- `code_names` is the one opt-in exception to `fix` leaving quotes alone. With `quoted_tests`, a quoted test name becomes inline code; names in `checks` and words in `states` become inline code wherever they appear in prose.
- `external` names outside checkers. In `lines` mode, a line of the command's output that matches `fail` counts as a problem. `json` mode is for checkers like Vale and Harper.

furbish runs only the commands named in this file, never anything a draft names.
