#!/usr/bin/env python3
import argparse, bisect, os, re, sys, tomllib
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


class ConfigError(Exception):
    pass


def find_config(env):
    for key in ("FURBISH_CONFIG", "XDG_CONFIG_HOME", "HOME"):
        val = env.get(key)
        if not val:
            continue
        if key == "FURBISH_CONFIG":
            if not os.path.isfile(val):
                raise ConfigError(f"FURBISH_CONFIG points to {val} which does not exist")
            return val
        if key == "XDG_CONFIG_HOME":
            path = os.path.join(val, "furbish", "config.toml")
        else:
            path = os.path.join(val, ".config", "furbish", "config.toml")
        if os.path.isfile(path):
            return path
    return None


def _validate_repo_name(name):
    if name.count("/") != 1:
        raise ConfigError(f"repo key {name} must contain exactly one slash")
    owner, repo = name.split("/")
    if not owner or not repo:
        raise ConfigError(f"repo key {name} has empty owner or name")
    if any(c.isspace() for c in name):
        raise ConfigError(f"repo key {name} contains whitespace")


def _validate_string(key, val, repo):
    if not isinstance(val, str):
        raise ConfigError(f"{key} in {repo} must be a string")


def _validate_nonempty_string(key, val, repo):
    _validate_string(key, val, repo)
    if not val:
        raise ConfigError(f"{key} in {repo} must be non-empty")


def _validate_list_of_strings(key, val, repo):
    if not isinstance(val, list):
        raise ConfigError(f"{key} in {repo} must be a list")
    for item in val:
        if not isinstance(item, str):
            raise ConfigError(f"{key} in {repo} must contain only strings")
        if not item:
            raise ConfigError(f"{key} in {repo} must not contain empty strings")


def _validate_int_at_least_one(key, val, repo):
    if isinstance(val, bool):
        raise ConfigError(f"{key} in {repo} must be an integer")
    if not isinstance(val, int):
        raise ConfigError(f"{key} in {repo} must be an integer")
    if val < 1:
        raise ConfigError(f"{key} in {repo} must be at least 1")


def _validate_bool(key, val, repo):
    if not isinstance(val, bool):
        raise ConfigError(f"{key} in {repo} must be a boolean")


def _validate_code_names(cn, repo):
    if not isinstance(cn, dict):
        raise ConfigError(f"code_names in {repo} must be a table")
    for k in cn:
        if k not in ("quoted_tests", "checks", "states"):
            raise ConfigError(f"unknown key {k} in code_names in {repo}")
    quoted_tests = cn.get("quoted_tests", False)
    checks = cn.get("checks", [])
    states = cn.get("states", [])
    _validate_bool("quoted_tests", quoted_tests, repo)
    _validate_list_of_strings("checks", checks, repo)
    _validate_list_of_strings("states", states, repo)
    return {"quoted_tests": quoted_tests, "checks": list(checks), "states": list(states)}


def _validate_external(ext, repo):
    if not isinstance(ext, list):
        raise ConfigError(f"external in {repo} must be a list")
    seen_names = set()
    result = []
    for entry in ext:
        if not isinstance(entry, dict):
            raise ConfigError(f"external entry in {repo} must be a table")
        for k in entry:
            if k not in ("name", "mode", "command", "fail"):
                raise ConfigError(f"unknown key {k} in external entry in {repo}")
        name = entry.get("name")
        mode = entry.get("mode")
        command = entry.get("command")
        fail = entry.get("fail")
        if name is None:
            raise ConfigError(f"name is required in external entry in {repo}")
        if not isinstance(name, str) or not name:
            raise ConfigError(f"name in external entry in {repo} must be a non-empty string")
        if name in seen_names:
            raise ConfigError(f"duplicate name {name} in external in {repo}")
        seen_names.add(name)
        if mode is None:
            raise ConfigError(f"mode is required in external entry in {repo}")
        if mode not in ("lines", "json"):
            raise ConfigError(f"mode in external entry in {repo} must be 'lines' or 'json'")
        if command is None:
            raise ConfigError(f"command is required in external entry in {repo}")
        if not isinstance(command, list) or not command:
            raise ConfigError(f"command in external entry in {repo} must be a non-empty list")
        for cmd in command:
            if not isinstance(cmd, str) or not cmd:
                raise ConfigError(f"command in external entry in {repo} must contain non-empty strings")
        if mode == "lines":
            if fail is None:
                raise ConfigError(f"fail is required when mode is 'lines' in external entry in {repo}")
            if not isinstance(fail, str):
                raise ConfigError(f"fail in external entry in {repo} must be a string")
            if not fail:
                raise ConfigError(f"fail in external entry in {repo} must not be empty")
            try:
                re.compile(fail)
            except (re.error, OverflowError, RecursionError):
                raise ConfigError(f"fail in external entry in {repo} is not a valid regex")
        else:
            if fail is not None:
                raise ConfigError(f"fail is not allowed when mode is 'json' in external entry in {repo}")
        result.append({"name": name, "mode": mode, "command": list(command), "fail": fail if mode == "lines" else None})
    return result


