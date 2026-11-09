# Privacy

furbish has no network, no telemetry and no logs. It reads what you give it and writes only what you ask it to. This page lists what it reads and writes, so you can check it yourself.

## What it reads

- the draft you name on the command line
- your config: `$FURBISH_CONFIG`, else `$XDG_CONFIG_HOME/furbish/config.toml`, else `~/.config/furbish/config.toml`
- its own `data/` folder (planned word lists)
- an outside checker, only if your config names it. It is a program on your machine and does whatever that program does.

## What it writes

- only the draft, and only with `--write`
- nothing else: no cache, no log file, no record of the drafts it checked

## Turning it down

Nothing needs a key, an account or a connection. furbish itself never sends a draft or its config anywhere.
