#!/usr/bin/env python3
import argparse, bisect, json, os, re, shutil, subprocess, sys, tempfile, tomllib
from collections import namedtuple

__version__ = "0.1.0.dev0"

Sentence = namedtuple("Sentence", "id line text")
Located = namedtuple("Located", "sentence where kind level heading under span")

_URL = re.compile(r"https?://\S*[^\s.,;:!?)\]\"']")
_TAG = re.compile(r"<[/!A-Za-z][^<>]*>")
_HTML_ONLY = re.compile(r"(?:<[/!A-Za-z][^<>]*>\s*)+")
_HEADING = re.compile(r" {0,3}(#{1,6})\s")
_LIST = re.compile(r"\s*(?:[-*+]|\d+[.)])[ \t]")
_EMPTY_ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])[ \t]*")
_TASK = re.compile(r"\[[ xX]\][ \t]+")
_THEMATIC = re.compile(r" {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*")
_UNDERLINE = re.compile(r" {0,3}(?:=+|-+)[ \t]*")
_TABLE_DELIM = re.compile(r"\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?")
_REFDEF = re.compile(r" {0,3}\[(?!\^)[^\]]+\]:[ \t]*\S")
_SPACES = re.compile(r"\s+")
_STOPS = re.compile(r"[.!?]")
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


def _grade(words, chars):
    if not words:
        return 0.0
    return 4.71 * chars / words + 0.5 * words - 21.43


def ari(text):
    return _grade(*_count(text))


def _fence_open(line):
    n = len(line) - len(line.lstrip(" "))
    if n > 3:
        return None
    rest = line[n:]
    if not rest or rest[0] not in "`~":
        return None
    c = rest[0]
    k = len(rest) - len(rest.lstrip(c))
    if k < 3 or (c == "`" and "`" in rest[k:]):
        return None
    return (c, k)


def _fence_close(line, c, k):
    n = len(line) - len(line.lstrip(" "))
    if n > 3:
        return False
    s = line.strip()
    return len(s) >= k and s == c * len(s)


def _comments(line):
    if "<!--" not in line:
        return line, False
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


class _IndentedCode:
    def __init__(self):
        self.prev = None
        self.blank = True
        self.code = False

    def step(self, line):
        stripped = line.strip()
        if not stripped:
            self.blank = True
            return self.code
        indent = 4 if line.startswith("\t") else len(line) - len(line.lstrip(" "))
        if self.code:
            if indent >= 4:
                self.blank = False
                return True
            self.code = False
        if self.blank and indent >= 4 and self.prev != "list":
            self.code = True
            self.blank = False
            return True
        self.blank = False
        if _LIST.match(line):
            self.prev = "list"
        elif indent == 0:
            self.prev = "quote" if stripped[0] == ">" else "text"
        return False


def _blocks(lines, footer):
    blocks = []
    cur = None
    fence = None
    comment = False
    summary = False
    table = False
    icode = _IndentedCode()
    for no, line in enumerate(lines, 1):
        base = 0
        if no == 1 and line.startswith("\ufeff"):
            line = line[1:]
            base = 1
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
            base += end + 3
        if footer and re.search(footer, line):
            cur = None
            continue
        fo = _fence_open(line)
        if fo:
            fence = fo
            cur = None
            continue
        if icode.step(line):
            cur = None
            continue
        whole = line
        line, comment = _comments(line)
        shift = base if line == whole else None
        end_col = len(line.rstrip())
        hid = _edit(line, _code_spans(line), _hide).lower()
        if "<summary" in hid:
            summary = "</summary>" not in hid
            cur = None
            continue
        stripped = line.strip()
        if not stripped:
            cur = None
            table = False
            continue
        if "|" in stripped and _TABLE_DELIM.fullmatch(stripped):
            if cur is not None and cur[0] == "para" and "|" in cur[1][-1][1]:
                cur[1].pop()
                if not cur[1]:
                    blocks.pop()
            cur = None
            table = True
            continue
        if stripped[0] == "|" or _HTML_ONLY.fullmatch(stripped):
            cur = None
            continue
        if table:
            if _HEADING.match(line) or stripped[0] == ">" or _LIST.match(line):
                table = False
            else:
                cur = None
                continue
        c0 = stripped[0]
        if c0 in "=-" and cur is not None and cur[0] == "para" and _UNDERLINE.fullmatch(line):
            cur[0] = "heading"
            cur[2] = 1 if c0 == "=" else 2
            cur = None
            continue
        if (c0 in "-*_" and _THEMATIC.fullmatch(line)) or (c0 in "-*+0123456789" and _EMPTY_ITEM.fullmatch(line)) or (c0 == "[" and cur is None and _REFDEF.match(line)):
            cur = None
            continue
        hm = _HEADING.match(line)
        if hm:
            t = line[hm.end(1):].strip()
            blocks.append(["heading", [(no, t, None if shift is None else shift + end_col - len(t))], len(hm.group(1))])
            cur = None
            continue
        lm = _LIST.match(line)
        if lm:
            t = line[lm.end():].strip()
            tm = _TASK.match(t)
            if tm:
                t = t[tm.end():]
            cur = ["list", [(no, t, None if shift is None else shift + end_col - len(t))], 0]
            blocks.append(cur)
            continue
        if stripped[0] == ">":
            t = stripped.lstrip("> \t")
            qm = _LIST.match(t)
            if qm:
                t = t[qm.end():].strip()
            part = (no, t, None if shift is None else shift + end_col - len(t))
            if cur and cur[0] == "quote":
                cur[1].append(part)
            else:
                cur = ["quote", [part], 0]
                blocks.append(cur)
            continue
        part = (no, stripped, None if shift is None else shift + end_col - len(stripped))
        if cur:
            cur[1].append(part)
        else:
            cur = ["para", [part], 0]
            blocks.append(cur)
    return blocks


def _code_spans(text):
    if "`" not in text:
        return []
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


_ID_START = re.compile(r"https?://|[0-9a-f]{7,40}(?![0-9A-Za-z])")


def _starts_id(text, k):
    m = _ID_START.match(text, k)
    return bool(m) and (m.group().startswith("http") or not m.group().isalpha())


def _split(text, masked):
    spans = []
    start = 0
    n = len(masked)
    for m in _STOPS.finditer(masked):
        i = m.start()
        j = i + 1
        while j < n and masked[j] in "\"')]":
            j += 1
        if j >= n or not masked[j].isspace():
            continue
        k = j
        while k < n and masked[k].isspace():
            k += 1
        if k < n and text[k].islower() and not _starts_id(text, k):
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
    if "](" not in text:
        return text
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
    return _TAG.sub("", text) if "<" in text else text


def _prose(text):
    t = _edit(text, _code_spans(text), lambda s: "")
    t = _unlink(t)
    t = _strip_tags(t)
    t = _URL.sub("", t)
    t = _edit(t, _sha_spans(t), lambda x: "")
    t = t.replace("*", "").replace("~~", "")
    return _SPACES.sub(" ", t).strip()