def _validate_profile(profile, repo):
    if not isinstance(profile, dict):
        raise ConfigError(f"profile for {repo} must be a table")
    allowed = {"pr_template", "issue_template", "first_line_prefix", "footer", "tldr", "tldr_words", "tldr_max_sentences", "banned", "private", "keep_negation", "code_names", "external"}
    for k in profile:
        if k not in allowed:
            raise ConfigError(f"unknown key {k} in profile for {repo}")
    pr_template = profile.get("pr_template")
    if pr_template is not None:
        _validate_string("pr_template", pr_template, repo)
        pr_template = os.path.expanduser(pr_template)
    issue_template = profile.get("issue_template")
    if issue_template is not None:
        _validate_string("issue_template", issue_template, repo)
        issue_template = os.path.expanduser(issue_template)
    first_line_prefix = profile.get("first_line_prefix")
    if first_line_prefix is not None:
        _validate_nonempty_string("first_line_prefix", first_line_prefix, repo)
    footer = profile.get("footer")
    if footer is not None:
        _validate_string("footer", footer, repo)
        try:
            re.compile(footer)
        except (re.error, OverflowError, RecursionError):
            raise ConfigError(f"footer in {repo} is not a valid regex")
    tldr = profile.get("tldr", "off")
    if tldr not in ("required", "off"):
        raise ConfigError(f"tldr in {repo} must be 'required' or 'off'")
    tldr_words = profile.get("tldr_words")
    tldr_max_sentences = profile.get("tldr_max_sentences")
    if tldr == "required":
        if tldr_words is None:
            raise ConfigError(f"tldr_words is required when tldr is 'required' in {repo}")
        if tldr_max_sentences is None:
            raise ConfigError(f"tldr_max_sentences is required when tldr is 'required' in {repo}")
    if tldr_words is not None:
        _validate_int_at_least_one("tldr_words", tldr_words, repo)
    if tldr_max_sentences is not None:
        _validate_int_at_least_one("tldr_max_sentences", tldr_max_sentences, repo)
    banned = profile.get("banned", [])
    _validate_list_of_strings("banned", banned, repo)
    private = profile.get("private", [])
    _validate_list_of_strings("private", private, repo)
    keep_negation = profile.get("keep_negation", [])
    _validate_list_of_strings("keep_negation", keep_negation, repo)
    code_names = profile.get("code_names", {})
    code_names = _validate_code_names(code_names, repo)
    external = profile.get("external", [])
    external = _validate_external(external, repo)
    return {
        "pr_template": pr_template,
        "issue_template": issue_template,
        "first_line_prefix": first_line_prefix,
        "footer": footer,
        "tldr": tldr,
        "tldr_words": tldr_words,
        "tldr_max_sentences": tldr_max_sentences,
        "banned": list(banned),
        "private": list(private),
        "keep_negation": list(keep_negation),
        "code_names": code_names,
        "external": external,
    }


def _normalise(data):
    for k in data:
        if k not in ("default_repo", "repo"):
            raise ConfigError(f"unknown setting {k}")
    default_repo = data.get("default_repo")
    if default_repo is not None:
        if not isinstance(default_repo, str):
            raise ConfigError("default_repo must be a string")
        _validate_repo_name(default_repo)
    table = data.get("repo", {})
    if not isinstance(table, dict):
        raise ConfigError("repo must be a table")
    profiles = {}
    for name, profile in table.items():
        _validate_repo_name(name)
        profiles[name] = _validate_profile(profile, name)
    if default_repo is not None and default_repo not in profiles:
        raise ConfigError(f"default_repo {default_repo} has no profile")
    return {"default_repo": default_repo, "repo": profiles}


def load_config(path):
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return _normalise(data)
    except RecursionError:
        raise ConfigError(f"{path}: the file is nested too deep to read") from None
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError, ConfigError) as e:
        raise ConfigError(f"{path}: {e}") from None


def pick_profile(config, repo):
    if config is None:
        if repo is not None:
            raise ConfigError(f"no config file but repo {repo} was requested")
        return None
    if repo is None:
        repo = config.get("default_repo")
        if repo is None:
            return None
    if repo not in config["repo"]:
        known = ", ".join(sorted(config["repo"]))
        raise ConfigError(f"repo {repo} not found; known repos: {known}")
    return config["repo"][repo]


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
