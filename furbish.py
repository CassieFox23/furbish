#!/usr/bin/env python3
import argparse, bisect, re, sys
from collections import namedtuple

__version__ = "0.1.0.dev0"

PLANNED = """planned commands, not working yet:
  check DRAFT            planned: print only the problems, with line and sentence id
  fix DRAFT [--write]    planned: safe mechanical edits, shown as a diff unless --write
  set DRAFT S12 "text"   planned: replace one sentence by its id
  split DRAFT            planned: suggest where to split long sentences"""

Sentence = namedtuple("Sentence", "id line text grade")

_URL = re.compile(r"https?://\S*[^\s.,;:!?)\]\"']")
_TAG = re.compile(r"<[/!A-Za-z][^<>]*>")
_HTML_ONLY = re.compile(r"(?:<[/!A-Za-z][^<>]*>\s*)+")
_HEADING = re.compile(r"(#{1,6})\s")
_LIST = re.compile(r"\s*(?:[-*+]|\d+[.)]) ")
_SPACES = re.compile(r"\s+")
_ABBR = {"e.g.", "i.e.", "vs.", "cf.", "mr.", "mrs.", "ms.", "dr.", "st."}


def _hide(s):
    return "x" * len(s)


def _count(text):
    words = chars = 0
    for tok in text.split():
        n = sum(c.isalnum() for c in tok)
        if n:
            words += 1
            chars += n
    return words, chars


def ari(text):
    words, chars = _count(text)
    if not words:
        return 0.0
    return 4.71 * chars / words + 0.5 * words - 21.43


def _fence_open(line):
    n = len(line) - len(line.lstrip(" "))
    if n > 3:
        return None
    rest = line[n:]
    if not rest or rest[0] not in "`~":
        return None
    c = rest[0]
    k = len(rest) - len(rest.lstrip(c))
    return (c, k) if k >= 3 else None


def _fence_close(line, c, k):
    n = len(line) - len(line.lstrip(" "))
    if n > 3:
        return False
    s = line.strip()
    return len(s) >= k and s == c * len(s)


def _comments(line):
    masked = _edit(line, _code_spans(line), _hide)
    pieces = []
    last = 0
    pos = masked.find("<!--")
    while pos != -1:
        end = masked.find("-->", pos + 4)
        pieces.append(line[last:pos])
        if end == -1:
            return "".join(pieces), True
        last = end + 3
        pos = masked.find("<!--", last)
    pieces.append(line[last:])
    return "".join(pieces), False


def _blocks(lines, footer):
    blocks = []
    cur = None
    fence = None
    comment = False
    summary = False
    for no, line in enumerate(lines, 1):
        if fence:
            if _fence_close(line, *fence):
                fence = None
            cur = None
            continue
        if summary:
            if "</summary>" in line.lower():
                summary = False
            cur = None
            continue
        if comment:
            end = line.find("-->")
            if end == -1:
                cur = None
                continue
            comment = False
            line = line[end + 3:]
        if footer and re.search(footer, line):
            cur = None
            continue
        fo = _fence_open(line)
        if fo:
            fence = fo
            cur = None
            continue
        line, comment = _comments(line)
        hid = _edit(line, _code_spans(line), _hide).lower()
        if "<summary" in hid:
            summary = "</summary>" not in hid
            cur = None
            continue
        stripped = line.strip()
        if not stripped or stripped[0] == "|" or _HTML_ONLY.fullmatch(stripped):
            cur = None
            continue
        hm = _HEADING.match(line)
        if hm:
            blocks.append(["heading", [(no, line[len(hm.group(1)):].strip())]])
            cur = None
            continue
        lm = _LIST.match(line)
        if lm:
            cur = ["list", [(no, line[lm.end():].strip())]]
            blocks.append(cur)
            continue
        if stripped[0] == ">":
            t = stripped.lstrip("> \t")
            if cur and cur[0] == "quote":
                cur[1].append((no, t))
            else:
                cur = ["quote", [(no, t)]]
                blocks.append(cur)
            continue
        if cur:
            cur[1].append((no, stripped))
        else:
            cur = ["para", [(no, stripped)]]
            blocks.append(cur)
    return [parts for _, parts in blocks]