def _sentences(lines, footer):
    out = []
    stack = []
    for kind, parts, level in _blocks(lines, footer):
        joined = ""
        starts = []
        nos = []
        cols = []
        unsafe = [0]
        for no, content, col in parts:
            if not content:
                continue
            if joined:
                joined += " "
            starts.append(len(joined))
            nos.append(no)
            cols.append(col)
            unsafe.append(unsafe[-1] + (col is None))
            joined += content
        if kind == "heading":
            while stack and stack[-1][0] >= level:
                stack.pop()
        under = tuple(text for _, text in stack)
        if kind == "heading":
            stack.append((level, joined))
        masked = _mask(joined)
        for a, b in _split(joined, masked):
            seg = joined[a:b]
            s = seg.strip()
            if not s:
                continue
            if _count(_prose(s))[0] == 0:
                continue
            sa = a + len(seg) - len(seg.lstrip())
            sb = sa + len(s)
            i = bisect.bisect_right(starts, sa) - 1
            j = bisect.bisect_right(starts, sb - 1) - 1
            where = None
            if unsafe[j + 1] == unsafe[i]:
                where = ((nos[i], cols[i] + sa - starts[i]), (nos[j], cols[j] + sb - starts[j]))
                for k in range(i + 1, j + 1):
                    if nos[k] != nos[k - 1] + 1 or lines[nos[k] - 1][:cols[k]].strip(" \t>"):
                        where = None
                        break
            out.append((s, nos[i], where, kind, level, joined if kind == "heading" else None, under, (sa, sb)))
    return [Located(Sentence(f"S{i}", line, s), where, kind, level, head, under, span) for i, (s, line, where, kind, level, head, under, span) in enumerate(out, 1)]


def read_prose(text, footer=None):
    return [x.sentence for x in _sentences(text.replace("\r\n", "\n").split("\n"), footer)]


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
    for key, names in (("checks", checks), ("states", states)):
        for name in names:
            if not re.match(r"\w", name):
                raise ConfigError(f"{key} in {repo} has {name!r}, and every name must start with a letter or a digit")
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
    allowed = {"pr_template", "issue_template", "first_line_prefix", "first_line_skip", "footer", "tldr", "tldr_words", "tldr_max_sentences", "banned", "private", "keep_negation", "grade_skip", "code_names", "external"}
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
    first_line_skip = profile.get("first_line_skip")
    if first_line_skip is not None:
        _validate_nonempty_string("first_line_skip", first_line_skip, repo)
        try:
            re.compile(first_line_skip)
        except (re.error, OverflowError, RecursionError):
            raise ConfigError(f"first_line_skip in {repo} is not a valid regex")
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
    grade_skip = profile.get("grade_skip", [])
    _validate_list_of_strings("grade_skip", grade_skip, repo)
    for pattern in grade_skip:
        try:
            re.compile(pattern)
        except (re.error, OverflowError, RecursionError):
            raise ConfigError(f"grade_skip in {repo} is not a valid regex: {pattern}")
    code_names = profile.get("code_names", {})
    code_names = _validate_code_names(code_names, repo)
    external = profile.get("external", [])
    external = _validate_external(external, repo)
    return {
        "pr_template": pr_template,
        "issue_template": issue_template,
        "first_line_prefix": first_line_prefix,
        "first_line_skip": first_line_skip,
        "footer": footer,
        "tldr": tldr,
        "tldr_words": tldr_words,
        "tldr_max_sentences": tldr_max_sentences,
        "banned": list(banned),
        "private": list(private),
        "keep_negation": list(keep_negation),
        "grade_skip": list(grade_skip),
        "code_names": code_names,
        "external": external,
    }


_KIND_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def _validate_kinds(kinds, base, repo):
    if not isinstance(kinds, dict):
        raise ConfigError(f"kinds in {repo} must be a table")
    out = {}
    for name, kind in kinds.items():
        if not _KIND_NAME.fullmatch(name):
            raise ConfigError(f"kind name {name} in {repo} must be letters, digits, - or _")
        if not isinstance(kind, dict):
            raise ConfigError(f"kind {name} in {repo} must be a table")
        out[name] = _validate_profile({**base, **kind}, f"{repo} kind {name}")
    return out


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
        kinds = {}
        if isinstance(profile, dict):
            profile = dict(profile)
            kinds = profile.pop("kinds", {})
        profiles[name] = _validate_profile(profile, name)
        profiles[name]["kinds"] = _validate_kinds(kinds, profile, name)
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


def pick_profile(config, repo, kind=None):
    if config is None:
        if kind is not None:
            raise ConfigError(f"no config file was found, so there is no kind {kind}")
        if repo is not None:
            raise ConfigError(f"no config file was found, so there is no profile for {repo}")
        return None
    if repo is None:
        repo = config.get("default_repo")
        if repo is None:
            if kind is not None:
                raise ConfigError("a kind needs a repo profile: pass --repo or set default_repo")
            return None
    if repo not in config["repo"]:
        known = ", ".join(sorted(config["repo"]))
        raise ConfigError(f"the config file has no profile for {repo}; it has: {known}")
    profile = config["repo"][repo]
    if kind is None:
        return profile
    if kind not in profile["kinds"]:
        names = ", ".join(sorted(profile["kinds"])) or "none"
        raise ConfigError(f"the profile for {repo} has no kind {kind}; it has: {names}")
    return profile["kinds"][kind]


Problem = namedtuple("Problem", "line sid rule message")

_MENTION = re.compile(r"(?<!\w)@[A-Za-z0-9][A-Za-z0-9-]*")
_SPDX_PATTERNS = (
    re.compile(r"\b[AL]?GPL ?v?\d(?:\.\d)?\+?(?![\w-]|\.\d)"),
    re.compile(r"\bApache(?: License)?,? (?:v|version )?2(?:\.0)?\b"),
    re.compile(r"\bBSD [23](?:-| )[Cc]lause\b"),
)
_SHA_RE = re.compile(r"[0-9a-f]{7,40}")
_LABEL_RE = re.compile(r"^(\*\*|__)[^*_]{1,40}?(:(\*\*|__)|(\*\*|__):)\s*")
_BARE_URL_RE = re.compile(r"https?://\S+")
_CHECKBOX_RE = re.compile(r"(?:[-*+]|\d+[.)])\s+\[[ xX]\]")


def _mask_code(line):
    return _edit(line, _code_spans(line), _hide) if "`" in line else line


def _outside_code(lines):
    fence = None
    comment = False
    icode = _IndentedCode()
    for no, line in enumerate(lines, 1):
        if no == 1:
            line = line.removeprefix("\ufeff")
        if fence:
            if _fence_close(line, *fence):
                fence = None
            continue
        if comment:
            end = line.find("-->")
            if end == -1:
                continue
            comment = False
            line = line[end + 3:]
        fo = _fence_open(line)
        if fo:
            fence = fo
            continue
        if icode.step(line):
            continue
        if "<!--" in line:
            line, comment = _comments(line)
        yield no, line


