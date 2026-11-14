# Configuring furbish

`furbish check` reads and checks this file. The key names may still change. A mistake in the file, such as a misspelt key or a regex that doesn't compile, is reported with the file's path and the key at fault, and nothing runs until it's fixed.

furbish looks for the file in this order: `$FURBISH_CONFIG`, then `$XDG_CONFIG_HOME/furbish/config.toml`, then `~/.config/furbish/config.toml`.

Each target repo has its own profile, `[repo."owner/name"]`. Pick one with `--repo owner/name`, or set `default_repo` to use it every time. The example uses made-up names:

```toml
default_repo = "example-org/example"

[repo."example-org/example"]
pr_template = "/path/to/example/pull_request_template.md"
issue_template = "/path/to/example/issue_template.md"
first_line_prefix = "Example:"
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

- `pr_template` and `issue_template` hold the repo's templates. Their lines are exempt from grading. A leading `~` means your home folder. A repo that uses GitHub issue forms (YAML files) needs no `issue_template`: the field labels and checkboxes a form produces appear in a posted issue as `###` headings and `- [x]` items, which are already exempt.
- `first_line_prefix` is the text a post must start with, for repos that want posts to open a set way.
- `first_line_skip` is a regex for a whole first line that comes before the TL;DR, such as a line of badges. When the first non-blank line matches it, the TL;DR rule reads the next non-blank line instead.
- `footer` is a regex for the footer line. `fix` never touches it.
- `tldr` is `"required"` or `"off"` (the default). `tldr_words` is the length in words from which a post needs a TL;DR line first, written `**TL;DR:**` or `**TL;DR**:`, and `tldr_max_sentences` caps it. Both are whole numbers of at least 1, and both must be set when `tldr` is `"required"`.
- `banned` lists phrases to flag. They are looked for in the prose only, as whole words and in any case; code, tables and fold summaries are not searched.
- `private` lists strings that must never reach a post, such as a home folder path or a machine name. `check` fails a draft that holds one, and looks at every line, code and tables included.
- `keep_negation` names headings whose sentences must stay negative. `set` refuses a rewrite of a sentence under one of them if the old sentence said no and the new one doesn't. Negation words are not, no, never, none, nothing, nobody, nowhere, neither, nor, cannot, without, and any word ending in n't. A sentence with none of them has no negation to keep. A heading is a line that starts with `#` (up to three spaces of indent) or a line underlined with `===` or `---`; a heading inside a quote or a code block doesn't count. It matches when its text, ignoring case and any `*` or `_` around it, is the entry or starts with it followed by something that is not a letter or digit, so `Not run` also covers `Not run:` and `Not run yet (testing now)`, but not `Not running`. It covers everything under it, down to the next heading of the same or a higher level. `set` also refuses to reword such a heading so that it no longer matches.
- `grade_skip` is a list of regexes for lines the reading grade (`--post`) should leave out, such as a quoted log line. A line whose text matches one anywhere is skipped by the grade check, the same way template lines are. Nothing else changes: `private`, `banned`, the TL;DR, the footer and the other rules still look at that line.
- `code_names` is the one opt-in exception to `fix` leaving quotes alone. With `quoted_tests`, a quoted test name becomes inline code. A quoted name counts as a test name when it is made only of letters, digits, `_`, `.`, `/` and `::`, and either has an underscore or `::` in it or starts with `test` or `Test` and a capital letter or a digit: `"test_open_file"` and `"TestOpen"` do, `"hello"`, `"Testimony"` and `"foo.bar"` don't. Every name in `checks` and `states` must start with a letter or a digit, and furbish says so if one doesn't. Names in `checks` and words in `states` become inline code wherever they appear in plain prose, as whole words in the same case, the longest name first. None of the three touches code, links, URLs, quotes, tables, headings, checkboxes, template lines or the footer.
- `external` names outside checkers. Each needs a unique `name`, a `mode` and a `command`. In `lines` mode, a line of the command's output that matches `fail` counts as a problem, and `fail` is required. `json` mode is for checkers like Vale and Harper, and takes no `fail`.
- `kinds` holds named variants of the repo's profile, for another kind of post in the same repo, such as a release note. Each kind is a table under `kinds`, and it overrides only the keys it names; every other key comes from the repo profile, so `private` still applies to it. Pick one with `--kind NAME`, which needs `--repo` or `default_repo`. A kind name is made only of letters, digits, `-` and `_`, and a kind can't have a `kinds` table of its own. This made-up example turns off the TL;DR rule for release notes only, and skips the grade for lines that start with `Changelog:`:

  ```toml
  [repo."example-org/example".kinds.release]
  tldr = "off"
  grade_skip = ["^Changelog:"]
  ```

How an outside checker is run:

- furbish runs the `command` with the draft's full path added as the last argument. There is no shell, the checker gets no input to wait for, and it is stopped after 60 seconds.
- Exit status 0 and 1 are normal, since linters exit 1 when they find problems. Any other status, a program that can't be started, a timeout or output furbish can't read stops the whole run with a message naming the checker, and `furbish check` exits 2.
- In `lines` mode, every output line that matches `fail` is a problem. A line that starts with the draft's path and a line number, like `/path/draft.md:7:12: text`, is reported at that line; any other matching line is reported without one.
- In `json` mode furbish reads what Vale prints with `--output=JSON`: an object of file paths, each holding a list of alerts with `Line`, `Check` and `Message`. Every alert counts as a problem, so set the level in the command itself, for example Vale's `--minAlertLevel=warning`.
- The checker reads the whole draft file. Template lines are not taken out for it, as they are for the reading-grade check.

Every key is optional. A repo profile with nothing in it is fine: lists are empty, `tldr` is `"off"` and the rest are unset.

furbish runs only the commands named in this file, never anything a draft names.