def _code_spans(text):
    runs = [m.span() for m in re.finditer(r"`+", text)]
    by = {}
    for i, (s, e) in enumerate(runs):
        by.setdefault(e - s, []).append(i)
    spans = []
    i = 0
    while i < len(runs):
        lst = by[runs[i][1] - runs[i][0]]
        k = bisect.bisect_right(lst, i)
        if k < len(lst):
            c = lst[k]
            spans.append((runs[i][0], runs[c][1]))
            i = c + 1
        else:
            i += 1
    return spans


def _target_spans(text):
    spans = []
    pos = text.find("](")
    close = -1
    while pos != -1:
        if close < pos + 2:
            close = text.find(")", pos + 2)
            if close == -1:
                break
        spans.append((pos + 1, close + 1))
        pos = text.find("](", close + 1)
    return spans


def _edit(text, spans, fn):
    pieces = []
    last = 0
    for a, b in spans:
        pieces.append(text[last:a])
        pieces.append(fn(text[a:b]))
        last = b
    pieces.append(text[last:])
    return "".join(pieces)


def _mask(text):
    text = _edit(text, _code_spans(text), _hide)
    text = _edit(text, _target_spans(text), _hide)
    return _URL.sub(lambda m: _hide(m.group(0)), text)


def _split(text, masked):
    spans = []
    start = 0
    n = len(masked)
    for i, ch in enumerate(masked):
        if ch not in ".!?":
            continue
        j = i + 1
        while j < n and masked[j] in "\"')]":
            j += 1
        if j >= n or not masked[j].isspace():
            continue
        k = j
        while k < n and masked[k].isspace():
            k += 1
        if k < n and text[k].islower():
            continue
        s = i
        while s > 0 and not masked[s - 1].isspace():
            s -= 1
        if masked[s:i + 1].lower().lstrip("([{\"'") in _ABBR:
            continue
        spans.append((start, k))
        start = k
    spans.append((start, n))
    return spans


def _unlink(text):
    brk = [m.start() for m in re.finditer(r"[\[\]]", text)]
    pieces = []
    last = 0
    pos = text.find("](")
    close = -1
    while pos != -1:
        if close < pos + 2:
            close = text.find(")", pos + 2)
            if close == -1:
                break
        i = bisect.bisect_left(brk, pos) - 1
        if i >= 0 and brk[i] >= last and text[brk[i]] == "[":
            pieces.append(text[last:brk[i]])
            pieces.append(text[brk[i] + 1:pos])
            last = close + 1
            pos = text.find("](", last)
        else:
            pos = text.find("](", pos + 1)
    pieces.append(text[last:])
    return "".join(pieces)


def _strip_tags(text):
    return _TAG.sub("", text)


def _prose(text):
    t = _edit(text, _code_spans(text), lambda s: "")
    t = _unlink(t)
    t = _strip_tags(t)
    t = _URL.sub("", t)
    t = t.replace("*", "").replace("~~", "")
    return _SPACES.sub(" ", t).strip()


def read_prose(text, footer=None):
    out = []
    for parts in _blocks(text.replace("\r\n", "\n").split("\n"), footer):
        joined = ""
        owners = []
        for no, content in parts:
            if not content:
                continue
            if joined:
                joined += " "
                owners.append(no)
            joined += content
            owners.extend([no] * len(content))
        masked = _mask(joined)
        for a, b in _split(joined, masked):
            seg = joined[a:b]
            s = seg.strip()
            if not s:
                continue
            prose = _prose(s)
            if _count(prose)[0] == 0:
                continue
            line = owners[a + len(seg) - len(seg.lstrip())]
            out.append((s, line, ari(prose)))
    return [Sentence(f"S{i}", line, s, g) for i, (s, line, g) in enumerate(out, 1)]


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