def _first_nonblank(lines):
    for i, line in enumerate(lines):
        if line.strip():
            return i
    return None


def _last_nonblank(lines):
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            return i
    return None


def _fold_lines(outside):
    folds = set()
    depth = 0
    for no, line in outside:
        low = _mask_code(line).lower()
        if "<details" in low:
            depth += 1
        if depth:
            folds.add(no)
        if "</details>" in low:
            depth = max(0, depth - 1)
    return folds


def _rule_prefix(lines, prefix):
    if not prefix:
        return []
    i = _first_nonblank(lines)
    if i is None or lines[i].lstrip().startswith(prefix):
        return []
    return [Problem(i + 1, "", "prefix", f"the first line must start with {prefix}")]


def _rule_tldr(lines, outside, sentences, p):
    limit = p.get("tldr_words")
    cap = p.get("tldr_max_sentences")
    prefix = p.get("first_line_prefix")
    i = _first_nonblank(lines)
    if i is None:
        return []
    skip = p.get("first_line_skip")
    if skip and re.fullmatch(skip, lines[i].strip()):
        after = _first_nonblank(lines[i + 1:])
        if after is not None:
            i += 1 + after
    no = i + 1
    first = lines[i].lstrip()
    if prefix and first.startswith(prefix):
        first = first[len(prefix):].lstrip()
    if first.startswith("**TL;DR:**"):
        end = i
        while end < len(lines) and lines[end].strip() and (end == i or not _HEADING.match(lines[end])):
            end += 1
        if cap is None:
            return []
        count = sum(1 for s in sentences if no <= s.line <= end)
        if count > cap:
            return [Problem(no, "", "tldr", f"the TL;DR has {count} sentences and must have {cap} or fewer")]
        return []
    if limit is None:
        return []
    folds = _fold_lines(outside)
    visible = sum(_count(s.text)[0] for s in sentences if s.line not in folds)
    if visible >= limit:
        return [Problem(no, "", "tldr", f"a post of {limit} words or more needs a **TL;DR:** line first")]
    return []


def _rule_footer(lines, footer):
    if not footer:
        return []
    i = _last_nonblank(lines)
    if i is None or re.search(footer, lines[i]):
        return []
    return [Problem(i + 1, "", "footer", "the last line should be the footer")]


def _rule_banned(sentences, phrases):
    out = []
    for s in sentences:
        low = _edit(s.text, _code_spans(s.text), _hide).lower()
        for phrase in phrases:
            p = phrase.lower()
            if not p:
                continue
            idx = low.find(p)
            while idx != -1:
                end = idx + len(p)
                if (idx == 0 or not low[idx - 1].isalnum()) and (end >= len(low) or not low[end].isalnum()):
                    out.append(Problem(s.line, s.id, "banned", f"found {phrase}, which is banned"))
                    break
                idx = low.find(p, idx + 1)
    return out


def _rule_private(lines, phrases):
    out = []
    for no, line in enumerate(lines, 1):
        low = line.lower()
        for phrase in phrases:
            p = phrase.lower()
            if p and p in low:
                out.append(Problem(no, "", "private", f"found {phrase}, which is private text and must not reach a post"))
    return out


def _rule_code_spans(outside):
    out = []
    for no, line in outside:
        if "`" not in line:
            continue
        for a, b in _code_spans(line):
            s = line[a:b]
            k = len(s) - len(s.lstrip("`"))
            content = s[k:len(s) - k].strip()
            if "http://" in content or "https://" in content:
                out.append(Problem(no, "", "url-in-code", "a URL belongs outside backticks so it becomes a link"))
            if _SHA_RE.fullmatch(content) and any(c.isdigit() for c in content) and any(c.isalpha() for c in content):
                out.append(Problem(no, "", "sha", f"{content} is a commit sha in backticks; write it bare, because GitHub only links a bare sha"))
    return out


def _mask_links(line):
    line = _mask_code(line)
    ends = {e: s for s, e in _brackets(line)}
    ranges = [m.span() for m in _URL.finditer(line)]
    for start, end in _target_spans(line):
        ranges.append((ends.get(start, start), end))
    return _edit(line, _merge(ranges), _hide)


def _rule_mentions(outside):
    out = []
    for no, line in outside:
        if "@" not in line:
            continue
        for m in _MENTION.finditer(_mask_links(line)):
            out.append(Problem(no, "", "mention", f"{m.group()} is an @ mention, which pings that person"))
    return out


def _rule_spdx(outside):
    out = []
    for no, line in outside:
        if "GPL" not in line and "Apache" not in line and "BSD" not in line:
            continue
        masked = _mask_code(line)
        for pat in _SPDX_PATTERNS:
            for m in pat.finditer(masked):
                name = m.group(0)
                example = "Apache-2.0" if name.startswith("Apache") else f"BSD-{name[4]}-Clause" if name.startswith("BSD") else "GPL-2.0-only"
                out.append(Problem(no, "", "spdx", f"{name} is an informal licence name; use the SPDX licence id, for example {example}"))
    return out


def _details_gaps(lines, outside):
    out = []
    for no, line in outside:
        if "</" not in line:
            continue
        low = _mask_code(line).lower()
        if "</summary>" in low and no < len(lines) and lines[no].strip():
            out.append((no, "after"))
        if "</details>" in low and no > 1 and lines[no - 2].strip():
            out.append((no, "before"))
    return out


def _rule_details(lines, outside):
    return [Problem(no, "", "details-blank", f"a blank line is needed {side} {'</summary>' if side == 'after' else '</details>'} or the text inside will not be formatted") for no, side in _details_gaps(lines, outside)]


def _cleaned(text):
    cleaned = _LABEL_RE.sub("", text)
    cleaned = _edit(cleaned, _code_spans(cleaned), lambda t: "code")
    cleaned = _strip_tags(_unlink(cleaned))
    cleaned = _BARE_URL_RE.sub("link", cleaned)
    return cleaned.replace("*", "").replace("~~", "")


def _grade_skip(p):
    return [re.compile(x) for x in p.get("grade_skip", [])]


def _hard(lines, located, exempt, skip=()):
    skipped = {}
    for x in located:
        s = x.sentence
        ignore = skipped.get(s.line)
        if ignore is None:
            src = lines[s.line - 1].removeprefix("\ufeff").strip()
            ignore = skipped[s.line] = src in exempt or bool(_CHECKBOX_RE.match(src)) or any(r.search(src) for r in skip)
        if ignore or x.kind == "heading":
            continue
        cleaned = _cleaned(s.text)
        if len(cleaned.split()) < 3:
            continue
        grade = ari(cleaned)
        if grade >= 10:
            yield s, grade


