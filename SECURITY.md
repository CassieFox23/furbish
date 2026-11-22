# Security

## Reporting a problem

Use the private report form: this repository's **Security** tab, then **Report a vulnerability**. Only the maintainer can read it. Please don't open a public issue for a security problem.

What counts:

- furbish runs, fetches or opens anything a draft names
- furbish makes any network request, or sends a draft or its config anywhere
- a crafted draft or config makes furbish write a file it wasn't asked to write, or print something that fools the terminal
- furbish changes a draft without `--write`, changes text outside the one thing `set` was asked to change, or `fix` changes code, a comment, a table, a quote, link text or the footer

A draft that furbish passes but shouldn't is a missed rule, not a vulnerability. Open a normal issue for that, with a made-up draft that shows the problem.

## What to expect

This is a hobby project kept by one person. A first reply usually comes within a week. Only the latest commit on `main` is supported.
