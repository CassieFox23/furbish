# Changelog

Format after [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- The repo base: docs, CI, and a stub CLI that answers `--help` and `--version`. No checks work yet.
- The prose reader (`read_prose`): reads the sentences out of a draft, numbers them S1, S2, …, and grades each with the Automated Readability Index. It skips fenced code, comments, tables, `<details>` summaries and the footer, and it stays fast on hostile text. No command shows it yet.
- The config loader (`find_config`, `load_config`, `pick_profile`): finds the file in the order `CONFIG.md` describes, checks every key and value, and reports a mistake with the file's path and the key at fault instead of crashing. No command reads it yet.