def _rule_grade(lines, located, exempt, skip):
    return [Problem(s.line, s.id, "grade", f"the reading grade is {round(grade)}, which is too hard; every sentence should be under grade 10") for s, grade in _hard(lines, located, exempt, skip)]


def check(text, profile=None, post=False, exempt=frozenset()):
    p = profile or {}
    lines = text.replace("\r\n", "\n").split("\n")
    lines[0] = lines[0].removeprefix("\ufeff")
    footer = p.get("footer")
    outside = list(_outside_code(lines))
    need = post or p.get("tldr") == "required" or bool(p.get("banned"))
    located = _sentences(lines, footer) if need else []
    sentences = [x.sentence for x in located]
    problems = []
    problems += _rule_prefix(lines, p.get("first_line_prefix"))
    if p.get("tldr") == "required":
        problems += _rule_tldr(lines, outside, sentences, p)
    problems += _rule_footer(lines, footer)
    problems += _rule_banned(sentences, p.get("banned") or [])
    problems += _rule_private(lines, p.get("private") or [])
    problems += _rule_code_spans(outside)
    problems += _rule_mentions(outside)
    problems += _rule_spdx(outside)
    problems += _rule_details(lines, outside)
    if post:
        problems += _rule_grade(lines, located, exempt, _grade_skip(p))
    problems.sort(key=lambda q: q.line)
    return problems


EXTERNAL_TIMEOUT = 60


class ExternalError(ConfigError):
    pass


def _parse_json_output(name, stdout):
    try:
        data = json.loads(stdout)
    except (ValueError, RecursionError):
        raise ExternalError(f"{name}: printed something that is not JSON")
    if not isinstance(data, dict):
        raise ExternalError(f"{name}: printed JSON in a shape furbish does not read")
    for v in data.values():
        if not isinstance(v, list):
            raise ExternalError(f"{name}: printed JSON in a shape furbish does not read")
    return data


def _parse_lines_output(name, draft_path, stdout, fail_re):
    path_prefix = "^" + re.escape(draft_path) + r":(\d{1,9})(?::\d+)?:\s*(.*)$"
    path_re = re.compile(path_prefix)
    problems = []
    for line in stdout.split("\n"):
        line = line.rstrip("\r")
        if not fail_re.search(line):
            continue
        m = path_re.match(line)
        if m:
            line_num = int(m.group(1))
            text = m.group(2)
        else:
            line_num = 0
            text = line.strip()
        problems.append(Problem(line_num, "", name, f"{name}: {text}"))
    return problems


def _parse_json_alerts(name, data):
    problems = []
    for alerts in data.values():
        for item in alerts:
            if not isinstance(item, dict):
                raise ExternalError(f"{name}: printed JSON in a shape furbish does not read")
            line = item.get("Line")
            if isinstance(line, int) and not isinstance(line, bool) and line >= 0:
                line_num = line
            else:
                line_num = 0
            check = item.get("Check")
            if not isinstance(check, str):
                check = ""
            msg = item.get("Message")
            if not isinstance(msg, str) or not msg:
                msg = "reported a problem"
            if check:
                problems.append(Problem(line_num, "", name, f"{name}: {msg} ({check})"))
            else:
                problems.append(Problem(line_num, "", name, f"{name}: {msg}"))
    return problems


def _first_line(text):
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _why(stdout, stderr):
    for text in (stdout, stderr):
        try:
            obj = json.loads(text)
        except (ValueError, RecursionError):
            continue
        if isinstance(obj, dict) and isinstance(obj.get("Text"), str) and obj["Text"]:
            return obj["Text"][:200]
    return (_first_line(stdout) or _first_line(stderr) or "no output")[:200]


def _run_entry(entry, draft_path, timeout):
    name = entry["name"]
    mode = entry["mode"]
    command = entry["command"]
    argv = list(command) + [draft_path]
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except (OSError, ValueError) as e:
        reason = getattr(e, "strerror", None) or e
        raise ExternalError(f"{name}: could not run {command[0]}: {reason}")
    except subprocess.TimeoutExpired:
        raise ExternalError(f"{name}: took longer than {timeout:g} seconds and was stopped")
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    rc = result.returncode
    if rc not in (0, 1):
        raise ExternalError(f"{name}: stopped with status {rc}: {_why(stdout, stderr)}")
    if mode == "lines":
        fail = entry["fail"]
        if fail is None:
            return []
        fail_re = re.compile(fail)
        return _parse_lines_output(name, draft_path, stdout, fail_re)
    else:
        if not stdout.strip():
            if rc == 1:
                raise ExternalError(f"{name}: stopped with status 1 and printed nothing: {_why(stdout, stderr)}")
            return []
        data = _parse_json_output(name, stdout)
        return _parse_json_alerts(name, data)


def run_external(entries, draft_path, timeout=EXTERNAL_TIMEOUT):
    problems = []
    for entry in entries:
        problems.extend(_run_entry(entry, draft_path, timeout))
    return problems


_ID = re.compile(r"[Ss]([0-9]{1,9})")
_SHA_TOKEN = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{7,40}(?![0-9A-Za-z])")
_NUMBER = re.compile(r"\d+(?:[.,:/]\d+)*")
_TAG_NAME = re.compile(r"(?<=<)/?[A-Za-z][A-Za-z0-9]*(?=[\s>/])")
_WORD = re.compile(r"[a-z]+(?:['\u2019\u02bc][a-z]+)*")
_APOSTROPHE = re.compile(r"['\u2019\u02bc]")
_NT = re.compile(r"n['\u2019\u02bc]t$")
_QUOTED_TAG = re.compile(r"<[/!A-Za-z](?:[^<>\"']|\"[^\"<]*\"|'[^'<]*')*>")
_IMAGE = re.compile(r"!\[[^\]\[]*\]\([^()]*\)")
_HIDDEN = re.compile("[\t\u200b\u2060\ufeff\U000e0000-\U000e007f]")
_NEGATIONS = frozenset(("not", "no", "never", "none", "nothing", "nobody", "nowhere", "neither", "nor", "cannot", "without"))
Edit = namedtuple("Edit", "text first old new")


class Refused(Exception):
    def __init__(self, reasons, line=0, sid=""):
        super().__init__("\n".join(reasons))
        self.reasons = reasons
        self.line = line
        self.sid = sid


def _negated(text):
    text = _QUOTED_TAG.sub("", _IMAGE.sub("", text))
    for w in _WORD.findall(_prose(text).lower()):
        if _APOSTROPHE.split(w)[0] in _NEGATIONS or _NT.search(w):
            return True
    return False


def _sha_spans(text):
    return [m.span() for m in _SHA_TOKEN.finditer(text) if not m.group().isdigit() and not m.group().isalpha()]


