# Contributing

Issues and pull requests are welcome. This is a hobby project kept by one person, so replies can take a while.

## Issues

- **A wrong flag** (a good line flagged, or a bad one missed): use the "Bug" template and tick "Wrong flag". Use a made-up draft that shows the problem, and paste furbish's full output.
- **A bug** (a crash, a check that never runs): use the "Bug" template.
- **An idea** (a rule, a command or a checker): use the "Idea" template, and check [ROADMAP.md](ROADMAP.md) first.
- **A security problem**: don't open an issue. See [SECURITY.md](SECURITY.md).

## Pull requests

Open an issue first for anything bigger than a small fix, and for anything that changes what a rule flags, so we can agree on the shape before you spend time on it. Keep each change small and focused: one thing per pull request.

A change is ready when:

- furbish still never touches the network, and never runs anything a draft names
- it uses the Python standard library only, Python 3.11 or newer
- any AI help is named in the pull request, as [AI_POLICY.md](AI_POLICY.md) asks
- `python3 -I -m py_compile furbish.py` passes, and `python3 -I -m unittest discover -s tests -v` passes, with the tests run before merge
- a new check gets a test in `tests/`, on a made-up draft

Some pull requests won't fit. When that happens you'll get a no with a reason, not silence. A pause is fine too.

By contributing you agree your work is released under the GPL-3.0, the same as the rest of the project.

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).
