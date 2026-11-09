#!/usr/bin/env python3
import argparse, sys

__version__ = "0.1.0.dev0"

PLANNED = """planned commands, not working yet:
  check DRAFT            planned: print only the problems, with line and sentence id
  fix DRAFT [--write]    planned: safe mechanical edits, shown as a diff unless --write
  set DRAFT S12 "text"   planned: replace one sentence by its id
  split DRAFT            planned: suggest where to split long sentences"""


def main():
    argv = sys.argv[1:]
    ap = argparse.ArgumentParser(prog="furbish", description="Checks and tidies GitHub PR and issue drafts before they're posted: plain words, house rules, safe fixes. Script-first and offline.", epilog=PLANNED, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"furbish {__version__}")
    if not argv:
        ap.print_help(sys.stderr)
        return 2
    ap.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