def _lost(old, new):
    out = []
    spans = _code_spans(old)
    kept = {new[a:b] for a, b in _code_spans(new)}
    for span in dict.fromkeys(old[a:b] for a, b in spans):
        if span not in kept:
            out.append(f"the new sentence drops the inline code {span}")
    old = _TAG_NAME.sub(" ", _edit(old, spans, lambda t: " "))
    new = _TAG_NAME.sub(" ", _edit(new, _code_spans(new), lambda t: " "))
    spans = _sha_spans(old)
    kept = {new[a:b] for a, b in _sha_spans(new)}
    for sha in dict.fromkeys(old[a:b] for a, b in spans):
        if sha not in kept:
            out.append(f"the new sentence drops the commit sha {sha}")
    old = _edit(old, spans, lambda t: " ")
    new = _edit(new, _sha_spans(new), lambda t: " ")
    kept = {n.replace(",", "") for n in _NUMBER.findall(new)}
    for num in dict.fromkeys(_NUMBER.findall(old)):
        if num.replace(",", "") not in kept:
            out.append(f"the new sentence drops the number {num}")
    return out


def _listed(heading, entries):
    h = _prose(heading).strip("_ \t").lower()
    for entry in entries:
        e = entry.strip().lower()
        if e and (h == e or h.startswith(e) and not h[len(e)].isalnum()):
            return entry
    return None


def _guards(x, old, new, entries):
    out = _lost(old, new)
    if not entries:
        return out
    if x.kind == "heading":
        hit = _listed(x.heading, entries)
        sa, sb = x.span
        if hit and not _listed(x.heading[:sa] + new + x.heading[sb:], entries):
            out.append(f'"{hit}" is a heading on the keep_negation list; keep it, or the guard stops working')
    if _negated(old) and not _negated(new):
        for text in x.under:
            hit = _listed(text, entries)
            if hit:
                out.append(f'it sits under "{hit}" and says no there, so the new sentence must say no too (with not, never, no, without and so on)')
                break
    return out


def _alnum(text):
    return [c for c in text if c.isalnum()]


def set_sentence(text, sid, new, profile=None):
    m = _ID.fullmatch(sid)
    if not m:
        raise ConfigError(f"{sid[:40]!r} is not a sentence id; ids look like S12, and furbish check prints them")
    n = int(m.group(1))
    p = profile or {}
    raw = text.split("\n")
    crs = [l.endswith("\r") for l in raw[:-1]] + [False]
    lines = [l[:-1] if c else l for l, c in zip(raw, crs)]
    footer = p.get("footer")
    located = _sentences(lines, footer)
    if not located:
        raise ConfigError("the draft has no sentences")
    if not 1 <= n <= len(located):
        raise ConfigError(f"the draft has only S1" if len(located) == 1 else f"the draft has S1 to S{len(located)}, so there is no {sid[:40]!r}")
    x = located[n - 1]
    old = x.sentence.text
    sid = f"S{n}"
    line = x.sentence.line
    new = new.strip()
    if not new:
        raise Refused(["the new sentence is empty; to remove a sentence, edit the file yourself"], line, sid)
    if _CONTROL.search(new) or _HIDDEN.search(new):
        raise Refused(["the new sentence must be one plain line, with no line breaks, tabs, control characters, hidden or text-direction marks"], line, sid)
    if "<!--" in new or "-->" in new:
        raise Refused(["the new sentence cannot hold a comment"], line, sid)
    if x.where is None:
        raise Refused(["this sentence shares its lines with a comment or with list marks that furbish would lose, so change it by hand"], line, sid)
    (l1, c1), (l2, c2) = x.where
    if l1 == l2 and lines[l1 - 1][c1:c2] != old:
        raise Refused(["furbish could not find this sentence safely, so change it by hand"], line, sid)
    if new == old and l1 == l2:
        return Edit(text, l1, lines[l1 - 1:l2], lines[l1 - 1])
    reasons = _guards(x, old, new, p.get("keep_negation") or [])
    if reasons:
        raise Refused(reasons, line, sid)
    merged = lines[l1 - 1][:c1] + new + lines[l2 - 1][c2:]
    out = lines[:l1 - 1] + [merged] + lines[l2:]
    ends = crs[:l1 - 1] + [crs[l2 - 1]] + crs[l2:]
    after = _sentences(out, footer)
    k = len(after) - len(located) + 1
    same = lambda y: (y.sentence.text, y.kind, y.level)
    fresh = after[n - 1:n - 1 + k]
    if k < 1 or [same(y) for y in after[:n - 1]] != [same(y) for y in located[:n - 1]] or [same(y) for y in after[n - 1 + k:]] != [same(y) for y in located[n:]] or any((y.kind, y.level) != (x.kind, x.level) for y in fresh) or _alnum(" ".join(y.sentence.text for y in fresh)) != _alnum(new):
        raise Refused(["the sentences around it would not read the same after this change; end the new text with a full stop, and do not start a code block, comment, table, list or heading with it"], line, sid)
    joined = "\n".join(l + "\r" if c else l for l, c in zip(out, ends))
    return Edit(joined, l1, lines[l1 - 1:l2], merged)


def _quote_spans(text):
    out = []
    for o, c in (('"', '"'), ('“', '”')):
        i = text.find(o)
        while i != -1:
            j = text.find(c, i + 1)
            if j == -1:
                break
            out.append((i, j + 1))
            i = text.find(o, j + 1)
    return out


def _merge(ranges):
    out = []
    for s, e in sorted(ranges):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def _brackets(text):
    out = []
    stack = []
    for m in re.finditer(r"(?<!\\)[\[\]]", _edit(text, _code_spans(text), lambda t: "\x01" * len(t))):
        if m.group() == "[":
            stack.append(m.start())
        elif stack:
            out.append((stack.pop(), m.end()))
    return out


def _shield(text, code=True, quotes=True):
    spans = list(_code_spans(text)) if code else []
    spans += _brackets(text)
    spans += _target_spans(text)
    spans += [m.span() for m in _URL.finditer(text)]
    spans += [m.span() for m in _TAG.finditer(text)]
    if quotes:
        spans += _quote_spans(_edit(text, _code_spans(text), lambda t: "\x01" * len(t)))
    out = list(text)
    for s, e in _merge(spans):
        out[s:e] = "\x00" * (e - s)
    return "".join(out)


def _unwrap(text):
    shield = _shield(text, code=False)
    found = []
    for s, e in _code_spans(text):
        if shield[s] == "\x00":
            continue
        span = text[s:e]
        k = len(span) - len(span.lstrip("`"))
        content = span[k:len(span) - k].strip()
        sha_ok = (_SHA_RE.fullmatch(content) and any(c.isdigit() for c in content)
                  and any(c.isalpha() for c in content))
        if sha_ok or re.fullmatch(r"https?://\S+", content):
            found.append((s, e, content))
    out, pos = [], 0
    for s, e, content in found:
        out.append(text[pos:s])
        out.append(content)
        pos = e
    out.append(text[pos:])
    return "".join(out)


def _quoted_tests(text):
    s = _shield(text, code=True, quotes=False)
    pairs = set(_quote_spans(_edit(text, _code_spans(text), lambda t: "\x01" * len(t))))
    spans, last = [], -1
    for m in re.finditer(r'"([^"\s]{1,200})"|\u201c([^\u201d\s]{1,200})\u201d', s):
        a, b = m.span()
        if (a, b) not in pairs or "\x00" in s[a:b] or a == last or text[a - 1:a] == "`" or text[b:b + 1] == "`":
            continue
        name = text[a + 1:b - 1]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.|/)[A-Za-z0-9_]+)*", name) and ("_" in name or "::" in name or re.match(r"[Tt]est[A-Z0-9]", name)):
            spans.append((a, b, "`" + name + "`"))
            last = b
    out, pos = [], 0
    for a, b, rep in spans:
        out.append(text[pos:a])
        out.append(rep)
        pos = b
    out.append(text[pos:])
    return "".join(out)


def _wrap_names(text, index):
    s = _shield(text)
    spans, last = [], 0
    for m in re.finditer(r"\w+(?:[-.]\w+)*", s):
        a = m.start()
        if a < last:
            continue
        for name in index.get(m.group(), ()):
            b = a + len(name)
            if s.startswith(name, a) and (b == len(s) or not (s[b].isalnum() or s[b] in "_-")) and text[a - 1:a] != "`" and text[b:b + 1] != "`":
                spans.append((a, b))
                last = b
                break
    return _edit(text, spans, lambda span: "`" + span + "`")


def _name_index(names):
    index = {}
    for name in names:
        if not name:
            continue
        m = re.match(r"\w+(?:[-.]\w+)*", name)
        if not m or not name.startswith(m.group()):
            continue
        index.setdefault(m.group(), []).append(name)
    for group in index.values():
        group.sort(key=len, reverse=True)
    return index


Fixed = namedtuple("Fixed", "text old new tags")


def _same_structure(old, new):
    if _fence_open(old) != _fence_open(new):
        return False
    a, b = _comments(old), _comments(new)
    if a[1] != b[1] or (a[0] == old) != (b[0] == new):
        return False
    return ("<summary" in _mask_code(old).lower()) == ("<summary" in _mask_code(new).lower())


def _gap_line(line, exempt, summary):
    bare = line.removeprefix("\ufeff")
    flat = bare.strip()
    if flat in exempt or not flat.startswith("<") or len(bare) - len(bare.lstrip(" ")) >= 4 or bare.startswith("\t"):
        return False
    return bool(_HTML_ONLY.fullmatch(flat)) or (summary and "<summary" in _mask_code(flat).lower())


def _fixable(lines, kind, parts, exempt):
    joined = "\n".join(content for _, content, _ in parts)
    if "\\`" in joined or len(re.findall(r"`+", joined)) != 2 * len(_code_spans(joined)) or "|" in _mask_code(joined):
        return False
    for k, (no, content, col) in enumerate(parts):
        src = lines[no - 1]
        bare = src.removeprefix("\ufeff")
        flat = bare.strip()
        if col is None or not content or src[col:col + len(content)] != content or flat in exempt:
            return False
        if "-->" in src[:col] or "<!--" in src or content[0] in ">|" or content.startswith(("```", "~~~")) or _LIST.match(content):
            return False
        if k == 0:
            marker = _LIST.match(bare)
            if bare.startswith("\t") or len(bare) - len(bare.lstrip(" ")) >= 4 or _CHECKBOX_RE.match(flat) or marker and _TASK.match(bare[marker.end():].lstrip()):
                return False
        elif kind == "list" and (bare.startswith("\t") or len(bare) - len(bare.lstrip(" ")) >= 4):
            return False
    return True


def fix_text(text, profile=None, exempt=frozenset()):
    p = profile or {}
    raw = text.split("\n")
    crs = [l.endswith("\r") for l in raw[:-1]] + [False]
    lines = [l[:-1] if c else l for l, c in zip(raw, crs)]
    footer = p.get("footer")
    cn = p.get("code_names") or {}
    index = _name_index(list(cn.get("checks") or []) + list(cn.get("states") or []))
    quoted = bool(cn.get("quoted_tests"))
    changed = list(lines)
    blocks = _blocks(lines, footer)
    for kind, parts, _ in blocks:
        if kind in ("para", "list") and _fixable(lines, kind, parts, exempt):
            joined = "\n".join(content for _, content, _ in parts)
            out = _unwrap(joined)
            if quoted:
                out = _quoted_tests(out)
            if index:
                out = _wrap_names(out, index)
            pieces = out.split("\n")
            if out == joined or len(pieces) != len(parts):
                continue
            for (no, content, col), piece in zip(parts, pieces):
                src = lines[no - 1]
                edited = src[:col] + piece + src[col + len(content):]
                if piece != content and _same_structure(src, edited):
                    changed[no - 1] = edited
    gaps = _details_gaps(lines, list(_outside_code(lines)))
    before = {no for no, side in gaps if side == "before" and _gap_line(lines[no - 1], exempt, False)}
    after = {no for no, side in gaps if side == "after" and _gap_line(lines[no - 1], exempt, True)}
    new, ends, tags = [], [], []
    for i, line in enumerate(changed):
        if (i + 1) in before or i in after:
            new.append("")
            ends.append(crs[i - 1])
            tags.append(("+", None))
        new.append(line)
        ends.append(crs[i])
        tags.append(("=" if line == lines[i] else "~", i))
    if new != lines:
        shape = lambda b: [(kind, level, len(parts)) for kind, parts, level in b]
        if shape(_blocks(new, footer)) != shape(blocks):
            raise Refused(["the changes would alter how the draft is built, so furbish changed nothing"])
    joined = "\n".join(l + "\r" if c else l for l, c in zip(new, ends))
    return Fixed(joined, lines, new, tags)


_NO_NEWLINE = "\\ No newline at end of file"


def _hunks(old, new, tags, context=1):
    last = len(new) - 1 if new and new[-1] == "" and tags[-1][0] == "=" else len(new)
    no_newline = last == len(new)
    spans = []
    for k in range(last):
        if tags[k][0] != "=":
            a, b = max(0, k - context), min(last, k + context + 1)
            if spans and a <= spans[-1][1]:
                spans[-1][1] = b
            else:
                spans.append([a, b])
    seen = [0]
    for t, _ in tags:
        seen.append(seen[-1] + (t != "+"))
    out = []
    for a, b in spans:
        before = seen[a]
        count = seen[b] - seen[a]
        body, gone, came = [], [], []
        for k in range(a, b):
            tag, oi = tags[k]
            if tag == "=":
                body += ["-" + _plain(x) for x in gone] + ["+" + _plain(x) for x in came] + [" " + _plain(new[k])]
                gone, came = [], []
                if no_newline and k == last - 1:
                    body.append(_NO_NEWLINE)
                continue
            if tag == "~":
                gone.append(old[oi])
            came.append(new[k])
        tail = [_NO_NEWLINE] if no_newline and b == last else []
        body += ["-" + _plain(x) for x in gone] + (tail if gone else []) + ["+" + _plain(x) for x in came] + (tail if came else [])
        out.append(f"@@ -{before + 1 if count else before},{count} +{a + 1},{b - a} @@")
        out += body
    return out


_BREAK = re.compile(r"; +| [\u2014\u2013-] +|, +(?=(?:and|but|so|or|yet) )")
_MARKUP = re.compile(r"[()]|\*+|~~|(?<!\w)_+(?=\S)|(?<=\S)_+(?!\w)")
_ENTITY = re.compile(r"&#?\w+$")
_PLAIN_WORD = re.compile(r"[a-z]+(?![\w./:@-])")
_SPLIT_MAX = 2000
_SPLIT_TRIES = 6
Suggestion = namedtuple("Suggestion", "line sid grade first second grades")


def _breaks(text):
    s = _shield(text)
    if '"' in s or "\u201c" in s or "\u201d" in s:
        return []
    end = len(text.rstrip())
    events = [(m.start(), m.group()[0]) for m in _MARKUP.finditer(s)]
    out = []
    k = depth = 0
    runs = {"*": 0, "~": 0, "_": 0}
    lead = False
    pos = 0
    for m in _BREAK.finditer(s):
        a, b = m.span()
        while k < len(events) and events[k][0] < a:
            c = events[k][1]
            if c == "(":
                depth += 1
            elif c == ")":
                depth = max(0, depth - 1)
            else:
                runs[c] += 1
            k += 1
        lead = lead or bool(text[pos:a].strip())
        pos = a
        if lead and b < end and depth == 0 and all(v % 2 == 0 for v in runs.values()) and not (text[a] == ";" and _ENTITY.search(text, max(0, a - 12), a)):
            out.append((a, b))
    return out


def _half(text):
    cleaned = _cleaned(text)
    return ari(cleaned) if _count(cleaned)[0] >= 3 else None


def split_suggestions(text, profile=None, exempt=frozenset()):
    p = profile or {}
    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    for s, grade in _hard(lines, _sentences(lines, p.get("footer")), exempt, _grade_skip(p)):
        if len(s.text) > _SPLIT_MAX:
            continue
        middle = len(s.text) / 2
        marks = sorted(_breaks(s.text), key=lambda m: abs(m[0] - middle))[:_SPLIT_TRIES]
        best = None
        for a, b in marks:
            right = s.text[b:]
            if right[:1].islower() and not _PLAIN_WORD.match(right) and not _starts_id(right, 0):
                continue
            gl, gr = _half(s.text[:a]), _half(right)
            if gl is None or gr is None or round(gl) >= round(grade) or round(gr) >= round(grade):
                continue
            if best is None or max(gl, gr) < max(best[2]):
                best = (a, b, (gl, gr))
        if best:
            a, b, grades = best
            first = s.text[:a].rstrip(" ,;:")
            right = s.text[b:]
            out.append(Suggestion(s.line, s.id, grade, first if first.endswith((".", "!", "?", "\u2026")) else first + ".", right[:1].upper() + right[1:] if _PLAIN_WORD.match(right) else right, grades))
    return out


def _read_text(path, strict=False):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e.strerror or e}") from None
    try:
        return data.decode("utf-8", errors="strict" if strict else "replace")
    except UnicodeDecodeError:
        raise ConfigError(f"{path} is not UTF-8 text, so furbish will not rewrite it") from None


def _template_lines(profile):
    lines = set()
    for key in ("pr_template", "issue_template"):
        path = profile.get(key) if profile else None
        if path:
            try:
                body = _read_text(path)
            except ConfigError as e:
                raise ConfigError(f"{key} in the config: {e}") from None
            lines.update(l.strip() for l in body.removeprefix("\ufeff").replace("\r\n", "\n").split("\n") if l.strip())
    return frozenset(lines)


_CONTROL = re.compile("[\x00-\x08\x0a-\x1f\x7f-\x9f\u061c\u200e\u200f\u2028-\u202e\u2066-\u2069\ud800-\udfff]")


def _plain(text):
    return _CONTROL.sub("?", text)


def _run_check(args):
    try:
        path = find_config(os.environ)
        config = load_config(path) if path else None
        profile = pick_profile(config, args.repo, args.kind)
        exempt = _template_lines(profile)
        text = _read_text(args.draft)
        problems = check(text, profile, args.post, exempt)
        if profile:
            problems += run_external(profile["external"], os.path.abspath(args.draft))
    except ConfigError as e:
        print(f"furbish: {_plain(str(e))}", file=sys.stderr)
        return 2
    problems.sort(key=lambda p: p.line)
    said = {}
    if args.text:
        lines = text.replace("\r\n", "\n").split("\n")
        said = {x.sentence.id: x.sentence.text for x in _sentences(lines, (profile or {}).get("footer"))}
    for p in problems:
        shown = _plain(args.draft)
        where = f"{shown}:{p.line}: " if p.line else f"{shown}: "
        sid = f"{p.sid}: " if p.sid else ""
        print(f"{where}{sid}{_plain(p.message)}")
        if p.sid in said:
            print(f"    {_plain(said[p.sid])}")
    return 1 if problems else 0


def _write_text(path, text):
    real = os.path.realpath(path)
    try:
        info = os.stat(real)
        if not os.access(real, os.W_OK):
            raise ConfigError(f"{path} is read-only, so furbish will not change it")
        if info.st_nlink > 1:
            raise ConfigError(f"{path} has more than one name (a hard link), and replacing it would leave the other names with the old text, so furbish will not change it")
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(real), prefix=".furbish-")
    except OSError as e:
        raise ConfigError(f"cannot write {path}: {e.strerror or e}") from None
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(text.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        shutil.copymode(real, tmp)
        os.replace(tmp, real)
    except (OSError, ValueError) as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise ConfigError(f"cannot write {path}: {getattr(e, 'strerror', None) or e}") from None


def _run_set(args):
    shown = _plain(args.draft)
    try:
        path = find_config(os.environ)
        config = load_config(path) if path else None
        profile = pick_profile(config, args.repo, args.kind)
        text = _read_text(args.draft, True)
        edit = set_sentence(text, args.sid, args.text, profile)
        if edit.text != text and args.write:
            _write_text(args.draft, edit.text)
    except Refused as e:
        where = f"{shown}:{e.line}: " if e.line else f"{shown}: "
        for reason in e.reasons:
            print(f"{where}{e.sid}: {_plain(reason)}", file=sys.stderr)
        return 1
    except ConfigError as e:
        print(f"furbish: {_plain(str(e))}", file=sys.stderr)
        return 2
    if edit.text == text:
        print("furbish: that sentence already reads that way, so nothing changed", file=sys.stderr)
        return 0
    print(f"--- {shown}\n+++ {shown}\n@@ -{edit.first},{len(edit.old)} +{edit.first},1 @@")
    unterminated = not text.endswith("\n") and edit.first + len(edit.old) - 1 == text.count("\n") + 1
    for l in edit.old:
        print("-" + _plain(l))
    if unterminated:
        print(_NO_NEWLINE)
    print("+" + _plain(edit.new))
    if unterminated:
        print(_NO_NEWLINE)
    if not args.write:
        print("furbish: nothing was written; add --write to change the file", file=sys.stderr)
    return 0


def _run_fix(args):
    shown = _plain(args.draft)
    try:
        path = find_config(os.environ)
        config = load_config(path) if path else None
        profile = pick_profile(config, args.repo, args.kind)
        exempt = _template_lines(profile)
        text = _read_text(args.draft, True)
        fixed = fix_text(text, profile, exempt)
        if fixed.text != text and args.write:
            _write_text(args.draft, fixed.text)
    except Refused as e:
        for reason in e.reasons:
            print(f"{shown}: {_plain(reason)}", file=sys.stderr)
        return 1
    except ConfigError as e:
        print(f"furbish: {_plain(str(e))}", file=sys.stderr)
        return 2
    if fixed.text == text:
        return 0
    print(f"--- {shown}\n+++ {shown}")
    for row in _hunks(fixed.old, fixed.new, fixed.tags):
        print(row)
    if not args.write:
        print("furbish: nothing was written; add --write to change the file", file=sys.stderr)
    return 0


def _run_split(args):
    try:
        path = find_config(os.environ)
        config = load_config(path) if path else None
        profile = pick_profile(config, args.repo, args.kind)
        exempt = _template_lines(profile)
        found = split_suggestions(_read_text(args.draft), profile, exempt)
    except ConfigError as e:
        print(f"furbish: {_plain(str(e))}", file=sys.stderr)
        return 2
    shown = _plain(args.draft)
    for x in found:
        print(f"{shown}:{x.line}: {x.sid}: reading grade {round(x.grade)}. As two sentences it would read at grade {round(x.grades[0])} and {round(x.grades[1])}:")
        print(f"    {_plain(x.first)}")
        print(f"    {_plain(x.second)}")
    return 0


def main():
    argv = sys.argv[1:]
    ap = argparse.ArgumentParser(prog="furbish", description="Checks and tidies GitHub PR and issue drafts before they're posted: plain words, house rules, safe fixes. Script-first and offline.")
    ap.add_argument("--version", action="version", version=f"furbish {__version__}")
    sub = ap.add_subparsers(dest="command", metavar="command")
    ck = sub.add_parser("check", help="print only the problems in a draft, with line and sentence id", description="Prints only the problems in a draft, one per line as path:line: message, and nothing at all when the draft passes. Exits 0 when it passes, 1 when it finds problems and 2 when it cannot run.")
    ck.add_argument("draft", help="the draft file to check")
    ck.add_argument("--repo", metavar="OWNER/NAME", help="the repo profile from the config file to use; without it, default_repo is used")
    ck.add_argument("--kind", metavar="NAME", help="a kind inside the repo profile, such as tracker; it overrides only the keys it names")
    ck.add_argument("--post", action="store_true", help="also grade the reading level, as you would just before a post goes up")
    ck.add_argument("--text", action="store_true", help="print each flagged sentence, indented, under its problem")
    st = sub.add_parser("set", help="replace one sentence by its id", description="Replaces one sentence of a draft, found by the id that furbish check prints (S12). The new sentence must keep every number, commit sha and inline-code span of the old one, and under a heading from keep_negation it must keep its negation. Prints the change as a diff, and writes the file only with --write. Exits 0 on success, 1 when the new sentence is refused and 2 when it cannot run.")
    st.add_argument("draft", help="the draft file to change")
    st.add_argument("sid", metavar="ID", help="the sentence id, for example S12")
    st.add_argument("text", help="the new sentence, as one line; if it starts with a dash, put -- before it, and put any option such as --write before the --")
    st.add_argument("--repo", metavar="OWNER/NAME", help="the repo profile from the config file to use; without it, default_repo is used")
    st.add_argument("--kind", metavar="NAME", help="a kind inside the repo profile, such as tracker; it overrides only the keys it names")
    st.add_argument("--write", action="store_true", help="change the file; without it nothing is written")
    fi = sub.add_parser("fix", help="make the safe mechanical edits to a draft", description="Makes the safe mechanical edits to the prose of a draft: takes the backticks off a lone commit sha or URL, puts a blank line inside <details> where GitHub needs one, and, if the repo profile has code_names, turns quoted test names, CI check names and CI states into inline code. It never touches code blocks, comments, tables, quotes, link text, headings, checkboxes, template lines or the footer. Prints the changes as a diff, and writes the file only with --write. Exits 0 when it is done (and prints nothing when there is nothing to fix), 1 when it refuses to change a draft and 2 when it cannot run.")
    fi.add_argument("draft", help="the draft file to change")
    fi.add_argument("--repo", metavar="OWNER/NAME", help="the repo profile from the config file to use; without it, default_repo is used")
    fi.add_argument("--kind", metavar="NAME", help="a kind inside the repo profile, such as tracker; it overrides only the keys it names")
    fi.add_argument("--write", action="store_true", help="change the file; without it nothing is written")
    sp = sub.add_parser("split", help="suggest where a hard sentence could be cut in two", description="Looks at every sentence that reads at grade 10 or harder (the sentences check --post flags) and, where cutting it at a semicolon, a spaced dash or a comma before and, but, so, or or yet gives two sentences that both read easier, prints the sentence id and the two sentences. It only suggests: it never changes the draft, so apply a suggestion with furbish set. It looks only in plain prose, never inside code, links, URLs or quotes, and skips a sentence over 2,000 characters. Prints nothing when it has no suggestion. Exits 0, or 2 when it cannot run.")
    sp.add_argument("draft", help="the draft file to look at")
    sp.add_argument("--repo", metavar="OWNER/NAME", help="the repo profile from the config file to use; without it, default_repo is used")
    sp.add_argument("--kind", metavar="NAME", help="a kind inside the repo profile, such as tracker; it overrides only the keys it names")
    if not argv:
        ap.print_help(sys.stderr)
        return 2
    args = ap.parse_args(argv)
    if args.command == "check":
        return _run_check(args)
    if args.command == "set":
        return _run_set(args)
    if args.command == "fix":
        return _run_fix(args)
    if args.command == "split":
        return _run_split(args)
    return 0


if __name__ == "__main__":
    try:
        code = main()
        sys.stdout.flush()
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        code = 0
    sys.exit(code)
