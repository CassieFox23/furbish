import importlib.util, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "furbish.py")
DRAFTS = os.path.join(HERE, "drafts")
FOOTER = r"^-- Sent from the made-up example footer$"

spec = importlib.util.spec_from_file_location("furbish", SCRIPT)
furbish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(furbish)


def run(*args):
    return subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True, text=True)


def texts(draft, footer=None):
    return [s.text for s in furbish.read_prose(draft, footer)]


def lines(draft, footer=None):
    return [s.line for s in furbish.read_prose(draft, footer)]


class TestCli(unittest.TestCase):
    def test_version(self):
        r = run("--version")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "furbish 0.1.0.dev0")

    def test_no_args_exits_2(self):
        r = run()
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage: furbish", r.stderr)


class TestAri(unittest.TestCase):
    def test_short_sentence(self):
        self.assertAlmostEqual(furbish.ari("The cat sat on the mat."), -5.085, places=3)

    def test_punctuation_is_not_counted(self):
        self.assertAlmostEqual(furbish.ari("Run before you push."), -0.59, places=3)

    def test_no_words_is_zero(self):
        self.assertEqual(furbish.ari(""), 0.0)
        self.assertEqual(furbish.ari("-- ..."), 0.0)


class TestReadProse(unittest.TestCase):
    def test_plain_sentences_get_ids_and_lines(self):
        s = furbish.read_prose("This is a plain sentence. Here is another one!\n\nIs this a question? Yes it is.\n")
        self.assertEqual([x.id for x in s], ["S1", "S2", "S3", "S4"])
        self.assertEqual([x.text for x in s], ["This is a plain sentence.", "Here is another one!", "Is this a question?", "Yes it is."])
        self.assertEqual([x.line for x in s], [1, 1, 3, 3])

    def test_fenced_code_is_skipped(self):
        d = 'Before the code.\n\n```python\nprint("Not prose. At all.")\n```\n\nAfter the code.\n'
        self.assertEqual(texts(d), ["Before the code.", "After the code."])
        self.assertEqual(lines(d), [1, 7])

    def test_tilde_and_long_fences_are_skipped(self):
        d = "One.\n\n~~~\nNot prose. At all.\n~~~\n\nTwo.\n\n````\nNot prose. ```still code```\n````\n\nThree.\n"
        self.assertEqual(texts(d), ["One.", "Two.", "Three."])

    def test_inline_code_stays_in_text_but_not_in_grade(self):
        s = furbish.read_prose("Run `make test` before you push. The `--flag` option is new.")
        self.assertEqual([x.text for x in s], ["Run `make test` before you push.", "The `--flag` option is new."])
        self.assertEqual(furbish._cleaned(s[0].text), "Run code before you push.")
        self.assertEqual(furbish._cleaned(s[1].text), "The code option is new.")

    def test_sentence_of_only_inline_code_is_not_numbered(self):
        s = furbish.read_prose("- `make test`\n- Real sentence.\n")
        self.assertEqual([(x.id, x.text) for x in s], [("S1", "Real sentence.")])

    def test_table_rows_are_skipped(self):
        d = "Results below.\n\n| name | result |\n|---|---|\n| a | pass. fine. |\n\nDone here.\n"
        self.assertEqual(texts(d), ["Results below.", "Done here."])
        self.assertEqual(lines(d), [1, 7])

    def test_details_summary_is_skipped_but_body_is_read(self):
        d = "Intro sentence.\n\n<details>\n<summary>Long log output</summary>\n\nBody sentence one.\n\n</details>\n"
        self.assertEqual(texts(d), ["Intro sentence.", "Body sentence one."])
        self.assertEqual(lines(d), [1, 6])

    def test_footer_is_skipped(self):
        d = "Main sentence here.\n\n-- Sent from the made-up example footer\n"
        self.assertEqual(texts(d, FOOTER), ["Main sentence here."])

    def test_headings_lists_and_quotes_are_sentences_without_their_markers(self):
        d = "## What changed\n\n- Added the reader\n- Fixed the tests.\n\n> Quoted line here.\n\n1. First step\n2. Second step\n"
        self.assertEqual(texts(d), ["What changed", "Added the reader", "Fixed the tests.", "Quoted line here.", "First step", "Second step"])
        self.assertEqual(lines(d), [1, 3, 4, 6, 8, 9])

    def test_abbreviations_versions_and_decimals_do_not_split(self):
        d = "Use e.g. the new flag, i.e. this one. Version 1.2.3 is out. It costs 3.14 units."
        self.assertEqual(texts(d), ["Use e.g. the new flag, i.e. this one.", "Version 1.2.3 is out.", "It costs 3.14 units."])

    def test_wrapped_paragraph_is_one_sentence_starting_on_its_first_line(self):
        d = "This sentence wraps\nacross two lines. Next one."
        self.assertEqual(texts(d), ["This sentence wraps across two lines.", "Next one."])
        self.assertEqual(lines(d), [1, 2])

    def test_link_url_and_bare_url_are_not_graded(self):
        s = furbish.read_prose("See [the guide](https://example.com/guide) for details. Visit https://example.com/a/b now.")
        self.assertEqual(s[0].text, "See [the guide](https://example.com/guide) for details.")
        self.assertEqual(furbish._cleaned(s[0].text), "See the guide for details.")
        self.assertEqual(furbish._cleaned(s[1].text), "Visit link now.")

    def test_html_comments_are_skipped_even_when_they_wrap(self):
        d = "Keep.\n\n<!-- hidden. text -->\n\n<!--\nalso hidden. text\n-->\n\nAlso keep.\n"
        self.assertEqual(texts(d), ["Keep.", "Also keep."])
        self.assertEqual(lines(d), [1, 9])

    def test_comment_and_summary_markers_inside_inline_code_are_prose(self):
        d = "Use `<!--` to open a comment.\n\nNext paragraph here."
        self.assertEqual(texts(d), ["Use `<!--` to open a comment.", "Next paragraph here."])
        self.assertEqual(lines(d), [1, 3])
        d = "Use `<summary>` for titles.\n\nMore text here."
        self.assertEqual(texts(d), ["Use `<summary>` for titles.", "More text here."])
        self.assertEqual(lines(d), [1, 3])

    def test_prose_beside_a_comment_is_kept(self):
        self.assertEqual(texts("Fix the crash. <!-- reviewer note -->"), ["Fix the crash."])
        self.assertEqual(texts("<!-- note --> Fix the crash."), ["Fix the crash."])
        d = "<!--\nnote\n--> Fix the crash.\n"
        self.assertEqual(texts(d), ["Fix the crash."])
        self.assertEqual(lines(d), [3])

    def test_punctuation_after_a_bare_url_is_not_part_of_it(self):
        self.assertEqual(texts("See https://example.com. Then run it."), ["See https://example.com.", "Then run it."])
        self.assertEqual(texts("(see https://x.com). Next one."), ["(see https://x.com).", "Next one."])
        self.assertEqual(texts("Read https://example.com/a.b/c now."), ["Read https://example.com/a.b/c now."])

    def test_a_less_than_sign_is_not_a_tag_unless_a_tag_follows(self):
        s = furbish.read_prose("if a < b and b > c then stop. A <b>bold</b> move.")
        self.assertEqual(furbish._cleaned(s[0].text), "if a < b and b > c then stop.")
        self.assertEqual(furbish._cleaned(s[1].text), "A bold move.")

    def test_crlf_line_endings(self):
        s = furbish.read_prose("Main one.\r\n\r\nNext one.\r\n\r\n-- Sent from the made-up example footer\r\n", FOOTER)
        self.assertEqual([(x.text, x.line) for x in s], [("Main one.", 1), ("Next one.", 3)])

    def test_a_one_line_code_span_is_not_a_fence(self):
        self.assertEqual(texts("```npm test```\n\nSee it here.\n"), ["See it here."])
        self.assertEqual(texts("```python\nx. Y.\n```\nAfter it.\n"), ["After it."])

    def test_same_draft_gives_same_result(self):
        d = "One. Two.\n\n```\nthree\n```\n"
        self.assertEqual(furbish.read_prose(d), furbish.read_prose(d))


class TestHostileText(unittest.TestCase):
    def test_openers_without_closers_stay_fast(self):
        cases = ["a" + "`" * 200000, "[a" * 100000, "[a](" * 60000, "<a " * 80000, "<" * 100000, ">" * 262000, "`a b " * 40000]
        for d in cases:
            t = time.perf_counter()
            furbish.read_prose(d)
            self.assertLess(time.perf_counter() - t, 2.0, d[:12])


class TestMadeUpDrafts(unittest.TestCase):
    def load(self, name):
        with open(os.path.join(DRAFTS, name), encoding="utf-8") as f:
            return f.read()

    def check_draft(self, name):
        s = furbish.read_prose(self.load(name), FOOTER)
        self.assertGreater(len(s), 5)
        self.assertEqual([x.id for x in s], [f"S{i}" for i in range(1, len(s) + 1)])
        for x in s:
            self.assertNotIn("CANARY_CODE", x.text)
            self.assertNotIn("Sent from", x.text)
            self.assertFalse(x.text.startswith(("|", "#", ">", "-", "`", "~", "<")), x.text)
            self.assertGreaterEqual(x.line, 1)
        self.assertEqual([x.line for x in s], sorted(x.line for x in s))
        return s

    def test_pr_body(self):
        s = self.check_draft("pr-body.md")
        t = [x.text for x in s]
        self.assertIn("Added type hints to all public functions in the main package", t)
        self.assertIn("Fixed a minor logging issue in the error handler", t)
        self.assertIn("The automated build process completed successfully after the third retry attempt.", t)
        self.assertNotIn("CANARY_CODE long log", t)
        p = next(x for x in s if x.text.startswith("Please review"))
        self.assertEqual(furbish._cleaned(p.text), "Please review the code variable usage in the test scripts before deploying.")

    def test_issue_body(self):
        s = self.check_draft("issue-body.md")
        t = [x.text for x in s]
        self.assertIn("The issue seems to be related to memory allocation, e.g., version 2.4.1 shows a latency of 0.75ms under normal conditions.", t)
        self.assertIn("Error: CRITICAL_FAILURE detected in module handler", t)
        self.assertEqual(t.count("Open the application in a standard browser window."), 1)


EXAMPLE = '''default_repo = "example-org/example"

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
'''


class ConfigCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def write(self, text, name="config.toml"):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def load(self, text):
        return furbish.load_config(self.write(text))

    def bad(self, text, *words):
        path = self.write(text)
        with self.assertRaises(furbish.ConfigError) as cm:
            furbish.load_config(path)
        msg = str(cm.exception)
        self.assertIn(path, msg)
        for w in words:
            self.assertIn(w, msg)


class TestFindConfig(ConfigCase):
    def test_nothing_set_and_no_file_gives_none(self):
        self.assertIsNone(furbish.find_config({"HOME": self.tmp}))

    def test_furbish_config_wins(self):
        a = self.write("", "a.toml")
        self.write("", "xdg/furbish/config.toml")
        self.write("", "home/.config/furbish/config.toml")
        env = {"FURBISH_CONFIG": a, "XDG_CONFIG_HOME": os.path.join(self.tmp, "xdg"), "HOME": os.path.join(self.tmp, "home")}
        self.assertEqual(furbish.find_config(env), a)

    def test_xdg_comes_before_home(self):
        x = self.write("", "xdg/furbish/config.toml")
        self.write("", "home/.config/furbish/config.toml")
        env = {"XDG_CONFIG_HOME": os.path.join(self.tmp, "xdg"), "HOME": os.path.join(self.tmp, "home")}
        self.assertEqual(furbish.find_config(env), x)

    def test_home_is_the_last_stop(self):
        h = self.write("", "home/.config/furbish/config.toml")
        env = {"XDG_CONFIG_HOME": os.path.join(self.tmp, "xdg"), "HOME": os.path.join(self.tmp, "home")}
        self.assertEqual(furbish.find_config(env), h)

    def test_empty_variables_count_as_unset(self):
        h = self.write("", "home/.config/furbish/config.toml")
        env = {"FURBISH_CONFIG": "", "XDG_CONFIG_HOME": "", "HOME": os.path.join(self.tmp, "home")}
        self.assertEqual(furbish.find_config(env), h)

    def test_furbish_config_pointing_nowhere_is_an_error(self):
        missing = os.path.join(self.tmp, "nope.toml")
        with self.assertRaises(furbish.ConfigError) as cm:
            furbish.find_config({"FURBISH_CONFIG": missing, "HOME": self.tmp})
        self.assertIn("FURBISH_CONFIG", str(cm.exception))
        self.assertIn(missing, str(cm.exception))


class TestLoadConfig(ConfigCase):
    def test_empty_file(self):
        self.assertEqual(self.load(""), {"default_repo": None, "repo": {}})

    def test_the_example_in_config_md(self):
        c = self.load(EXAMPLE)
        self.assertEqual(c["default_repo"], "example-org/example")
        p = c["repo"]["example-org/example"]
        self.assertEqual(p["pr_template"], "/path/to/example/pull_request_template.md")
        self.assertEqual(p["issue_template"], "/path/to/example/issue_template.md")
        self.assertEqual(p["first_line_prefix"], "Example:")
        self.assertEqual(p["footer"], "^-- Sent from the made-up example footer$")
        self.assertEqual((p["tldr"], p["tldr_words"], p["tldr_max_sentences"]), ("required", 100, 3))
        self.assertEqual(p["banned"], ["circle back", "synergy"])
        self.assertEqual(p["private"], ["/home/", "/Users/", "example-hostname"])
        self.assertEqual(p["keep_negation"], ["Not run"])
        self.assertEqual(p["code_names"], {"quoted_tests": True, "checks": ["Example lint", "Example unit tests"], "states": ["passed", "failed", "skipped"]})
        self.assertEqual(p["external"], [
            {"name": "example-lines", "mode": "lines", "command": ["example-checker", "--plain"], "fail": "^FAIL"},
            {"name": "example-json", "mode": "json", "command": ["example-json-checker"], "fail": None},
        ])

    def test_omitted_keys_get_plain_defaults(self):
        p = self.load('[repo."a/b"]\n')["repo"]["a/b"]
        self.assertEqual(p, {
            "pr_template": None, "issue_template": None, "first_line_prefix": None, "first_line_skip": None, "footer": None,
            "tldr": "off", "tldr_words": None, "tldr_max_sentences": None,
            "banned": [], "private": [], "keep_negation": [],
            "code_names": {"quoted_tests": False, "checks": [], "states": []},
            "external": [],
            "grade_skip": [], "kinds": {},
        })

    def test_template_paths_expand_a_home_folder(self):
        p = self.load('[repo."a/b"]\npr_template = "~/t.md"\n')["repo"]["a/b"]
        self.assertEqual(p["pr_template"], os.path.expanduser("~/t.md"))

    def test_broken_toml_names_the_file(self):
        self.bad("this is = = not toml")

    def test_unknown_top_level_key(self):
        self.bad('default_repo = "a/b"\nflavour = "x"\n[repo."a/b"]\n', "flavour")

    def test_unknown_profile_key_names_key_and_repo(self):
        self.bad('[repo."a/b"]\nbaned = ["x"]\n', "baned", "a/b")

    def test_unknown_code_names_key(self):
        self.bad('[repo."a/b".code_names]\nquoted = true\n', "quoted")

    def test_repo_name_must_be_owner_slash_name(self):
        self.bad('[repo."justaname"]\n', "justaname")
        self.bad('[repo."a/b/c"]\n', "a/b/c")

    def test_default_repo_must_have_a_profile(self):
        self.bad('default_repo = "a/b"\n[repo."c/d"]\n', "a/b")
        self.bad('default_repo = "a/b"\n', "a/b")

    def test_wrong_types(self):
        self.bad('[repo."a/b"]\ntldr_words = "100"\n', "tldr_words", "a/b")
        self.bad('[repo."a/b"]\ntldr_words = 0\n', "tldr_words")
        self.bad('[repo."a/b"]\ntldr_words = true\n', "tldr_words")
        self.bad('[repo."a/b"]\nbanned = "x"\n', "banned")
        self.bad('[repo."a/b"]\nbanned = ["x", 3]\n', "banned")
        self.bad('[repo."a/b"]\nbanned = [""]\n', "banned")
        self.bad('[repo."a/b"]\nfooter = 5\n', "footer")
        self.bad('[repo."a/b".code_names]\nquoted_tests = "yes"\n', "quoted_tests")
        self.bad('[repo."a/b"]\nfirst_line_prefix = ""\n', "first_line_prefix")

    def test_footer_and_fail_must_be_real_regexes(self):
        self.bad('[repo."a/b"]\nfooter = "(unclosed"\n', "footer")
        self.bad('[repo."a/b"]\n[[repo."a/b".external]]\nname = "x"\nmode = "lines"\ncommand = ["c"]\nfail = "[bad"\n', "fail")

    def test_a_regex_that_cannot_be_built_is_an_error_not_a_crash(self):
        self.bad('[repo."a/b"]\nfooter = "a{99999999999999999999}"\n', "footer")
        self.bad('[repo."a/b"]\nfooter = "' + "(" * 5000 + ")" * 5000 + '"\n', "footer")
        self.bad('[repo."a/b"]\n[[repo."a/b".external]]\nname = "x"\nmode = "lines"\ncommand = ["c"]\nfail = "a{99999999999999999999}"\n', "fail")

    def test_a_file_nested_too_deep_is_an_error_not_a_crash(self):
        self.bad("a = " + "[" * 5000 + "]" * 5000 + "\n", "too deep")

    def test_an_empty_fail_pattern_is_an_error(self):
        self.bad('[repo."a/b"]\n[[repo."a/b".external]]\nname = "x"\nmode = "lines"\ncommand = ["c"]\nfail = ""\n', "fail")

    def test_tldr_values(self):
        self.bad('[repo."a/b"]\ntldr = "sometimes"\n', "tldr")
        self.bad('[repo."a/b"]\ntldr = "required"\ntldr_max_sentences = 3\n', "tldr_words")
        self.bad('[repo."a/b"]\ntldr = "required"\ntldr_words = 100\n', "tldr_max_sentences")
        p = self.load('[repo."a/b"]\ntldr = "off"\n')["repo"]["a/b"]
        self.assertEqual(p["tldr"], "off")

    def test_external_checker_rules(self):
        head = '[repo."a/b"]\n[[repo."a/b".external]]\n'
        self.bad(head + 'name = "x"\nmode = "other"\ncommand = ["c"]\n', "mode")
        self.bad(head + 'name = "x"\nmode = "lines"\ncommand = ["c"]\n', "fail")
        self.bad(head + 'name = "x"\nmode = "json"\ncommand = ["c"]\nfail = "^F"\n', "fail")
        self.bad(head + 'name = "x"\nmode = "json"\ncommand = []\n', "command")
        self.bad(head + 'name = "x"\nmode = "json"\n', "command")
        self.bad(head + 'mode = "json"\ncommand = ["c"]\n', "name")
        self.bad(head + 'name = "x"\nmode = "json"\ncommand = ["c"]\nextra = 1\n', "extra")
        self.bad(head + 'name = "dup-name"\nmode = "json"\ncommand = ["c"]\n[[repo."a/b".external]]\nname = "dup-name"\nmode = "json"\ncommand = ["d"]\n', "dup-name")

    def test_grade_skip_must_be_a_list_of_working_regexes(self):
        self.assertEqual(self.load('[repo."a/b"]\ngrade_skip = ["^Legacy note:"]\n')["repo"]["a/b"]["grade_skip"], ["^Legacy note:"])
        self.bad('[repo."a/b"]\ngrade_skip = "^Legacy"\n', "grade_skip", "a/b")
        self.bad('[repo."a/b"]\ngrade_skip = [""]\n', "grade_skip")
        self.bad('[repo."a/b"]\ngrade_skip = ["(unclosed"]\n', "grade_skip", "(unclosed")
        self.bad('[repo."a/b"]\ngrade_skip = ["a{99999999999999999999}"]\n', "grade_skip")

    def test_loading_twice_gives_equal_results(self):
        path = self.write(EXAMPLE)
        self.assertEqual(furbish.load_config(path), furbish.load_config(path))


class TestPickProfile(ConfigCase):
    def test_explicit_repo_wins_over_default(self):
        c = self.load('default_repo = "a/b"\n[repo."a/b"]\nbanned = ["one"]\n[repo."c/d"]\nbanned = ["two"]\n')
        self.assertEqual(furbish.pick_profile(c, "c/d")["banned"], ["two"])

    def test_default_repo_is_used_when_none_is_given(self):
        c = self.load('default_repo = "a/b"\n[repo."a/b"]\nbanned = ["one"]\n')
        self.assertEqual(furbish.pick_profile(c, None)["banned"], ["one"])

    def test_no_repo_and_no_default_means_no_profile(self):
        self.assertIsNone(furbish.pick_profile(self.load('[repo."a/b"]\n'), None))
        self.assertIsNone(furbish.pick_profile(None, None))

    def test_unknown_repo_lists_the_known_ones(self):
        c = self.load('[repo."a/b"]\n[repo."c/d"]\n')
        with self.assertRaises(furbish.ConfigError) as cm:
            furbish.pick_profile(c, "x/y")
        msg = str(cm.exception)
        for w in ("x/y", "a/b", "c/d"):
            self.assertIn(w, msg)

    def test_a_repo_without_any_config_file_is_an_error(self):
        with self.assertRaises(furbish.ConfigError) as cm:
            furbish.pick_profile(None, "x/y")
        self.assertIn("x/y", str(cm.exception))


class TestKinds(ConfigCase):
    BASE = '[repo."a/b"]\ntldr = "required"\ntldr_words = 100\ntldr_max_sentences = 3\nprivate = ["secret-host"]\n'

    def test_a_kind_switches_the_tldr_rule_off_and_the_repo_keeps_it(self):
        c = self.load(self.BASE + '[repo."a/b".kinds.release]\ntldr = "off"\n')
        long_post = words(120) + "\n"
        self.assertEqual(probs(long_post, furbish.pick_profile(c, "a/b")), [(1, "tldr")])
        self.assertEqual(probs(long_post, furbish.pick_profile(c, "a/b", "release")), [])
        kind = furbish.pick_profile(c, "a/b", "release")
        self.assertEqual((kind["tldr"], kind["tldr_words"], kind["tldr_max_sentences"]), ("off", 100, 3))

    def test_a_kind_inherits_private_from_the_repo(self):
        c = self.load(self.BASE + '[repo."a/b".kinds.release]\ntldr = "off"\n')
        kind = furbish.pick_profile(c, "a/b", "release")
        self.assertEqual(kind["private"], ["secret-host"])
        self.assertEqual(probs("Host secret-host here.\n", kind), [(1, "private")])

    def test_an_unknown_key_in_a_kind_names_the_kind(self):
        self.bad(self.BASE + '[repo."a/b".kinds.release]\nbaned = ["x"]\n', "baned", "a/b", "release")

    def test_a_kind_cannot_hold_kinds(self):
        self.bad(self.BASE + '[repo."a/b".kinds.release]\nkinds = {}\n', "kinds", "release")

    def test_a_bad_kind_name_is_refused(self):
        for raw in ("bad name", "-x", "a.b", "ü", "release\\n"):
            self.bad(f'[repo."a/b".kinds."{raw}"]\n', "must be letters, digits, - or _", "a/b")

    def test_kinds_and_each_kind_must_be_tables(self):
        self.bad('[repo."a/b"]\nkinds = "release"\n', "kinds", "a/b")
        self.bad('[repo."a/b"]\nkinds = { release = "off" }\n', "release", "must be a table")

    def test_a_missing_kind_lists_the_known_ones(self):
        c = self.load(self.BASE + '[repo."a/b".kinds.release]\ntldr = "off"\n[repo."a/b".kinds.tracker]\ntldr = "off"\n')
        with self.assertRaises(furbish.ConfigError) as cm:
            furbish.pick_profile(c, "a/b", "nope")
        self.assertEqual(str(cm.exception), "the profile for a/b has no kind nope; it has: release, tracker")
        plain = self.load('[repo."a/b"]\n')
        with self.assertRaises(furbish.ConfigError) as cm:
            furbish.pick_profile(plain, "a/b", "nope")
        self.assertEqual(str(cm.exception), "the profile for a/b has no kind nope; it has: none")

    def test_a_kind_needs_a_repo_or_a_default_repo(self):
        c = self.load('[repo."a/b".kinds.release]\ntldr = "off"\n')
        with self.assertRaises(furbish.ConfigError) as cm:
            furbish.pick_profile(c, None, "release")
        self.assertEqual(str(cm.exception), "a kind needs a repo profile: pass --repo or set default_repo")
        for repo in (None, "a/b"):
            with self.assertRaises(furbish.ConfigError) as cm:
                furbish.pick_profile(None, repo, "release")
            self.assertEqual(str(cm.exception), "no config file was found, so there is no kind release")
        d = self.load('default_repo = "a/b"\n[repo."a/b".kinds.release]\ntldr = "off"\n')
        self.assertEqual(furbish.pick_profile(d, None, "release")["tldr"], "off")


HARD = "Unquestionably, the implementation's architectural characteristics necessitate comprehensive reconsideration."
EASY = "Run the tests before you push."


def prof(**kw):
    p = {
        "pr_template": None, "issue_template": None, "first_line_prefix": None, "first_line_skip": None, "footer": None,
        "tldr": "off", "tldr_words": None, "tldr_max_sentences": None,
        "banned": [], "private": [], "keep_negation": [],
        "code_names": {"quoted_tests": False, "checks": [], "states": []},
        "external": [],
    }
    p.update(kw)
    return p


def probs(text, profile=None, post=False, exempt=frozenset()):
    return [(p.line, p.rule) for p in furbish.check(text, profile, post, exempt)]


def words(n):
    return " ".join(["word"] * n) + "."


class TestCheckBasics(unittest.TestCase):
    def test_clean_and_empty_drafts_have_no_problems(self):
        self.assertEqual(probs("A short note here.\n"), [])
        self.assertEqual(probs(""), [])

    def test_problems_come_back_in_line_order(self):
        self.assertEqual(probs("Fixed in `c1217e711`.\n\nThanks @someone.\n"), [(1, "sha"), (3, "mention")])
        self.assertEqual(probs("Thanks @someone.\n\nFixed in `c1217e711`.\n"), [(1, "mention"), (3, "sha")])

    def test_a_problem_says_what_is_wrong_in_words(self):
        (p,) = furbish.check("Thanks @someone for this.\n")
        self.assertEqual((p.line, p.rule, p.sid), (1, "mention", ""))
        self.assertIn("@someone", p.message)

    def test_crlf_drafts_give_the_same_problems(self):
        self.assertEqual(probs("Thanks @someone.\r\n\r\nFixed in `c1217e711`.\r\n"), [(1, "mention"), (3, "sha")])


class TestCheckGrade(unittest.TestCase):
    def test_the_sentences_used_below_are_what_they_claim_to_be(self):
        self.assertGreaterEqual(furbish.ari(HARD), 10)
        self.assertLess(furbish.ari(EASY), 10)

    def test_grade_runs_only_with_post(self):
        self.assertEqual(probs(HARD + "\n"), [])
        self.assertEqual(probs(HARD + "\n", post=True), [(1, "grade")])

    def test_a_grade_problem_names_the_sentence(self):
        (p,) = furbish.check(EASY + "\n\n" + HARD + "\n", post=True)
        self.assertEqual((p.line, p.sid, p.rule), (3, "S2", "grade"))
        self.assertIn("10", p.message)

    def test_an_easy_sentence_passes(self):
        self.assertEqual(probs(EASY + "\n", post=True), [])

    def test_template_lines_are_exempt(self):
        self.assertEqual(probs(HARD + "\n", post=True, exempt={HARD}), [])
        self.assertEqual(probs("  " + HARD + "  \n", post=True, exempt={HARD}), [])
        self.assertEqual(probs(HARD + " More.\n", post=True, exempt={HARD}), [(1, "grade")])

    def test_headings_checkboxes_and_short_sentences_are_exempt(self):
        self.assertEqual(probs("## " + HARD + "\n", post=True), [])
        self.assertEqual(probs("- [ ] " + HARD + "\n- [x] " + HARD + "\n", post=True), [])
        self.assertEqual(probs("Unquestionably incomprehensible.\n", post=True), [])

    def test_a_list_item_is_graded(self):
        self.assertEqual(probs("- " + HARD + "\n", post=True), [(1, "grade")])

    def test_inline_code_and_urls_count_as_one_plain_word_each(self):
        d = "Use `an_extraordinarily_long_identifier_name_here` and https://example.com/a/very/long/path/name today.\n"
        self.assertEqual(probs(d, post=True), [])

    def test_the_footer_is_not_graded(self):
        d = EASY + "\n\n" + HARD + "\n"
        self.assertEqual(probs(d, prof(footer="^" + HARD.replace(".", r"\.") + "$"), post=True), [])


class TestGradeSkip(unittest.TestCase):
    P = prof(grade_skip=["^Legacy note:"])

    def test_a_hard_sentence_on_a_matching_line_is_not_graded(self):
        d = "Legacy note: " + HARD + "\n"
        self.assertEqual(probs(d, post=True), [(1, "grade")])
        self.assertEqual(probs(d, self.P, post=True), [])
        self.assertEqual(probs(d, prof(grade_skip=["^Other note:"]), post=True), [(1, "grade")])

    def test_only_the_matching_line_is_skipped(self):
        self.assertEqual(probs("Legacy note: " + HARD + "\n\n" + HARD + "\n", self.P, post=True), [(3, "grade")])

    def test_a_private_string_on_a_skipped_line_is_still_reported(self):
        p = prof(grade_skip=["^Legacy note:"], private=["secret-host"])
        self.assertEqual(probs("Legacy note: " + HARD + " on secret-host.\n", p, post=True), [(1, "private")])

    def test_a_banned_phrase_on_a_skipped_line_is_still_reported(self):
        p = prof(grade_skip=["^Legacy note:"], banned=["synergy"])
        self.assertEqual(probs("Legacy note: " + HARD + " Some synergy.\n", p, post=True), [(1, "banned")])

    def test_split_and_check_skip_the_same_lines(self):
        d = f"{SPLIT_A}, and {SPLIT_B}\n"
        p = prof(grade_skip=["configuration loader"])
        self.assertEqual(len(sg(d)), 1)
        self.assertEqual(sg(d, p), [])
        self.assertEqual(probs(d, post=True), [(1, "grade")])
        self.assertEqual(probs(d, p, post=True), [])


class TestCheckFirstLinePrefix(unittest.TestCase):
    def test_prefix(self):
        p = prof(first_line_prefix="Example:")
        self.assertEqual(probs("Example: fine.\n", p), [])
        self.assertEqual(probs("Nope, fine.\n", p), [(1, "prefix")])
        self.assertEqual(probs("\n\nNope, fine.\n", p), [(3, "prefix")])
        self.assertEqual(probs("", p), [])


class TestCheckShaAndUrlInCode(unittest.TestCase):
    def test_a_sha_in_backticks_is_flagged(self):
        self.assertEqual(probs("Fixed in `c1217e711` today.\n"), [(1, "sha")])
        self.assertEqual(probs("Fixed in `c1217e711c9a3b2d4e5f60718293a4b5c6d7e8f9` today.\n"), [(1, "sha")])

    def test_things_that_are_not_shas_pass(self):
        for d in ["Fixed in c1217e711 today.\n", "Word `deadbeef` here.\n", "Count `1234567` here.\n", "Short `abc123` here.\n", "Mixed `c1217e711 and more` here.\n", "```\nfixed `c1217e711`\n```\n"]:
            self.assertEqual(probs(d), [], d)

    def test_a_url_in_backticks_is_flagged(self):
        self.assertEqual(probs("See `https://example.com/a` now.\n"), [(1, "url-in-code")])
        self.assertEqual(probs("See `http://example.com` now.\n"), [(1, "url-in-code")])

    def test_urls_outside_backticks_and_in_fences_pass(self):
        self.assertEqual(probs("See https://example.com/a now.\n"), [])
        self.assertEqual(probs("```\ncurl `https://example.com/a`\n```\n"), [])


class TestCheckDetails(unittest.TestCase):
    def test_a_well_formed_fold_passes(self):
        d = "Intro.\n\n<details>\n<summary>Test setup</summary>\n\n- Box: Nobara\n\n</details>\n"
        self.assertEqual(probs(d), [])

    def test_no_blank_line_after_the_summary(self):
        d = "Intro.\n\n<details>\n<summary>Test setup</summary>\n- Box: Nobara\n\n</details>\n"
        self.assertEqual(probs(d), [(4, "details-blank")])

    def test_no_blank_line_before_the_closing_tag(self):
        d = "<details>\n<summary>Log</summary>\n\nBody.\n</details>\n"
        self.assertEqual(probs(d), [(5, "details-blank")])

    def test_both_problems_are_reported(self):
        d = "<details>\n<summary>Log</summary>\nBody.\n</details>\n"
        self.assertEqual(probs(d), [(2, "details-blank"), (4, "details-blank")])

    def test_a_one_line_code_span_does_not_hide_the_rest_of_the_draft(self):
        self.assertEqual(probs("```npm test```\nSee `abcdef1` for details.\n"), [(2, "sha")])

    def test_a_fence_that_opens_where_a_comment_closes_is_code(self):
        self.assertEqual(probs("<!--\n--> ```\nuse `abc1234` here\n```\n"), [])

    def test_folds_inside_code_are_ignored(self):
        self.assertEqual(probs("```\n<details>\n<summary>x</summary>\ntext\n</details>\n```\n"), [])


class TestCheckSpdx(unittest.TestCase):
    def test_informal_licence_names_are_flagged(self):
        for d in ["Licensed under GPLv2.", "It is AGPLv3 code.", "We use LGPLv2.1 here.", "The GPL 3 text.", "GPL v3 or later.", "Plain GPL3 here.", "Apache 2.0 licence.", "Apache License 2.0 here.", "Released as BSD 3-clause."]:
            self.assertEqual(probs(d + "\n"), [(1, "spdx")], d)

    def test_spdx_ids_and_plain_words_pass(self):
        for d in ["Licensed under GPL-2.0-only.", "It is AGPL-3.0-or-later code.", "BSD-3-Clause here.", "Apache-2.0 here.", "The GPL is a licence.", "MIT licensed.", "Uses LGPL-2.1-or-later."]:
            self.assertEqual(probs(d + "\n"), [], d)

    def test_code_is_ignored(self):
        self.assertEqual(probs("`GPLv2` is wrong.\n"), [])
        self.assertEqual(probs("```\nGPLv2\n```\n"), [])


class TestCheckMentions(unittest.TestCase):
    def test_mentions_are_flagged(self):
        for d in ["Thanks @someone for this.", "(cc @some-one)", "@someone first."]:
            self.assertEqual(probs(d + "\n"), [(1, "mention")], d)

    def test_each_mention_is_its_own_problem(self):
        self.assertEqual(probs("Thanks @one and @two.\n"), [(1, "mention"), (1, "mention")])

    def test_emails_code_and_a_lone_at_sign_pass(self):
        for d in ["Mail a@b.com now.", "Use `@claude` here.", "An @ alone.", "```\n@someone\n```"]:
            self.assertEqual(probs(d + "\n"), [], d)


class TestCheckTldr(unittest.TestCase):
    P = prof(tldr="required", tldr_words=20, tldr_max_sentences=2)

    def test_short_posts_need_no_tldr(self):
        self.assertEqual(probs(words(19) + "\n", self.P), [])

    def test_a_long_post_needs_one(self):
        self.assertEqual(probs(words(20) + "\n", self.P), [(1, "tldr")])

    def test_a_tldr_line_satisfies_it(self):
        self.assertEqual(probs("**TL;DR:** Short summary here.\n\n" + words(25) + "\n", self.P), [])

    def test_the_tldr_must_come_first(self):
        self.assertEqual(probs("Intro line first.\n\n**TL;DR:** Short.\n\n" + words(25) + "\n", self.P), [(1, "tldr")])
        self.assertEqual(probs("\n\n**TL;DR:** Short.\n\n" + words(25) + "\n", self.P), [])

    def test_a_tldr_over_the_sentence_cap(self):
        self.assertEqual(probs("**TL;DR:** One thing. Two things. Three things.\n", self.P), [(1, "tldr")])
        self.assertEqual(probs("**TL;DR:** One thing. Two things.\n", self.P), [])

    def test_words_in_folds_do_not_count(self):
        d = "Short note.\n\n<details>\n<summary>Log</summary>\n\n" + words(40) + "\n\n</details>\n"
        self.assertEqual(probs(d, self.P), [])

    def test_the_footer_does_not_count(self):
        p = prof(tldr="required", tldr_words=20, tldr_max_sentences=2, footer=FOOTER)
        self.assertEqual(probs(words(15) + "\n\n-- Sent from the made-up example footer\n", p), [])

    def test_a_first_line_prefix_comes_before_the_tldr(self):
        p = prof(tldr="required", tldr_words=20, tldr_max_sentences=2, first_line_prefix="[AUTO] ")
        self.assertEqual(probs("[AUTO] **TL;DR:** Short summary.\n\n" + words(25) + "\n", p), [])

    def test_a_skippable_first_line_comes_before_the_tldr(self):
        p = prof(tldr="required", tldr_words=20, tldr_max_sentences=2, first_line_skip=r"!\[badge\]\(\S+\)")
        badge = "![badge](https://example.org/b.svg)\n\n"
        self.assertEqual(probs(badge + "**TL;DR:** Short summary.\n\n" + words(25) + "\n", p), [])
        self.assertEqual(probs(badge + "**TL;DR:** One thing. Two things. Three things.\n", p), [(3, "tldr")])
        self.assertEqual(probs(badge + words(25) + "\n", p), [(3, "tldr")])

    def test_only_a_whole_first_line_is_skipped(self):
        p = prof(tldr="required", tldr_words=20, tldr_max_sentences=2, first_line_skip="Badge")
        self.assertEqual(probs("Badge and more words.\n\n**TL;DR:** Short.\n\n" + words(25) + "\n", p), [(1, "tldr")])

    def test_a_bad_first_line_skip_is_reported(self):
        with self.assertRaises(furbish.ConfigError):
            furbish._validate_profile({"first_line_skip": "("}, "example-org/example")

    def test_off_means_off(self):
        self.assertEqual(probs(words(500) + "\n", prof(tldr="off")), [])


class TestCheckFooter(unittest.TestCase):
    P = prof(footer=FOOTER)

    def test_the_last_line_must_be_the_footer(self):
        self.assertEqual(probs("Body here.\n\n-- Sent from the made-up example footer\n", self.P), [])
        self.assertEqual(probs("Body here.\n", self.P), [(1, "footer")])
        self.assertEqual(probs("-- Sent from the made-up example footer\n\nBody after.\n", self.P), [(3, "footer")])

    def test_trailing_blank_lines_and_crlf_are_fine(self):
        self.assertEqual(probs("Body.\n\n-- Sent from the made-up example footer\n\n\n", self.P), [])
        self.assertEqual(probs("Body.\r\n\r\n-- Sent from the made-up example footer\r\n", self.P), [])

    def test_no_footer_setting_means_no_check(self):
        self.assertEqual(probs("Body here.\n", prof()), [])


class TestCheckBanned(unittest.TestCase):
    P = prof(banned=["circle back", "synergy"])

    def test_a_banned_phrase_is_flagged_with_its_sentence(self):
        (p,) = furbish.check("We should circle back later.\n", self.P)
        self.assertEqual((p.line, p.sid, p.rule), (1, "S1", "banned"))
        self.assertIn("circle back", p.message)

    def test_case_is_ignored_and_whole_words_are_needed(self):
        self.assertEqual(probs("We should Circle Back later.\n", self.P), [(1, "banned")])
        self.assertEqual(probs("Synergystic plans.\n", self.P), [])

    def test_code_is_not_prose(self):
        self.assertEqual(probs("Quote: `circle back` is banned.\n", self.P), [])
        self.assertEqual(probs("```\ncircle back\n```\n", self.P), [])

    def test_two_phrases_in_one_sentence_are_two_problems(self):
        self.assertEqual(probs("Circle back for synergy.\n", self.P), [(1, "banned"), (1, "banned")])


class TestCheckPrivate(unittest.TestCase):
    P = prof(private=["/home/", "example-hostname"])

    def test_private_text_is_flagged_anywhere(self):
        self.assertEqual(probs("Path is /home/someone/x.\n", self.P), [(1, "private")])
        self.assertEqual(probs("Intro.\n\n```\ncd /home/someone\n```\n", self.P), [(4, "private")])
        self.assertEqual(probs("<!-- note: /home/someone -->\n", self.P), [(1, "private")])
        self.assertEqual(probs("Host EXAMPLE-HOSTNAME here.\n", self.P), [(1, "private")])

    def test_one_problem_per_string_per_line(self):
        self.assertEqual(probs("/home/a and /home/b and example-hostname\n", self.P), [(1, "private"), (1, "private")])

    def test_nothing_private_passes(self):
        self.assertEqual(probs("A clean line.\n", self.P), [])


class TestCheckOnMadeUpDrafts(unittest.TestCase):
    def load(self, name):
        with open(os.path.join(DRAFTS, name), encoding="utf-8") as f:
            return f.read()

    def test_pr_body_lacks_a_tldr(self):
        p = prof(footer=FOOTER, tldr="required", tldr_words=50, tldr_max_sentences=3)
        self.assertEqual(probs(self.load("pr-body.md"), p), [(1, "tldr")])

    def test_issue_body_is_clean(self):
        self.assertEqual(probs(self.load("issue-body.md"), prof(footer=FOOTER)), [])


class TestCheckStaysFast(unittest.TestCase):
    P = prof(footer=FOOTER, tldr="required", tldr_words=100, tldr_max_sentences=3, first_line_prefix="x", banned=[f"banned phrase {i}" for i in range(30)], private=["/home/", "example-hostname", "secret"])

    def test_a_262_kb_draft_checks_in_under_a_second(self):
        with open(os.path.join(DRAFTS, "pr-body.md"), encoding="utf-8") as f:
            body = f.read()
        big = (body * (262000 // len(body) + 1))[:262000]
        for post in (False, True):
            t = time.perf_counter()
            furbish.check(big, self.P, post)
            self.assertLess(time.perf_counter() - t, 1.0, post)

    def test_hostile_text_stays_fast(self):
        cases = [
            "a" + "`" * 200000, "[a" * 100000, "[a](" * 60000, "<a " * 80000, "<" * 100000, ">" * 262000, "`a b " * 40000,
            "@a " * 80000, "GPL " * 60000, "`abcdef1` " * 30000, "<details>\n<summary>x</summary>\n" * 8000,
            "http://" * 30000, "/home/ " * 40000, "banned phrase 1 " * 15000, "`https://x.y/z` " * 15000, "a\n" * 130000, "Apache " * 30000,
            "Yes. " * 52000, "  " + "Yes. " * 52000, "- a b c.\n" * 30000,
        ]
        for d in cases:
            for post in (False, True):
                t = time.perf_counter()
                furbish.check(d, self.P, post)
                self.assertLess(time.perf_counter() - t, 2.0, d[:14])


class TestCheckCli(ConfigCase):
    def env(self, **extra):
        e = {"HOME": self.tmp, "PATH": "/usr/bin:/bin"}
        e.update(extra)
        return e

    def run_check(self, *args, **extra):
        return subprocess.run([sys.executable, "-I", SCRIPT, "check", *args], capture_output=True, text=True, env=self.env(**extra))

    def draft(self, text, name="draft.md"):
        return self.write(text, name)

    def test_a_clean_draft_prints_nothing_and_exits_0(self):
        r = self.run_check(self.draft("A short clean note.\n"))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_a_problem_prints_path_line_and_words_and_exits_1(self):
        path = self.draft("Fine line.\n\nThanks @someone.\n")
        r = self.run_check(path)
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith(f"{path}:3: "), lines[0])
        self.assertIn("@someone", lines[0])
        self.assertEqual(r.stderr, "")

    def test_a_sentence_problem_shows_its_id(self):
        r = self.run_check("--post", self.draft(EASY + "\n\n" + HARD + "\n"))
        self.assertEqual(r.returncode, 1)
        self.assertIn(":3: S2: ", r.stdout)

    def test_post_switches_the_reading_grade_on(self):
        path = self.draft(HARD + "\n")
        self.assertEqual(self.run_check(path).returncode, 0)
        self.assertEqual(self.run_check("--post", path).returncode, 1)

    def test_text_prints_the_flagged_sentence_under_its_problem(self):
        path = self.draft(HARD + "\n")
        out = self.run_check("--post", "--text", path).stdout.splitlines()
        self.assertEqual(out[1], "    " + HARD)
        self.assertEqual(len(self.run_check("--post", path).stdout.splitlines()), 1)

    def test_the_default_repo_profile_applies(self):
        cfg = self.write('default_repo = "a/b"\n[repo."a/b"]\nfooter = "^END$"\n[repo."c/d"]\n', "cfg.toml")
        path = self.draft("Body.\n")
        r = self.run_check(path, FURBISH_CONFIG=cfg)
        self.assertEqual(r.returncode, 1)
        self.assertIn(":1: ", r.stdout)
        self.assertIn("footer", r.stdout)
        self.assertEqual(self.run_check("--repo", "c/d", path, FURBISH_CONFIG=cfg).returncode, 0)

    def test_the_config_is_found_under_home(self):
        self.write('default_repo = "a/b"\n[repo."a/b"]\nfooter = "^END$"\n', ".config/furbish/config.toml")
        self.assertEqual(self.run_check(self.draft("Body.\n")).returncode, 1)

    def test_template_lines_are_exempt_from_grading(self):
        tpl = self.write(HARD + "\n", "tpl.md")
        cfg = self.write(f'default_repo = "a/b"\n[repo."a/b"]\npr_template = "{tpl}"\n', "cfg.toml")
        path = self.draft(HARD + "\n")
        self.assertEqual(self.run_check("--post", path, FURBISH_CONFIG=cfg).returncode, 0)
        self.assertEqual(self.run_check("--post", path).returncode, 1)

    def test_a_missing_template_file_is_a_plain_error(self):
        gone = os.path.join(self.tmp, "gone.md")
        cfg = self.write(f'default_repo = "a/b"\n[repo."a/b"]\npr_template = "{gone}"\n', "cfg.toml")
        r = self.run_check(self.draft("Body.\n"), FURBISH_CONFIG=cfg)
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn(gone, r.stderr)

    def test_an_unknown_repo_exits_2(self):
        cfg = self.write('[repo."a/b"]\n', "cfg.toml")
        r = self.run_check("--repo", "x/y", self.draft("Body.\n"), FURBISH_CONFIG=cfg)
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn("x/y", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_a_repo_with_no_config_file_exits_2(self):
        r = self.run_check("--repo", "x/y", self.draft("Body.\n"))
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn("x/y", r.stderr)

    def test_a_broken_config_exits_2_with_its_path(self):
        cfg = self.write("this is = = not toml", "cfg.toml")
        r = self.run_check(self.draft("Body.\n"), FURBISH_CONFIG=cfg)
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn(cfg, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_a_missing_draft_exits_2(self):
        gone = os.path.join(self.tmp, "gone.md")
        r = self.run_check(gone)
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn(gone, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_a_folder_instead_of_a_draft_exits_2(self):
        r = self.run_check(self.tmp)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_a_draft_that_is_not_utf8_does_not_crash(self):
        path = os.path.join(self.tmp, "bad.md")
        with open(path, "wb") as f:
            f.write(b"Bad \xff byte here.\n")
        r = self.run_check(path)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)

    def test_check_with_no_draft_is_a_usage_error(self):
        self.assertEqual(self.run_check().returncode, 2)

    def test_help_no_longer_lists_check_as_planned(self):
        r = subprocess.run([sys.executable, "-I", SCRIPT, "--help"], capture_output=True, text=True, env=self.env())
        self.assertEqual(r.returncode, 0)
        self.assertIn("check", r.stdout)
        self.assertNotIn("planned: print only the problems", r.stdout)
        self.assertNotIn("planned: replace one sentence", r.stdout)
        self.assertNotIn("planned", r.stdout)
        self.assertIn("split", r.stdout)


LINES_SCRIPT = """import sys
p = sys.argv[-1]
print(f"{p}:3: FAIL first problem")
print(f"{p}:7:12: FAIL second problem")
print("FAIL no line number")
print("note: fine")
print(f"{p}:9: note: also fine")
"""

VALE_SCRIPT = """import json, sys
p = sys.argv[-1]
alerts = [
    {"Action": {"Name": "", "Params": None}, "Suggestions": [], "Span": [1, 3], "Check": "Example.Spdx", "Description": "", "Link": "", "Message": "Use the SPDX id 'GPL-2.0-only' instead of 'GPLv2'.", "Severity": "warning", "Match": "GPLv2", "Line": 4},
    {"Check": "Example.NotRun", "Message": "Heading is 'Not run', not 'Not Run'.", "Severity": "error", "Line": 9},
]
print(json.dumps({p: alerts}))
sys.exit(1)
"""


class ExternalCase(ConfigCase):
    def script(self, text, name="checker.py"):
        return self.write(text, name)

    def entry(self, text, mode="lines", fail=None, name="ex", args=()):
        return {"name": name, "mode": mode, "command": [sys.executable, "-I", self.script(text, name + ".py"), *args], "fail": fail}

    def draft(self, text="Body.\n", name="draft.md"):
        return self.write(text, name)


class TestRunExternal(ExternalCase):
    def test_lines_mode_reports_the_matching_lines_with_their_line_numbers(self):
        path = self.draft()
        out = furbish.run_external([self.entry(LINES_SCRIPT, fail="FAIL")], path)
        self.assertEqual([(p.line, p.rule) for p in out], [(3, "ex"), (7, "ex"), (0, "ex")])
        self.assertTrue(all(p.sid == "" for p in out))
        self.assertIn("first problem", out[0].message)
        self.assertIn("second problem", out[1].message)
        self.assertTrue(out[0].message.startswith("ex: "))

    def test_nothing_matching_means_no_problems(self):
        self.assertEqual(furbish.run_external([self.entry(LINES_SCRIPT, fail="^NEVER$")], self.draft()), [])

    def test_the_draft_is_the_last_argument_and_is_passed_as_given(self):
        path = self.draft()
        script = "import sys\nprint(sys.argv[1:])\n"
        e = self.entry(script, fail=r"\['--flag', '" + re.escape(path) + r"'\]", args=("--flag",))
        self.assertEqual(len(furbish.run_external([e], path)), 1)

    def test_json_mode_reads_vale_alerts(self):
        out = furbish.run_external([self.entry(VALE_SCRIPT, mode="json")], self.draft())
        self.assertEqual([(p.line, p.rule) for p in out], [(4, "ex"), (9, "ex")])
        self.assertIn("Example.Spdx", out[0].message)
        self.assertIn("GPL-2.0-only", out[0].message)
        self.assertIn("Example.NotRun", out[1].message)

    def test_json_mode_with_no_alerts(self):
        self.assertEqual(furbish.run_external([self.entry("print('{}')\n", mode="json")], self.draft()), [])
        self.assertEqual(furbish.run_external([self.entry("", mode="json")], self.draft()), [])

    def test_json_alerts_without_a_usable_line_are_reported_without_one(self):
        text = 'import json\nprint(json.dumps({"a.md": [{"Check": "X.Y", "Message": "no line"}, {"Check": "X.Z", "Message": "bad line", "Line": "7"}, {"Check": "X.W", "Message": "negative", "Line": -3}]}))\n'
        out = furbish.run_external([self.entry(text, mode="json")], self.draft())
        self.assertEqual([(p.line, p.rule) for p in out], [(0, "ex"), (0, "ex"), (0, "ex")])

    def test_a_list_of_things_that_are_not_alerts_is_an_error(self):
        for text in ['print(\'{"a.md": ["oops"]}\')\n', 'print(\'{"a.md": [3, null]}\')\n']:
            with self.assertRaises(furbish.ExternalError, msg=text):
                furbish.run_external([self.entry(text, mode="json")], self.draft())

    def test_status_one_with_nothing_printed_in_json_mode_is_an_error(self):
        with self.assertRaises(furbish.ExternalError) as cm:
            furbish.run_external([self.entry("import sys\nsys.stderr.write('config trouble')\nsys.exit(1)\n", mode="json")], self.draft())
        self.assertIn("config trouble", str(cm.exception))

    def test_a_huge_line_number_is_not_a_line_number(self):
        e = self.entry("import sys\nprint(sys.argv[-1] + ':' + '9' * 5000 + ': FAIL msg')\n", fail="FAIL")
        out = furbish.run_external([e], self.draft())
        self.assertEqual([p.line for p in out], [0])

    def test_a_nul_byte_in_the_command_is_an_error_not_a_crash(self):
        e = {"name": "ex", "mode": "json", "command": ["a\x00b"], "fail": None}
        with self.assertRaises(furbish.ExternalError) as cm:
            furbish.run_external([e], self.draft())
        self.assertIn("ex", str(cm.exception))

    def test_lines_are_split_on_newlines_only(self):
        text = "import sys\np = sys.argv[-1]\nprint(p + ':3: ERROR bad \\x85 text')\nprint('junk\\x0b' + p + ':99: ERROR forged')\n"
        out = furbish.run_external([self.entry(text, fail="ERROR")], self.draft())
        self.assertEqual([p.line for p in out], [3, 0])

    def test_json_that_is_not_json_is_an_error(self):
        with self.assertRaises(furbish.ExternalError) as cm:
            furbish.run_external([self.entry("print('not json')\n", mode="json")], self.draft())
        self.assertIn("ex", str(cm.exception))
        self.assertIn("JSON", str(cm.exception))

    def test_json_in_a_shape_furbish_does_not_read_is_an_error(self):
        for text in ["print('[1, 2]')\n", "print('{\"a.md\": 5}')\n", "print('3')\n"]:
            with self.assertRaises(furbish.ExternalError, msg=text):
                furbish.run_external([self.entry(text, mode="json")], self.draft())

    def test_status_zero_and_one_are_normal_and_others_are_errors(self):
        for code in (0, 1):
            self.assertEqual(furbish.run_external([self.entry(f"import sys\nsys.exit({code})\n", fail="x")], self.draft()), [])
        with self.assertRaises(furbish.ExternalError) as cm:
            furbish.run_external([self.entry("import sys\nprint('trouble here')\nsys.exit(3)\n", fail="x")], self.draft())
        self.assertIn("ex", str(cm.exception))
        self.assertIn("3", str(cm.exception))
        self.assertIn("trouble here", str(cm.exception))

    def test_a_checker_that_reports_its_own_error_as_json_says_so(self):
        text = 'import json, sys\nprint(json.dumps({"Line": 0, "Path": "", "Text": "path nowhere does not exist", "Code": "E100", "Span": 0}))\nsys.exit(2)\n'
        with self.assertRaises(furbish.ExternalError) as cm:
            furbish.run_external([self.entry(text, mode="json")], self.draft())
        self.assertIn("path nowhere does not exist", str(cm.exception))

    def test_a_checker_that_reports_its_error_as_json_on_stderr_says_so(self):
        text = 'import json, sys\nsys.stderr.write(json.dumps({"Line": 0, "Path": "", "Text": "path nowhere does not exist", "Code": "E100"}, indent=2))\nsys.exit(2)\n'
        with self.assertRaises(furbish.ExternalError) as cm:
            furbish.run_external([self.entry(text, mode="json")], self.draft())
        self.assertIn("path nowhere does not exist", str(cm.exception))

    def test_stderr_is_the_reason_when_stdout_is_empty(self):
        with self.assertRaises(furbish.ExternalError) as cm:
            furbish.run_external([self.entry("import sys\nsys.stderr.write('\\n  bad thing happened\\n')\nsys.exit(4)\n", fail="x")], self.draft())
        self.assertIn("bad thing happened", str(cm.exception))

    def test_a_missing_program_is_an_error_naming_it(self):
        e = {"name": "ex", "mode": "lines", "command": ["/nonexistent/checker", "--plain"], "fail": "x"}
        with self.assertRaises(furbish.ExternalError) as cm:
            furbish.run_external([e], self.draft())
        self.assertIn("ex", str(cm.exception))
        self.assertIn("/nonexistent/checker", str(cm.exception))

    def test_a_checker_that_runs_too_long_is_stopped(self):
        e = self.entry("import time\ntime.sleep(10)\n", fail="x")
        t = time.perf_counter()
        with self.assertRaises(furbish.ExternalError) as cm:
            furbish.run_external([e], self.draft(), timeout=0.5)
        self.assertLess(time.perf_counter() - t, 5)
        self.assertIn("ex", str(cm.exception))
        self.assertIn("longer", str(cm.exception))

    def test_the_checker_cannot_wait_for_input(self):
        e = self.entry("import sys\nsys.stdin.read()\nprint('done')\n", fail="done")
        t = time.perf_counter()
        self.assertEqual(len(furbish.run_external([e], self.draft(), timeout=5)), 1)
        self.assertLess(time.perf_counter() - t, 4)

    def test_entries_run_in_config_order_and_results_are_joined(self):
        a = self.entry("print('FAIL from a')\n", fail="FAIL", name="a")
        b = self.entry("print('FAIL from b')\n", fail="FAIL", name="b")
        self.assertEqual([p.rule for p in furbish.run_external([a, b], self.draft())], ["a", "b"])

    def test_one_failing_entry_stops_the_run(self):
        a = self.entry("print('FAIL from a')\n", fail="FAIL", name="a")
        b = {"name": "b", "mode": "lines", "command": ["/nonexistent/checker"], "fail": "x"}
        with self.assertRaises(furbish.ExternalError) as cm:
            furbish.run_external([a, b], self.draft())
        self.assertIn("b", str(cm.exception))

    def test_nothing_in_the_draft_or_its_path_is_run(self):
        path = self.draft("$(touch pwned)\n`touch pwned`\n; touch pwned\n", "a b;touch pwned;$(touch pwned).md")
        out = furbish.run_external([self.entry(LINES_SCRIPT, fail="FAIL")], path)
        self.assertEqual(len(out), 3)
        self.assertFalse(os.path.exists("pwned"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "pwned")))

    def test_a_flood_of_output_stays_fast(self):
        e = self.entry("import sys\np = sys.argv[-1]\nsys.stdout.write((p + ':5: FAIL x\\n') * 100000)\n", fail="FAIL")
        t = time.perf_counter()
        out = furbish.run_external([e], self.draft())
        self.assertEqual(len(out), 100000)
        self.assertLess(time.perf_counter() - t, 3.0)

    def test_no_entries_means_nothing_runs(self):
        self.assertEqual(furbish.run_external([], self.draft()), [])


class TestCheckCliWithCheckers(ExternalCase):
    def env(self, **extra):
        e = {"HOME": self.tmp, "PATH": "/usr/bin:/bin"}
        e.update(extra)
        return e

    def config(self, *entries, repo="a/b"):
        parts = [f'default_repo = "{repo}"\n[repo."{repo}"]\n']
        for e in entries:
            parts.append(f'[[repo."{repo}".external]]\nname = {json.dumps(e["name"])}\nmode = {json.dumps(e["mode"])}\ncommand = {json.dumps(e["command"])}\n')
            if e["fail"]:
                parts.append(f'fail = {json.dumps(e["fail"])}\n')
        return self.write("".join(parts), "cfg.toml")

    def run_check(self, *args, cfg=None, cwd=None):
        extra = {"FURBISH_CONFIG": cfg} if cfg else {}
        return subprocess.run([sys.executable, "-I", SCRIPT, "check", *args], capture_output=True, text=True, env=self.env(**extra), cwd=cwd)

    def test_checker_problems_join_the_built_in_ones_in_line_order(self):
        cfg = self.config(self.entry(LINES_SCRIPT, fail="FAIL"))
        self.draft("One.\n\nTwo.\n\nThree.\n\nFour.\n\nThanks @someone.\n", "d.md")
        r = self.run_check("d.md", cfg=cfg, cwd=self.tmp)
        self.assertEqual(r.returncode, 1)
        lines = r.stdout.splitlines()
        self.assertEqual([l.split(": ")[0] for l in lines], ["d.md", "d.md:3", "d.md:7", "d.md:9"])
        self.assertIn("first problem", lines[1])
        self.assertIn("second problem", lines[2])
        self.assertIn("@someone", lines[3])
        self.assertEqual(r.stderr, "")

    def test_a_checker_problem_without_a_line_prints_just_the_path(self):
        cfg = self.config(self.entry(LINES_SCRIPT, fail="no line number"))
        r = self.run_check(self.draft(), cfg=cfg)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stdout.startswith(f"{os.path.join(self.tmp, 'draft.md')}: ex: FAIL no line number"), r.stdout)

    def test_vale_style_json_through_the_command(self):
        cfg = self.config(self.entry(VALE_SCRIPT, mode="json"))
        r = self.run_check(self.draft(), cfg=cfg)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stdout.splitlines()), 2)
        self.assertIn(":4: ex: ", r.stdout)
        self.assertIn("Example.Spdx", r.stdout)

    def test_a_clean_draft_and_a_quiet_checker_print_nothing(self):
        cfg = self.config(self.entry(LINES_SCRIPT, fail="^NEVER$"))
        r = self.run_check(self.draft(), cfg=cfg)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_a_checker_that_cannot_run_exits_2_with_a_plain_message(self):
        cfg = self.config({"name": "ex", "mode": "lines", "command": ["/nonexistent/checker"], "fail": "x"})
        r = self.run_check(self.draft("Thanks @someone.\n"), cfg=cfg)
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn("ex", r.stderr)
        self.assertIn("/nonexistent/checker", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_control_characters_in_checker_output_are_not_printed(self):
        text = "import sys\nprint(sys.argv[-1] + ':3: FAIL \\x1b[31mred\\x1b]0;title\\x07 \\x9b end')\n"
        cfg = self.config(self.entry(text, fail="FAIL"))
        r = self.run_check(self.draft(), cfg=cfg)
        self.assertEqual(r.returncode, 1)
        for bad in ("\x1b", "\x07", "\x9b"):
            self.assertNotIn(bad, r.stdout)
        self.assertIn("red", r.stdout)

    def test_bidi_marks_surrogates_and_a_draft_path_with_escapes_are_not_printed(self):
        text = "import sys\nsys.stdout.write(sys.argv[-1] + ':3: FAIL a\\u202eb\\u200fc\\u2028d\\n')\n"
        cfg = self.config(self.entry(text, fail="FAIL"))
        r = self.run_check(self.draft("Body.\n", "d\x1b[31mx.md"), cfg=cfg)
        self.assertEqual(r.returncode, 1)
        for bad in ("\x1b", "\u202e", "\u200f", "\u2028"):
            self.assertNotIn(bad, r.stdout)
        self.assertIn("a?b?c?d", r.stdout)

    def test_a_lone_surrogate_in_json_output_does_not_crash_the_printing(self):
        text = "import sys\nsys.stdout.write('{\"f\": [{\"Line\": 1, \"Message\": \"bad \\\\ud800 here\"}]}')\n"
        cfg = self.config(self.entry(text, mode="json"))
        r = self.run_check(self.draft(), cfg=cfg)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("bad ? here", r.stdout)

    def test_a_profile_without_checkers_runs_none(self):
        cfg = self.write('default_repo = "a/b"\n[repo."a/b"]\n[repo."c/d"]\n', "cfg2.toml")
        marker = os.path.join(self.tmp, "ran")
        entry = self.entry(f"open({marker!r}, 'w').close()\n", fail="x")
        both = self.write(open(cfg).read() + f'[[repo."a/b".external]]\nname = "ex"\nmode = "lines"\ncommand = {json.dumps(entry["command"])}\nfail = "x"\n', "cfg3.toml")
        self.assertEqual(self.run_check("--repo", "c/d", self.draft(), cfg=both).returncode, 0)
        self.assertFalse(os.path.exists(marker))
        self.run_check("--repo", "a/b", self.draft(), cfg=both)
        self.assertTrue(os.path.exists(marker))


class TestSetWhere(unittest.TestCase):
    def put(self, text, sid, new, profile=None):
        return furbish.set_sentence(text, sid, new, profile).text

    def test_one_sentence_is_replaced_and_the_rest_is_kept(self):
        self.assertEqual(self.put("First one. Second one. Third one.\n", "S2", "Changed it."), "First one. Changed it. Third one.\n")

    def test_a_repeated_sentence_is_found_by_position_not_by_search(self):
        self.assertEqual(self.put("Yes. Yes.\n", "S2", "No."), "Yes. No.\n")
        self.assertEqual(self.put("Yes. Yes.\n", "S1", "No."), "No. Yes.\n")
        self.assertEqual(self.put("Yes.\n\nYes.\n\nYes.\n", "S3", "No."), "Yes.\n\nYes.\n\nNo.\n")

    def test_a_wrapped_sentence_becomes_one_line(self):
        d = "Intro line. This sentence is long\nand wraps here. Tail.\n"
        self.assertEqual(texts(d)[1], "This sentence is long and wraps here.")
        self.assertEqual(self.put(d, "S2", "Short."), "Intro line. Short. Tail.\n")

    def test_the_edit_reports_the_lines_it_replaced(self):
        e = furbish.set_sentence("Top.\n\nA sentence that\nwraps here.\n\nEnd.\n", "S2", "Short.")
        self.assertEqual((e.first, e.old, e.new), (3, ["A sentence that", "wraps here."], "Short."))
        e = furbish.set_sentence("One here. Two here.\n", "S1", "Uno.")
        self.assertEqual((e.first, e.old, e.new), (1, ["One here. Two here."], "Uno. Two here."))

    def test_list_quote_and_heading_markers_stay(self):
        d = "- Item one.\n> Quoted words.\n# Title here\n"
        self.assertEqual(texts(d), ["Item one.", "Quoted words.", "Title here"])
        self.assertEqual(self.put(d, "S1", "Item two."), "- Item two.\n> Quoted words.\n# Title here\n")
        self.assertEqual(self.put(d, "S2", "Said it."), "- Item one.\n> Said it.\n# Title here\n")
        self.assertEqual(self.put(d, "S3", "New title"), "- Item one.\n> Quoted words.\n# New title\n")

    def test_a_wrapped_list_item_and_a_wrapped_quote(self):
        self.assertEqual(self.put("1. First step is long\n   and continues.\n2. Next.\n", "S1", "Do it."), "1. Do it.\n2. Next.\n")
        self.assertEqual(self.put("> A quoted line that\n> goes on here. Then more.\n", "S1", "Short."), "> Short. Then more.\n")

    def test_indent_and_trailing_spaces_stay(self):
        self.assertEqual(self.put("  - Item.  \n", "S1", "Done."), "  - Done.  \n")
        self.assertEqual(self.put("Words here.   \nMore words.\n", "S1", "Fine."), "Fine.   \nMore words.\n")

    def test_line_endings_survive(self):
        self.assertEqual(self.put("One here.\r\nTwo here.\r\nThree here.\n", "S2", "Two changed."), "One here.\r\nTwo changed.\r\nThree here.\n")
        self.assertEqual(self.put("A sentence that\r\nwraps here.\r\nNext one.\r\n", "S1", "Short."), "Short.\r\nNext one.\r\n")
        self.assertEqual(self.put("One here.\nTwo here.\r\n", "S2", "Two changed."), "One here.\nTwo changed.\r\n")

    def test_a_lone_carriage_return_is_not_a_line_break(self):
        d = "One here.\rTwo here.\nThree here.\n"
        self.assertEqual(lines(d), [1, 1, 2])
        self.assertEqual(self.put(d, "S3", "Done."), "One here.\rTwo here.\nDone.\n")

    def test_odd_line_breaks_do_not_move_the_ids(self):
        d = "One here.\x0bTwo here.\x85Three here.\u2028Four here.\n\nFive here.\n"
        self.assertEqual(lines(d), [1, 1, 1, 1, 3])
        self.assertEqual(self.put(d, "S2", "Done."), "One here.\x0bDone.\x85Three here.\u2028Four here.\n\nFive here.\n")
        self.assertEqual(self.put(d, "S5", "Done."), "One here.\x0bTwo here.\x85Three here.\u2028Four here.\n\nDone.\n")

    def test_a_replacement_may_read_as_more_than_one_sentence(self):
        out = self.put("One. Two. Three.\n", "S2", "A. B.")
        self.assertEqual(out, "One. A. B. Three.\n")
        self.assertEqual(texts(out), ["One.", "A.", "B.", "Three."])

    def test_the_replacement_is_stripped(self):
        self.assertEqual(self.put("One here. Two here.\n", "S1", "  Uno.\t "), "Uno. Two here.\n")

    def test_the_same_text_changes_nothing(self):
        e = furbish.set_sentence("One here. Two here.\n", "S2", "Two here.")
        self.assertEqual(e.text, "One here. Two here.\n")

    def test_a_replacement_that_breaks_the_rest_of_the_draft_is_refused(self):
        for new in ("```", "~~~", "<!-- x -->", "<!-- open", "| a | b |", "<details>", "-->"):
            for d in ("Hello there.\n\nKeep this.\n", "Hello there. Keep this.\n"):
                with self.assertRaises(furbish.Refused, msg=(new, d)):
                    furbish.set_sentence(d, "S1", new)

    def test_a_replacement_that_cannot_be_one_plain_line_is_refused(self):
        for new in ("", "   ", "a\nb", "a\rb", "a\x1b[31mb", "a\u202eb", "a\u2028b", "a\x00b", "bad \udc80 text", "a\x85b", "a\x0bb"):
            with self.assertRaises(furbish.Refused, msg=repr(new)):
                furbish.set_sentence("One here. Two here.\n", "S1", new)

    def test_ids_are_read_by_the_same_reader_as_check(self):
        d = "One here.\n\n-- Sent from the made-up example footer\n\nTwo here.\n"
        p = {"footer": FOOTER}
        self.assertEqual(self.put(d, "S2", "Done.", p), "One here.\n\n-- Sent from the made-up example footer\n\nDone.\n")
        self.assertEqual(self.put(d, "S2", "Done."), "One here.\n\nDone.\n\nTwo here.\n")

    def test_code_comments_and_tables_are_not_numbered_and_not_touched(self):
        d = "Text one.\n```\nCode. Not prose.\n```\n| a | b |\n<!-- gone. -->\nText two.\n"
        self.assertEqual(texts(d), ["Text one.", "Text two."])
        self.assertEqual(self.put(d, "S2", "Done."), "Text one.\n```\nCode. Not prose.\n```\n| a | b |\n<!-- gone. -->\nDone.\n")

    def test_a_sentence_after_a_comment_closes_is_found(self):
        d = "<!--\nnote\n--> After words here. Next.\n"
        self.assertEqual(self.put(d, "S1", "New."), "<!--\nnote\n--> New. Next.\n")
        self.assertEqual(self.put(d, "S2", "New."), "<!--\nnote\n--> After words here. New.\n")

    def test_a_sentence_on_a_line_with_a_comment_is_refused_and_the_comment_is_never_eaten(self):
        for d in ("Before <!-- note --> after words. Next one.\n", "Words here. <!-- note -->\n", "Start of it <!-- note -->\nand the end of it.\n"):
            with self.assertRaises(furbish.Refused) as cm:
                furbish.set_sentence(d, "S1", "New.")
            self.assertIn("comment", str(cm.exception))

    def test_a_sentence_after_a_one_line_comment_on_its_own_line_is_fine(self):
        d = "<!-- note -->\nWords here.\n"
        self.assertEqual(self.put(d, "S1", "New."), "<!-- note -->\nNew.\n")

    def test_inline_code_with_odd_backticks_is_kept_whole(self):
        d = "Run ``a ` b`` now. Next one.\n"
        self.assertEqual(self.put(d, "S1", "Run ``a ` b`` soon."), "Run ``a ` b`` soon. Next one.\n")

    def test_unknown_or_badly_formed_ids_cannot_run(self):
        d = "One here. Two here. Three here.\n"
        for sid in ("S4", "S0", "12", "S", "S-1", "Sx", "S1.5", "S 2", "", "S" + "9" * 5000, "S\u0663", "S+1", "SS1"):
            with self.assertRaises(furbish.ConfigError, msg=sid) as cm:
                furbish.set_sentence(d, sid, "New.")
            self.assertNotIsInstance(cm.exception, furbish.Refused)
        with self.assertRaises(furbish.ConfigError) as cm:
            furbish.set_sentence(d, "S4", "New.")
        self.assertIn("S1 to S3", str(cm.exception))

    def test_a_lower_case_id_works(self):
        self.assertEqual(self.put("One here. Two here.\n", "s2", "Done."), "One here. Done.\n")

    def test_a_draft_with_no_sentences_cannot_run(self):
        with self.assertRaises(furbish.ConfigError) as cm:
            furbish.set_sentence("```\ncode\n```\n", "S1", "New.")
        self.assertIn("no sentences", str(cm.exception))


class TestSetGuards(unittest.TestCase):
    P = {"keep_negation": ["Not run", "Still not run"]}

    def refuse(self, text, sid, new, profile=None, *words):
        with self.assertRaises(furbish.Refused, msg=new) as cm:
            furbish.set_sentence(text, sid, new, profile)
        for w in words:
            self.assertIn(w, str(cm.exception))
        return cm.exception

    def allow(self, text, sid, new, profile=None):
        return furbish.set_sentence(text, sid, new, profile).text

    def test_numbers_must_stay(self):
        d = "It took 12 seconds. Next one.\n"
        self.refuse(d, "S1", "It took a while.", None, "12")
        self.refuse(d, "S1", "It took 120 seconds.", None, "12")
        self.refuse(d, "S1", "It took 1 or 2 seconds.", None, "12")
        self.assertEqual(self.allow(d, "S1", "Twelve is 12 s."), "Twelve is 12 s. Next one.\n")

    def test_numbers_with_points_and_commas_are_one_number(self):
        d = "It ran 3.5 times in 1,000 tries.\n"
        self.refuse(d, "S1", "It ran 35 times in 1,000 tries.", None, "3.5")
        self.refuse(d, "S1", "It ran 3 times in 1,000 tries.", None, "3.5")
        self.refuse(d, "S1", "It ran 3.5 times in 100 tries.", None, "1,000")
        self.assertEqual(self.allow(d, "S1", "In 1000 tries it ran 3.5 times."), "In 1000 tries it ran 3.5 times.\n")
        self.assertEqual(self.allow("Over 65536 bytes.\n", "S1", "Over 65,536 bytes."), "Over 65,536 bytes.\n")

    def test_issue_numbers_and_times_must_stay(self):
        self.refuse("See #123 at 12:30.\n", "S1", "See the issue at 12:30.", None, "123")
        self.refuse("See #123 at 12:30.\n", "S1", "See #123 at noon.", None, "12:30")

    def test_commit_shas_must_stay(self):
        d = "Fixed in abc1234 today.\n"
        self.refuse(d, "S1", "Fixed today.", None, "abc1234")
        self.refuse(d, "S1", "Fixed in abc12345 today.", None, "abc1234")
        self.refuse(d, "S1", "Fixed in abc123 today.", None, "abc1234")
        self.assertEqual(self.allow(d, "S1", "Today it is fixed in abc1234."), "Today it is fixed in abc1234.\n")

    def test_a_long_sha_and_its_digits_are_one_thing(self):
        d = "Reverted 0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b here.\n"
        self.refuse(d, "S1", "Reverted 0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9 here.", None, "0a1b2c3d")
        self.allow(d, "S1", "Here it is 0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b.")

    def test_inline_code_must_stay(self):
        d = "Run `npm test` now.\n"
        self.refuse(d, "S1", "Run it now.", None, "`npm test`")
        self.refuse(d, "S1", "Run `npm` now.", None, "`npm test`")
        self.refuse("Use `a`.\n", "S1", "Use `ab`.", None, "`a`")
        self.refuse("Use `a`.\n", "S1", "Use a.", None, "`a`")
        self.assertEqual(self.allow(d, "S1", "Now run `npm test`."), "Now run `npm test`.\n")
        self.assertEqual(self.allow("Use `a`.\n", "S1", "Use `a` or `b`."), "Use `a` or `b`.\n")

    def test_every_dropped_thing_is_listed(self):
        e = self.refuse("Fixed 12 in abc1234 with `x`.\n", "S1", "Fixed it.")
        text = str(e)
        for w in ("12", "abc1234", "`x`"):
            self.assertIn(w, text)
        self.assertEqual(len(e.reasons), 3)

    def test_a_number_inside_a_code_span_is_part_of_the_span(self):
        d = "Run `step 12` now.\n"
        self.assertEqual(self.allow(d, "S1", "Now run `step 12`."), "Now run `step 12`.\n")
        self.refuse(d, "S1", "Run `step` 12 now.", None, "`step 12`")

    def test_a_link_target_is_kept_with_its_numbers(self):
        d = "See [the issue](https://example.com/issues/77) now.\n"
        self.refuse(d, "S1", "See the issue now.", None, "77")

    def test_nothing_to_keep_means_anything_goes(self):
        self.assertEqual(self.allow("Words here, plain ones.\n", "S1", "Other words."), "Other words.\n")

    NOT_RUN = "### Not run\n\n- The Windows build was not run.\n- Nothing ran on the GPU.\n\n### Notes\n\nThe build did not fail.\n"

    def test_a_negation_under_a_listed_heading_must_stay(self):
        d = self.NOT_RUN
        self.assertEqual([s.id for s in furbish.read_prose(d)][1:3], ["S2", "S3"])
        e = self.refuse(d, "S2", "The Windows build ran.", self.P, "not")
        self.assertIn("Not run", str(e))
        self.refuse(d, "S3", "The GPU ran.", self.P)
        self.assertIn("never run", self.allow(d, "S2", "The Windows build was never run.", self.P))
        self.assertIn("wasn't run", self.allow(d, "S2", "The Windows build wasn't run.", self.P))
        self.assertIn("wasn\u2019t run", self.allow(d, "S2", "The Windows build wasn\u2019t run.", self.P))
        self.assertIn("No one ran", self.allow(d, "S3", "No one ran the GPU.", self.P))
        self.assertIn("without", self.allow(d, "S3", "It ran without the GPU.", self.P))

    def test_each_negation_word_counts(self):
        for w in ("not", "no", "never", "none", "nothing", "nobody", "nowhere", "neither", "nor", "cannot", "without", "Not", "NEVER", "didn't", "can't", "won't", "isn't", "hasn't", "ain't"):
            self.assertTrue(furbish._negated(f"It {w} ran."), w)
        for w in ("note", "know", "nothingness", "another", "knot", "notice", "now", "node", "non", "nope"):
            self.assertFalse(furbish._negated(f"It {w} ran."), w)

    def test_a_negation_word_in_code_or_a_link_does_not_count(self):
        d = "### Not run\n\n- It was not run.\n"
        self.refuse(d, "S2", "It ran with `--no-cache`.", self.P)
        self.refuse(d, "S2", "It ran, see [there](https://example.com/not/there).", self.P)
        self.refuse(d, "S2", "It ran, see https://example.com/not/there.", self.P)
        self.refuse(d, "S2", "Take note.", self.P)

    def test_a_struck_through_item_keeps_its_negation(self):
        d = "### Not run\n\n- The Windows build was not run.\n"
        self.assertEqual(self.allow(d, "S2", "~~The Windows build was not run.~~", self.P), "### Not run\n\n- ~~The Windows build was not run.~~\n")

    def test_a_sentence_without_negation_has_none_to_keep(self):
        d = "### Not run\n\n- The Windows build.\n"
        self.assertEqual(self.allow(d, "S2", "The Windows build passed.", self.P), "### Not run\n\n- The Windows build passed.\n")

    def test_other_headings_and_no_profile_are_not_guarded(self):
        d = self.NOT_RUN
        self.assertIn("The build failed.", self.allow(d, "S5", "The build failed.", self.P))
        self.assertIn("The Windows build ran.", self.allow(d, "S2", "The Windows build ran."))
        self.assertIn("The Windows build ran.", self.allow(d, "S2", "The Windows build ran.", {"keep_negation": []}))
        self.assertIn("The Windows build ran.", self.allow(d, "S2", "The Windows build ran.", {}))

    def test_a_listed_heading_covers_what_is_nested_under_it_and_stops_at_the_next_one_of_its_level(self):
        d = "## Not run\n\n### Node 22\n\nIt was not run here.\n\n#### Deeper\n\nNor here.\n\n## Done\n\nIt was not run there.\n"
        self.assertEqual([s.id for s in furbish.read_prose(d)], ["S1", "S2", "S3", "S4", "S5", "S6", "S7"])
        self.refuse(d, "S3", "It ran here.", self.P)
        self.refuse(d, "S5", "It ran here.", self.P)
        self.assertIn("It ran there.", self.allow(d, "S7", "It ran there.", self.P))

    def test_a_heading_inside_a_code_fence_is_not_a_heading(self):
        d = "```\n# Not run\n```\n\nThe tests were not run.\n"
        self.assertIn("The tests ran.", self.allow(d, "S1", "The tests ran.", self.P))

    def test_the_heading_match_ignores_case_and_allows_a_tail(self):
        for h in ("NOT RUN", "not run", "Not run:", "Not run yet (testing now)", "Not run - and why", "**Not run**"):
            d = f"### {h}\n\nIt was not run.\n"
            self.refuse(d, "S2", "It ran.", self.P)
        for h in ("Not running", "Not runnable", "Notrun", "Still testing", "Run"):
            d = f"### {h}\n\nIt was not run.\n"
            self.assertIn("It ran.", self.allow(d, "S2", "It ran.", self.P), h)
        d = "### Still not run\n\nIt was not run.\n"
        self.refuse(d, "S2", "It ran.", self.P)

    def test_a_listed_heading_cannot_be_renamed_away(self):
        d = self.NOT_RUN
        self.refuse(d, "S1", "Tested", self.P, "Not run")
        self.assertEqual(self.allow(d, "S1", "Not run at all", self.P)[:20], "### Not run at all\n\n")
        self.assertIn("### Other", self.allow(d, "S4", "Other", self.P))

    def test_a_bold_line_is_not_a_heading(self):
        d = "**Not run**\n\nIt was not run.\n"
        self.assertIn("It ran.", self.allow(d, "S2", "It ran.", self.P))

    def test_a_guard_failure_and_a_structure_failure_are_both_refusals(self):
        d = "### Not run\n\nIt was not run 12 times.\n"
        self.refuse(d, "S2", "```", self.P)
        self.refuse(d, "S2", "It ran.", self.P, "12", "not")


class TestSetCli(ConfigCase):
    def env(self, **extra):
        e = {"HOME": self.tmp, "PATH": "/usr/bin:/bin"}
        e.update(extra)
        return e

    def run_set(self, *args, cwd=None, **extra):
        return subprocess.run([sys.executable, "-I", SCRIPT, "set", *args], capture_output=True, text=True, env=self.env(**extra), cwd=cwd)

    def draft(self, text, name="draft.md"):
        return self.write(text, name)

    def read(self, path):
        with open(path, "rb") as f:
            return f.read()

    def test_without_write_it_prints_the_change_and_touches_nothing(self):
        path = self.draft("One here.\n\nTwo here. Three here.\n")
        before = self.read(path)
        r = self.run_set(path, "S2", "Deux.")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read(path), before)
        self.assertEqual(r.stdout.splitlines(), [f"--- {path}", f"+++ {path}", "@@ -3,1 +3,1 @@", "-Two here. Three here.", "+Deux. Three here."])
        self.assertIn("--write", r.stderr)
        self.assertIn("nothing", r.stderr)

    def test_with_write_it_changes_the_file_and_says_so_the_same_way(self):
        path = self.draft("One here.\n\nTwo here. Three here.\n")
        r = self.run_set(path, "S2", "Deux.", "--write")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read(path), b"One here.\n\nDeux. Three here.\n")
        self.assertEqual(r.stdout.splitlines()[2:], ["@@ -3,1 +3,1 @@", "-Two here. Three here.", "+Deux. Three here."])
        self.assertEqual(r.stderr, "")

    def test_a_wrapped_sentence_shows_every_line_it_replaces(self):
        path = self.draft("Top.\n\nA sentence that\nwraps here. After.\n")
        r = self.run_set(path, "S2", "Short.")
        self.assertEqual(r.stdout.splitlines()[2:], ["@@ -3,2 +3,1 @@", "-A sentence that", "-wraps here. After.", "+Short. After."])

    def test_a_crlf_draft_keeps_its_line_endings_on_write(self):
        path = self.draft("")
        with open(path, "wb") as f:
            f.write(b"One here.\r\nTwo here.\r\n")
        r = self.run_set(path, "S2", "Deux.", "--write")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read(path), b"One here.\r\nDeux.\r\n")
        self.assertNotIn("\r", r.stdout)

    def test_a_refusal_prints_each_reason_with_the_line_and_id_and_writes_nothing(self):
        path = self.draft("Intro.\n\nIt took 12 seconds with `x`.\n")
        before = self.read(path)
        r = self.run_set(path, "S2", "It was quick.", "--write")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertEqual(self.read(path), before)
        out = r.stderr.splitlines()
        self.assertEqual(len(out), 2)
        for line in out:
            self.assertTrue(line.startswith(f"{path}:3: S2: "), line)
        self.assertIn("12", r.stderr)
        self.assertIn("`x`", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_the_repo_profile_guards_a_negation(self):
        cfg = self.write('[repo."a/b"]\nkeep_negation = ["Not run"]\n', "cfg.toml")
        path = self.draft("### Not run\n\nIt was not run.\n")
        r = self.run_set(path, "S2", "It ran.", "--repo", "a/b", FURBISH_CONFIG=cfg)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Not run", r.stderr)
        r = self.run_set(path, "S2", "It ran.", FURBISH_CONFIG=cfg)
        self.assertEqual(r.returncode, 0)
        cfg2 = self.write('default_repo = "a/b"\n[repo."a/b"]\nkeep_negation = ["Not run"]\n', "cfg2.toml")
        self.assertEqual(self.run_set(path, "S2", "It ran.", FURBISH_CONFIG=cfg2).returncode, 1)

    def test_the_ids_are_the_ones_check_prints(self):
        cfg = self.write(f'[repo."a/b"]\nfooter = {json.dumps(FOOTER)}\n', "cfg.toml")
        path = self.draft(f"{EASY}\n\n-- Sent from the made-up example footer\n\n{HARD}\n")
        r = subprocess.run([sys.executable, "-I", SCRIPT, "check", "--post", "--repo", "a/b", path], capture_output=True, text=True, env=self.env(FURBISH_CONFIG=cfg))
        m = re.search(r":5: (S\d+): ", r.stdout)
        self.assertTrue(m, r.stdout)
        self.assertEqual(m.group(1), "S2")
        r = self.run_set(path, m.group(1), "Look at it again.", "--repo", "a/b", "--write", FURBISH_CONFIG=cfg)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read(path).decode(), f"{EASY}\n\n-- Sent from the made-up example footer\n\nLook at it again.\n")

    def test_things_that_cannot_run_exit_2_with_a_plain_message(self):
        path = self.draft("One here.\n")
        for args in ((path, "S9", "New."), (path, "twelve", "New."), (os.path.join(self.tmp, "missing.md"), "S1", "New."), (path, "S" + "9" * 5000, "New."), (path, "S1", "New.", "--repo", "x/y")):
            r = self.run_set(*args)
            self.assertEqual((r.returncode, r.stdout), (2, ""), args)
            self.assertTrue(r.stderr.startswith("furbish: "), r.stderr)
            self.assertNotIn("Traceback", r.stderr)
        self.assertIn("only S1", self.run_set(path, "S9", "New.").stderr)

    def test_a_missing_argument_is_a_usage_error(self):
        path = self.draft("One here.\n")
        self.assertEqual(self.run_set(path, "S1").returncode, 2)
        self.assertEqual(self.run_set().returncode, 2)

    def test_a_draft_that_is_not_utf8_is_never_rewritten(self):
        path = self.draft("")
        with open(path, "wb") as f:
            f.write(b"Caf\xe9 is here. Two here.\n")
        for extra in ((), ("--write",)):
            r = self.run_set(path, "S2", "Deux.", *extra)
            self.assertEqual((r.returncode, r.stdout), (2, ""))
            self.assertIn("UTF-8", r.stderr)
        self.assertEqual(self.read(path), b"Caf\xe9 is here. Two here.\n")

    def test_control_characters_are_not_printed(self):
        path = self.draft("Esc \x1b[mred\x1b]t\x07 here \u202e done.\n")
        r = self.run_set(path, "S1", "New.")
        self.assertEqual(r.returncode, 0)
        for bad in ("\x1b", "\x07", "\u202e"):
            self.assertNotIn(bad, r.stdout)
        self.assertIn("red", r.stdout)
        r = self.run_set(self.draft("One here.\n", "d\x1b[31mx.md"), "S1", "Two.")
        self.assertNotIn("\x1b", r.stdout)

    def test_a_refusal_does_not_print_control_characters(self):
        path = self.draft("It took 12 \x1b[31mseconds\x1b[0m.\n")
        r = self.run_set(path, "S1", "It took a while.")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("\x1b", r.stderr)

    def test_a_symlinked_draft_is_written_through_the_link(self):
        real = self.draft("One here. Two here.\n", "real.md")
        link = os.path.join(self.tmp, "link.md")
        os.symlink(real, link)
        r = self.run_set(link, "S2", "Deux.", "--write")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(os.path.islink(link))
        self.assertEqual(self.read(real), b"One here. Deux.\n")

    def test_the_file_mode_survives_a_write_and_no_temp_file_is_left(self):
        path = self.draft("One here. Two here.\n")
        os.chmod(path, 0o640)
        before = sorted(os.listdir(self.tmp))
        self.assertEqual(self.run_set(path, "S2", "Deux.", "--write").returncode, 0)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o640)
        self.assertEqual(sorted(os.listdir(self.tmp)), before)

    def test_a_text_that_starts_with_a_dash_goes_after_two_dashes(self):
        path = self.draft("One here. Two here.\n")
        r = self.run_set(path, "S2", "--write", "--", "--odd.")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read(path), b"One here. --odd.\n")

    def test_help_lists_set_as_working(self):
        r = subprocess.run([sys.executable, "-I", SCRIPT, "--help"], capture_output=True, text=True, env=self.env())
        self.assertIn("set", r.stdout)
        self.assertNotIn("planned: replace one sentence", r.stdout)
        r = self.run_set("--help")
        self.assertIn("--write", r.stdout)

    def test_a_draft_given_by_a_relative_path_is_found(self):
        self.draft("One here. Two here.\n")
        r = self.run_set("draft.md", "S2", "Deux.", "--write", cwd=self.tmp)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read(os.path.join(self.tmp, "draft.md")), b"One here. Deux.\n")


class TestSetReviewFixes(unittest.TestCase):
    KN = {"keep_negation": ["Security"]}

    def put(self, text, sid, new, profile=None):
        return furbish.set_sentence(text, sid, new, profile).text

    def refuse(self, text, sid, new, profile=None):
        with self.assertRaises(furbish.Refused, msg=(text, new)) as cm:
            furbish.set_sentence(text, sid, new, profile)
        return str(cm.exception)

    def test_a_replacement_cannot_change_what_kind_of_block_the_next_lines_are(self):
        d = "Intro here.\nSecond line.\n\nTail para.\n"
        for new in ("> Quote one. Two.", "- Item one. Two.", "1. Item one. Two.", "# Head one. Two.", "> Quote one"):
            self.refuse(d, "S1", new)

    def test_a_heading_scope_cannot_be_ended_in_two_steps(self):
        d = "## Security\n\nIntro here.\n\nWe do not log.\n"
        self.refuse(d, "S3", "We log everything.", self.KN)
        self.refuse(d, "S2", "# Top. Fine here.", self.KN)

    def test_a_comment_cannot_be_written_into_a_draft(self):
        for new in ("Hi there. <!-- hidden --> Two.", "Hi <!--", "Hi -->", "<!---->", "A <!-- x --> B."):
            self.assertIn("comment", self.refuse("Intro here.\n", "S1", new))

    def test_hidden_and_odd_characters_are_not_accepted(self):
        for new in ("A\tB.", "A\u200bB.", "A\u2060B.", "A\ufeffB.", "A\U000e0041B."):
            self.refuse("Alpha beta.\n", "S1", new)

    def test_a_trailing_symbol_that_is_not_a_sentence_is_fine(self):
        self.assertEqual(self.put("Alpha beta.\n", "S1", "Done. \U0001F642"), "Done. \U0001F642\n")
        self.assertEqual(self.put("Alpha beta.\n", "S1", "Done \u2014"), "Done \u2014\n")

    def test_the_same_text_on_a_wrapped_sentence_still_joins_the_lines(self):
        self.assertEqual(self.put("Alpha beta\ngamma.\n", "S1", "Alpha beta gamma."), "Alpha beta gamma.\n")

    def test_a_bare_carriage_return_at_the_very_end_does_not_move_the_ids(self):
        d = "Alpha one.\n\nSent with furbish\r"
        p = {"footer": r"furbish$"}
        self.assertEqual([s.id for s in furbish.read_prose(d, p["footer"])], ["S1", "S2"])
        self.assertEqual(self.put(d, "S2", "Edited.", p), "Alpha one.\n\nEdited.\r")

    def test_negation_words_with_apostrophes_and_hidden_ones(self):
        for t in ("Nothing's logged here.", "Nobody's logging this.", "It don\u02bct run.", "It isn\u2019t run."):
            self.assertTrue(furbish._negated(t), t)
        for t in ("We log <b title='x > not'>it</b>.", "We log it ![not](x.png).", "We log <i>it</i>."):
            self.assertFalse(furbish._negated(t), t)
        self.assertTrue(furbish._negated("We log ~~not~~ it."))

    def test_an_image_or_a_tag_that_never_closes_is_not_a_negation_source(self):
        self.assertFalse(furbish._negated("It ran ![not](x.png) here."))
        self.assertTrue(furbish._negated("It ran ![a not here."))
        self.assertTrue(furbish._negated("It ran ![a](b not here."))
        self.assertTrue(furbish._negated("It <a 'x not here."))

    def test_nobody_s_counts_as_keeping_nobody(self):
        d = "## Security\n\nNobody logs this.\n"
        self.assertEqual(self.put(d, "S2", "Nobody's logging this.", self.KN), "## Security\n\nNobody's logging this.\n")
        self.refuse("## Security\n\nNothing's logged here.\n", "S2", "We log it.", self.KN)

    def test_every_way_of_writing_a_heading_guards_what_is_under_it(self):
        for h in ("## Security", "   ## Security", "Security\n========", "Security\n--------", "\ufeff## Security", "## _Security_", "## __Security__", "## **Security**", "## Security ##"):
            d = h + "\n\nWe do not log.\n"
            n = len(furbish.read_prose(d))
            self.refuse(d, f"S{n}", "We log.", self.KN)

    def test_a_quoted_heading_does_not_guard_what_follows_the_quote(self):
        d = "> ## Security\n\nWe do not log.\n"
        self.assertIn("We log.", self.put(d, "S2", "We log.", self.KN))

    def test_a_sibling_heading_can_be_reworded_and_ends_the_scope_before_it(self):
        d = "## Security\n\nAll fine.\n\n## No limits\n\nBody here.\n"
        self.assertIn("## Limits", self.put(d, "S3", "Limits", self.KN))
        self.assertIn("We know.", self.put("## Security\n\nAll fine.\n\n## No limits\n\nWe do not know.\n", "S4", "We know.", self.KN))

    def test_a_heading_with_no_words_still_ends_a_scope(self):
        d = "## Security\n\nAll fine.\n\n## `Details`\n\nWe do not know.\n"
        self.assertIn("We know.", self.put(d, "S3", "We know.", self.KN))
        d = "## Security\n\nAll fine.\n\n## \U0001F600\n\nWe do not know.\n"
        self.assertIn("We know.", self.put(d, "S3", "We know.", self.KN))

    def test_a_repeated_word_in_a_heading_is_changed_where_it_is(self):
        d = "## Security. Security\n\nWe do not log.\n"
        self.assertIn("## Security. Memo", self.put(d, "S2", "Memo", self.KN))
        self.refuse(d, "S1", "Memo.", self.KN)

    def test_tag_names_are_not_numbers(self):
        self.assertEqual(furbish._lost("<h2>Security</h2> now.", "Security now."), [])
        self.assertEqual(furbish._lost("A <b>bold 12</b> move.", "A bold move."), ["the new sentence drops the number 12"])
        self.assertEqual(furbish._lost("It is a<b2.", "It is."), ["the new sentence drops the number 2"])

    def test_upper_case_shas_are_shas(self):
        self.refuse("Fixed in ABCDEF1234 today.\n", "S1", "Fixed in 1234 today.")
        self.refuse("Fixed in abcdef1234 today.\n", "S1", "Fixed in ABCDEF1234 today.")
        self.assertEqual(self.put("Fixed in ABCDEF1234 today.\n", "S1", "Today, ABCDEF1234."), "Today, ABCDEF1234.\n")

    def test_marks_in_front_of_a_sentence_survive(self):
        self.assertEqual(self.put("Foo here.\n---\nBar here.\n", "S2", "Baz here."), "Foo here.\n---\nBaz here.\n")
        self.assertEqual(self.put("Foo here.\n***\nBar here.\n", "S2", "Baz here."), "Foo here.\n***\nBaz here.\n")
        self.assertEqual(self.put("- [ ] Task one.\n- [x] Task two.\n", "S1", "Task uno."), "- [ ] Task uno.\n- [x] Task two.\n")
        self.assertEqual(self.put("> - item one\n> continues here.\n", "S1", "New."), "> - New.\n")
        self.assertEqual(self.put("-\tTabbed item.\n", "S1", "New."), "-\tNew.\n")
        self.assertEqual(self.put("- Alpha one\n-\n- beta two.\n", "S1", "New."), "- New.\n-\n- beta two.\n")
        self.assertEqual(self.put("Foo here\n---\n\nBar here.\n", "S1", "Baz here"), "Baz here\n---\n\nBar here.\n")

    def test_a_sentence_that_runs_over_marked_lines_is_refused(self):
        for d in ("> Alpha one\n>\n> beta two.\n", "> - a b\n> - c d.\n"):
            self.assertIn("comment or with list marks", self.refuse(d, "S1", "New."))

    def test_the_reader_leaves_marks_out_of_the_prose(self):
        self.assertEqual(texts("Foo here.\n---\nBar here.\n"), ["Foo here.", "Bar here."])
        self.assertEqual(texts("A line.\n\n***\n\n___\n\n- - -\n\nAnother.\n"), ["A line.", "Another."])
        self.assertEqual(texts("- [ ] Task one.\n- [X] Task two.\n"), ["Task one.", "Task two."])
        self.assertEqual(texts("-\tTabbed item.\n"), ["Tabbed item."])
        self.assertEqual(texts("> - item one\n> continues here.\n"), ["item one continues here."])
        self.assertEqual(texts("- Alpha one\n-\n- beta two.\n"), ["Alpha one", "beta two."])
        self.assertEqual(texts("See [x] here.\n\n[x]: https://example.com/a\n"), ["See [x] here."])
        self.assertEqual(texts("A note[^1].\n\n[^1]: The note text.\n"), ["A note[^1].", "[^1]: The note text."])
        self.assertEqual(texts("See [x] here.\n[x]: not a definition here.\n"), ["See [x] here.", "[x]: not a definition here."])

    def test_the_reader_knows_more_kinds_of_heading(self):
        for d in ("  ## Hi there", "   # Hi there", "\ufeff## Hi there", "Hi there\n===", "Hi there\n---"):
            found = furbish._sentences(d.split("\n"), None)
            self.assertEqual([(x.sentence.text, x.kind) for x in found], [("Hi there", "heading")], d)
        self.assertEqual(furbish._sentences("    ## Hi there".split("\n"), None), [])
        self.assertEqual(furbish._sentences(["Hi there", "", "---"], None)[0].kind, "para")

    def test_each_sentence_knows_the_headings_over_it(self):
        found = furbish._sentences("# One\n\n## Two\n\nBody.\n\n## Three\n\nMore.\n".split("\n"), None)
        self.assertEqual([x.under for x in found], [(), ("One",), ("One", "Two"), ("One",), ("One", "Three")])


class TestSetWritePath(ConfigCase):
    def run_set(self, *args):
        return subprocess.run([sys.executable, "-I", SCRIPT, "set", *args], capture_output=True, text=True, env={"HOME": self.tmp, "PATH": "/usr/bin:/bin"})

    def test_a_closed_pipe_does_not_make_a_traceback_or_lose_the_write(self):
        path = self.write("One here. Two here.\n", "a.md")
        cmd = f"set -o pipefail; {shlex.quote(sys.executable)} -I {shlex.quote(SCRIPT)} set {shlex.quote(path)} S2 Deux. --write | head -c0; echo ${{PIPESTATUS[0]}}"
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env={"HOME": self.tmp, "PATH": "/usr/bin:/bin"})
        self.assertEqual(r.stdout.strip(), "0")
        self.assertNotIn("Exception", r.stderr)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "One here. Deux.\n")

    @unittest.skipIf(os.geteuid() == 0, "root can write a read-only file")
    def test_a_read_only_draft_is_left_alone(self):
        path = self.write("One here. Two here.\n", "a.md")
        os.chmod(path, 0o444)
        r = self.run_set(path, "S2", "Deux.", "--write")
        self.assertEqual(r.returncode, 2)
        self.assertIn("read-only", r.stderr)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "One here. Two here.\n")
        self.assertEqual(self.run_set(path, "S2", "Deux.").returncode, 0)

    def test_a_hard_linked_draft_is_left_alone(self):
        path = self.write("One here. Two here.\n", "a.md")
        link = os.path.join(self.tmp, "b.md")
        os.link(path, link)
        r = self.run_set(path, "S2", "Deux.", "--write")
        self.assertEqual(r.returncode, 2)
        self.assertIn("hard link", r.stderr)
        for p in (path, link):
            with open(p, encoding="utf-8") as f:
                self.assertEqual(f.read(), "One here. Two here.\n")
        self.assertEqual(sorted(os.listdir(self.tmp)), ["a.md", "b.md"])


class TestSetTiming(ConfigCase):
    def timed(self, text, sid, new):
        path = self.write(text, "big.md")
        for extra in ((), ("--write",)):
            t = time.perf_counter()
            r = subprocess.run([sys.executable, "-I", SCRIPT, "set", path, sid, new, *extra], capture_output=True, text=True, env={"HOME": self.tmp, "PATH": "/usr/bin:/bin"})
            took = time.perf_counter() - t
            self.assertEqual(r.returncode, 0, (sid, r.stderr[-300:]))
            self.assertLess(took, 2.0, (text[:14], extra, took))

    def test_a_262_kb_draft_is_changed_in_under_a_second(self):
        with open(os.path.join(DRAFTS, "pr-body.md"), encoding="utf-8") as f:
            body = f.read()
        big = (body * (262000 // len(body) + 1))[:262000]
        found = furbish.read_prose(big)
        mid = found[len(found) // 2]
        profile = {"footer": FOOTER, "keep_negation": ["Not run"]}
        t = time.perf_counter()
        edit = furbish.set_sentence(big, mid.id, mid.text + " Added.", profile)
        self.assertLess(time.perf_counter() - t, 1.0)
        self.assertNotEqual(edit.text, big)

    def test_many_short_lines_in_one_block(self):
        self.timed("Yes.\n" * 52000, "S26000", "No.")

    def test_many_sentences_on_one_long_line(self):
        self.timed("Yes. " * 52000, "S26000", "No.")
        self.timed("  " + "Yes. " * 52000, "S26000", "No.")

    def test_one_huge_wrapped_sentence(self):
        self.timed("word word word\n" * 17000, "S1", "Short.")

    def test_a_huge_sentence_with_many_things_to_keep(self):
        self.timed("see `a` 12 abc1234 " * 13000 + "\n", "S1", "see `a` 12 abc1234.")
        big = "see `a` 12 abc1234 " * 13000
        t = time.perf_counter()
        furbish.set_sentence(big + "\n", "S1", "x " + big)
        self.assertLess(time.perf_counter() - t, 2.0)

    def test_hostile_floods_through_the_negation_guard(self):
        profile = {"keep_negation": ["Not run"]}
        for body in ("![a" * 65000, "![a](" * 52000, "<a '" * 65000, '<a "' * 65000, "<a x='" * 43000, "<a " * 80000, "<b2 " * 65000, "<" * 200000, "don't " * 40000, "a'" * 130000, "![a](b) " * 30000):
            d = "## Not run\n\nIt was not run. " + body + "\n"
            t = time.perf_counter()
            try:
                furbish.set_sentence(d, "S3", "No.", profile)
            except (furbish.Refused, furbish.ConfigError):
                pass
            self.assertLess(time.perf_counter() - t, 2.0, body[:12])

    def test_hostile_lines(self):
        for d in ("a" + "`" * 200000, "[a" * 100000, "[a](" * 60000, "<a " * 80000, "`a b " * 40000, "- a b c.\n" * 30000, "> a b c.\n" * 30000):
            path = self.write(d + "\n\nTail here.\n", "hostile.md")
            t = time.perf_counter()
            r = subprocess.run([sys.executable, "-I", SCRIPT, "set", path, "S1", "New."], capture_output=True, text=True, env={"HOME": self.tmp, "PATH": "/usr/bin:/bin"})
            self.assertLess(time.perf_counter() - t, 2.0, d[:14])
            self.assertIn(r.returncode, (0, 1, 2), d[:14])
            self.assertNotIn("Traceback", r.stderr, d[:14])


CN = {"code_names": {"quoted_tests": True, "checks": ["Example lint", "Example unit tests"], "states": ["passed", "failed", "skipped"]}}


def fx(text, profile=None, exempt=frozenset()):
    return furbish.fix_text(text, profile, exempt).text


class TestFixText(unittest.TestCase):
    def test_a_lone_sha_loses_its_backticks(self):
        self.assertEqual(fx("Fixed in `abc1234` today.\n"), "Fixed in abc1234 today.\n")
        self.assertEqual(fx("Fixed in `0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b` today.\n"), "Fixed in 0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b today.\n")
        self.assertEqual(fx("Fixed in ``abc1234`` and ` def5678 `.\n"), "Fixed in abc1234 and def5678.\n")

    def test_other_code_spans_are_left_alone(self):
        for t in ("The `deadbeef` and `12345678` and `abcdef` words.", "Use `ABCDEF1234` here.", "Run `git show abc1234` now.", "Run `curl https://example.com` now.", "A `abc1234 def5678` pair.", "The `--flag` option."):
            self.assertEqual(fx(t + "\n"), t + "\n", t)

    def test_a_lone_url_loses_its_backticks(self):
        self.assertEqual(fx("See `https://example.com/a` and `http://x.y/z`.\n"), "See https://example.com/a and http://x.y/z.\n")

    def test_code_is_never_touched_where_it_is_not_prose(self):
        draft = "```\nFixed in `abc1234` with `https://example.com`.\n```\n\n~~~\n`abc1234`\n~~~\n\n<!-- `abc1234` -->\n\n| `abc1234` | b |\n\n> Quoted `abc1234` text.\n\n    Indented `abc1234` text.\n"
        self.assertEqual(fx(draft), draft)

    def test_link_text_and_quotes_and_headings_and_checkboxes_are_left_alone(self):
        for t in ("See [`abc1234`](https://example.com/x) now.", 'He said "see `abc1234`" there.', "### Fixed in `abc1234`", "- [x] Fixed in `abc1234`", "- [ ] Fixed in `abc1234`"):
            self.assertEqual(fx(t + "\n"), t + "\n", t)

    def test_a_line_with_a_comment_cut_out_of_it_is_left_alone(self):
        for t in ("Fixed in `abc1234` <!-- c --> now.", "<!-- c --> Fixed in `abc1234`."):
            self.assertEqual(fx(t + "\n"), t + "\n", t)
        self.assertEqual(fx("<!--\nnote\n--> Fixed in `abc1234` now.\n"), "<!--\nnote\n--> Fixed in `abc1234` now.\n")
        self.assertEqual(fx("<!--\nnote\n-->\nFixed in `abc1234` now.\n"), "<!--\nnote\n-->\nFixed in abc1234 now.\n")

    def test_the_footer_and_template_lines_are_left_alone(self):
        footer = r"^-- Sent with `abc1234`$"
        draft = "Fixed in `abc1234`.\n\n-- Sent with `abc1234`\n"
        self.assertEqual(fx(draft, {"footer": footer}), "Fixed in abc1234.\n\n-- Sent with `abc1234`\n")
        self.assertEqual(fx("Fixed in `abc1234` again.\n", None, frozenset({"Fixed in `abc1234` again."})), "Fixed in `abc1234` again.\n")

    def test_blank_lines_go_into_details(self):
        self.assertEqual(fx("<details>\n<summary>Test setup</summary>\nText here.\n</details>\n"), "<details>\n<summary>Test setup</summary>\n\nText here.\n\n</details>\n")
        self.assertEqual(fx("<details>\n<summary>x</summary>\n</details>\n"), "<details>\n<summary>x</summary>\n\n</details>\n")
        self.assertEqual(fx("<details><summary>x</summary>\nText.\n</details>\n"), "<details><summary>x</summary>\n\nText.\n\n</details>\n")

    def test_details_that_are_already_fine_or_not_real_are_left_alone(self):
        fine = "<details>\n<summary>x</summary>\n\nText.\n\n</details>\n"
        self.assertEqual(fx(fine), fine)
        for t in ("```\n<summary>x</summary>\nText\n</details>\n```\n", "A `</details>` span.\nNext.\n", "<!--\n</summary>\nText\n-->\n"):
            self.assertEqual(fx(t), t, t)

    def test_the_blank_line_takes_the_line_ending_of_its_neighbour(self):
        self.assertEqual(fx("<summary>x</summary>\r\nText.\r\n</details>\r\n"), "<summary>x</summary>\r\n\r\nText.\r\n\r\n</details>\r\n")
        self.assertEqual(fx("<summary>x</summary>\nText.\r\n</details>"), "<summary>x</summary>\n\nText.\r\n\r\n</details>")

    def test_line_endings_survive_an_edit(self):
        self.assertEqual(fx("One `abc1234`.\r\nTwo `def5678`.\nThree.\r\n"), "One abc1234.\r\nTwo def5678.\nThree.\r\n")

    def test_no_code_names_means_none_are_applied(self):
        d = 'The "test_open_file" test passed.\n'
        for prof in (None, {}, {"code_names": {}}, {"code_names": {"quoted_tests": False, "checks": [], "states": []}}):
            self.assertEqual(fx(d, prof), d)

    def test_quoted_test_names_become_code(self):
        p = {"code_names": {"quoted_tests": True, "checks": [], "states": []}}
        self.assertEqual(fx('The "test_open_file" test.\n', p), "The `test_open_file` test.\n")
        self.assertEqual(fx("The \u201cTestOpen\u201d test.\n", p), "The `TestOpen` test.\n")
        self.assertEqual(fx('A "tests/test_x.py::test_a" case.\n', p), "A `tests/test_x.py::test_a` case.\n")
        for t in ('Say "hello" and "foo.bar" and "Test open".', 'See [the "test_x" doc](https://example.com).', 'A `"test_x"` span.', 'He said "test_x y" ok.', '> A "test_x" quote.', '| "test_x" | b |', '### The "test_x" part', '- [ ] The "test_x" box'):
            self.assertEqual(fx(t + "\n", p), t + "\n", t)

    def test_quoted_tests_off_leaves_quotes_alone(self):
        p = {"code_names": {"quoted_tests": False, "checks": ["Example lint"], "states": []}}
        self.assertEqual(fx('The "test_open_file" test and Example lint.\n', p), 'The "test_open_file" test and `Example lint`.\n')

    def test_check_names_and_states_become_code_in_prose(self):
        self.assertEqual(fx("Example lint passed and Example unit tests failed.\n", CN), "`Example lint` `passed` and `Example unit tests` `failed`.\n")
        self.assertEqual(fx("- Linux skipped.\n", CN), "- Linux `skipped`.\n")
        self.assertEqual(fx("**passed**\n", CN), "**`passed`**\n")

    def test_the_longest_name_wins(self):
        p = {"code_names": {"checks": ["Example", "Example lint"], "states": []}}
        self.assertEqual(fx("Example lint ran. Example ran.\n", p), "`Example lint` ran. `Example` ran.\n")

    def test_names_need_whole_words_in_the_same_case(self):
        for t in ("It unpassed, pre-passed, passedly, and Passed.", "The Example linter and Example lint-all.", "Example lints."):
            self.assertEqual(fx(t + "\n", CN), t + "\n", t)

    def test_names_are_left_alone_in_code_links_urls_quotes_tables_headings_and_templates(self):
        for t in ("See [passed](https://example.com/passed) now.", "See https://example.com/passed now.", "It `passed` already.", 'She said "passed" twice.', "| passed | failed |", "### Tests passed", "> It passed.", "- [x] It passed.", "<b title=\"passed\">tag</b>", "<https://example.com/passed>"):
            self.assertEqual(fx(t + "\n", CN), t + "\n", t)
        self.assertEqual(fx("It passed here.\n", CN, frozenset({"It passed here."})), "It passed here.\n")

    def test_a_quoted_test_name_is_code_before_names_are_looked_for(self):
        self.assertEqual(fx('The "test_passed" test passed.\n', CN), "The `test_passed` test `passed`.\n")

    def test_names_inside_a_wrapped_paragraph_are_found_line_by_line(self):
        self.assertEqual(fx("It was a\nlong run that passed\nand then failed.\n", CN), "It was a\nlong run that `passed`\nand then `failed`.\n")

    def test_fixing_twice_changes_nothing_more(self):
        d = "<details>\n<summary>Setup</summary>\nFixed in `abc1234`, see `https://example.com/a`.\nThe \"test_a\" test passed; Example lint failed.\n</details>\n\n```\npassed\n```\n"
        once = fx(d, CN)
        self.assertNotEqual(once, d)
        self.assertEqual(fx(once, CN), once)

    def test_the_draft_keeps_its_shape(self):
        d = "# Title\n\nFixed in `abc1234`. It passed.\n\n- Item `def5678` failed.\n- Another one.\n\n> Quote passed.\n\n<details>\n<summary>x</summary>\nIn here.\n</details>\n"
        shape = lambda t: [(k, lv, len(parts)) for k, parts, lv in furbish._blocks(t.split("\n"), None)]
        self.assertEqual(shape(fx(d, CN)), shape(d))

    def test_random_drafts_keep_their_shape_and_are_fixed_once(self):
        import random
        rnd = random.Random(7)
        bits = ["Fixed in", "`abc1234`", "`https://e.com/a`", "passed", "failed", "Example lint", '"test_a"', "[l](https://e.com)", "[`abc1234`](u)", "<details>", "</details>", "<summary>x</summary>", "</summary>", "```", "<!--", "-->", "> q", "| a |", "- item", "1. item", "# Head", "---", "===", "", "", "\t", "  ", "text here.", "More words.", "`x`", "``", "\u201ctest_b\u201d", "- [ ] box", "<b>", "</b>", "@someone", "`https://e.com/<!--`", "`https://e.com/<summary>`", "<summary>", "~~~", "`", "\\`", '"', "\u201c", "\u201d", "[a", "b]", "[ref][1]", "[1]: u", "\ufeff", "a | b", "passed`x`", "    "]
        shape = lambda t: [(k, lv, len(parts)) for k, parts, lv in furbish._blocks(t.split("\n"), None)]
        refused = 0
        for _ in range(1500):
            d = "\n".join(" ".join(rnd.choice(bits) for _ in range(rnd.randint(0, 5))) for _ in range(rnd.randint(1, 9))) + "\n"
            try:
                once = fx(d, CN)
            except furbish.Refused:
                refused += 1
                continue
            self.assertEqual(shape(once), shape(d), d)
            self.assertEqual(fx(once, CN), once, d)
        self.assertLessEqual(refused, 10)

    def test_hostile_text_stays_fast(self):
        names = {"code_names": {"quoted_tests": True, "checks": [f"Check number {i}" for i in range(30)], "states": ["passed", "failed", "skipped"]}}
        cases = ["`a` " * 65000, "[a" * 130000, "[a](" * 65000, '"a ' * 86000, "<a " * 86000, "http://a " * 30000, "word " * 52000, "`abc1234` " * 28000, "passed " * 37000, '"test_a" ' * 28000, "\u201c" * 130000, "Check number 1 " * 17000, "a" + "`" * 200000, "![a" * 86000, "</summary>\ntext\n" * 17000, "<details>\n" * 26000, "Yes. " * 52000, "- a b c.\n" * 30000, ("`abcdef1`\n\n\n\n" * 20000)[:260000], "passed\n" * 37000, "[a" * 130000]
        for d in cases:
            t = time.perf_counter()
            fx(d, names)
            self.assertLess(time.perf_counter() - t, 2.0, d[:14])

    def test_a_262_kb_draft_is_fixed_in_under_a_second(self):
        with open(os.path.join(DRAFTS, "pr-body.md"), encoding="utf-8") as f:
            body = f.read()
        big = (body * (262000 // len(body) + 1))[:262000]
        names = {"footer": FOOTER, "code_names": {"quoted_tests": True, "checks": [f"Check number {i}" for i in range(30)], "states": ["passed", "failed", "skipped"]}}
        t = time.perf_counter()
        fx(big, names)
        self.assertLess(time.perf_counter() - t, 1.0)


class TestFixReviewFixes(unittest.TestCase):
    P = {"footer": r"^-- x$", "code_names": {"quoted_tests": True, "checks": ["Example lint", "Example"], "states": ["passed", "failed"]}}

    def same(self, *drafts):
        for d in drafts:
            self.assertEqual(fx(d, self.P), d, d)

    def test_constructs_that_run_over_several_lines_are_left_alone(self):
        self.same("see `foo\nbar passed baz` end\n", "[foo\nbar `abcdef1` baz](http://x)\n", "foo [bar\nbaz passed](http://x.y)\n", 'He said "foo bar\nbaz `abcdef1` end" ok\n', "He said \u201cfoo bar\nbaz `abcdef1` end\u201d ok\n")

    def test_indented_and_nested_code_is_left_alone(self):
        self.same("para\n\n    line1\n    line2 `abcdef1`\n", "para\n\n    - code `abcdef1`\n", "1. item\n\n    ```\n    code `abcdef1`\n    ```\n", "- a\n  - b\n    ```\n    x `abcdef1`\n    ```\n", "\tcode `abcdef1`\n")

    def test_blank_lines_are_not_put_into_quotes_tables_code_or_templates(self):
        self.same("> <details>\n> <summary>x</summary>\n> body\n> </details>\n", "| a | <summary>x</summary> |\n| b | c |\n", "text\n\n    <details>\n    <summary>x</summary>\n    code\n    </details>\n", "\ufeff```\n</summary>\ntext\n```\n")
        self.assertEqual(fx("<summary>x</summary>\nText.\n", None, frozenset({"<summary>x</summary>"})), "<summary>x</summary>\nText.\n")

    def test_a_quote_inside_a_list_item_is_left_alone(self):
        self.same("- > quote in list `abcdef1`\n", "1. > quote passed\n", "- - nested `abcdef1`\n")

    def test_reference_links_and_nested_brackets_are_left_alone(self):
        self.same("[ref `abcdef1`][1]\n\n[1]: http://x.y\n", "[passed]\n\n[passed]: http://x.y\n", "[a `abcdef1` [b] c](http://x.y)\n", "[a [b `abcdef1`]](http://x.y)\n", "![alt passed](x.png)\n")

    def test_tables_without_a_leading_pipe_are_left_alone(self):
        self.same("name | sha\n--- | ---\nfoo | `abcdef1`\n", "| a | b |\n|---|---|\nfoo | `abcdef1`\n")

    def test_every_kind_of_checkbox_item_is_left_alone(self):
        self.same("1. [ ] `abcdef1`\n", "1. [x] passed\n", "- - [ ] `abcdef1`\n", "\ufeff- [ ] `abcdef1`\n", "- [ ] foo\n  `abcdef1` bar passed\n")
        self.assertEqual(fx("\ufeffThe template passed\n", self.P, frozenset({"The template passed"})), "\ufeffThe template passed\n")

    def test_text_next_to_a_cut_out_comment_is_left_alone(self):
        self.same("<!-- a\nb -->`abcdef1`\n", "pre <!-- c\nd --> post `abcdef1`\n")
        self.assertEqual(fx("-->\nfoo `abcdef1`\n"), "-->\nfoo abcdef1\n")

    def test_stray_and_escaped_backticks_make_a_block_untouchable(self):
        self.same("a ` b passed c", "\\`abcdef1`\n", "a `` b passed\n")

    def test_new_code_never_joins_old_code(self):
        self.same("passed`x`\n", "`x`passed")
        self.assertEqual(fx('"test_x""test_y"', self.P), '`test_x`"test_y"')
        self.assertEqual(fx(fx('"test_x""test_y"', self.P), self.P), '`test_x`"test_y"')

    def test_a_stray_quote_mark_does_not_make_a_second_run_change_more(self):
        for d in ('Fixed in b] " `https://e.com/a`\n"test_a" tail.\n', 'He said " and `abcdef1` then "test_a" end.\n'):
            once = fx(d, self.P)
            self.assertEqual(fx(once, self.P), once, d)

    def test_a_quote_mark_inside_code_does_not_pair_with_real_quotes(self):
        self.same('Use `"` here: "x `abcdef1` y"\n')

    def test_a_lone_sha_in_a_wrapped_paragraph_is_still_fixed(self):
        self.assertEqual(fx("A long line that\nsays `abcdef1` and\npassed.\n", self.P), "A long line that\nsays abcdef1 and\n`passed`.\n")

    def test_the_diff_of_many_far_apart_hunks_is_made_in_linear_time(self):
        d = ("`abcdef1`\n\n\n\n" * 20000)[:260000]
        r = furbish.fix_text(d)
        t = time.perf_counter()
        rows = furbish._hunks(r.old, r.new, r.tags)
        self.assertLess(time.perf_counter() - t, 1.0)
        self.assertGreater(len(rows), 20000)

    def test_a_check_name_must_start_with_a_letter_or_a_digit(self):
        with self.assertRaises(furbish.ConfigError) as cm:
            furbish._validate_code_names({"checks": [".NET build"]}, "a/b")
        self.assertIn(".NET build", str(cm.exception))
        with self.assertRaises(furbish.ConfigError):
            furbish._validate_code_names({"states": [""]}, "a/b")
        self.assertEqual(furbish._validate_code_names({"checks": ["C++ build", "3.11 tests"]}, "a/b")["checks"], ["C++ build", "3.11 tests"])

    def test_only_test_like_quoted_names_become_code(self):
        p = {"code_names": {"quoted_tests": True}}
        for t in ('The "Testimony" and "Test" and "testing" words.', 'A "foo.bar" name.'):
            self.assertEqual(fx(t + "\n", p), t + "\n", t)
        self.assertEqual(fx('The "TestOpen" and "testOpen" and "Test1" cases.\n', p), "The `TestOpen` and `testOpen` and `Test1` cases.\n")


class TestFixCli(ConfigCase):
    DRAFT = "<details>\n<summary>Setup</summary>\nFixed in `abc1234`.\n</details>\n"

    def env(self, **extra):
        e = {"HOME": self.tmp, "PATH": "/usr/bin:/bin"}
        e.update(extra)
        return e

    def run_fix(self, *args, cwd=None, **extra):
        return subprocess.run([sys.executable, "-I", SCRIPT, "fix", *args], capture_output=True, text=True, env=self.env(**extra), cwd=cwd)

    def draft(self, text=None, name="draft.md"):
        return self.write(self.DRAFT if text is None else text, name)

    def read(self, path):
        with open(path, "rb") as f:
            return f.read()

    def test_without_write_it_prints_the_changes_and_touches_nothing(self):
        path = self.draft()
        before = self.read(path)
        r = self.run_fix(path)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read(path), before)
        self.assertEqual(r.stdout.splitlines(), [f"--- {path}", f"+++ {path}", "@@ -2,3 +2,5 @@", " <summary>Setup</summary>", "-Fixed in `abc1234`.", "+", "+Fixed in abc1234.", "+", " </details>"])
        self.assertIn("--write", r.stderr)

    def test_with_write_it_changes_the_file_and_prints_the_same_diff(self):
        path = self.draft()
        dry = self.run_fix(path)
        r = self.run_fix(path, "--write")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, dry.stdout)
        self.assertEqual(r.stderr, "")
        self.assertEqual(self.read(path), b"<details>\n<summary>Setup</summary>\n\nFixed in abc1234.\n\n</details>\n")

    def test_a_clean_draft_prints_nothing_and_exits_0(self):
        path = self.draft("Nothing to fix here.\n")
        for extra in ((), ("--write",)):
            r = self.run_fix(path, *extra)
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertEqual(self.read(path), b"Nothing to fix here.\n")

    def test_running_it_again_after_write_prints_nothing(self):
        path = self.draft()
        self.run_fix(path, "--write")
        r = self.run_fix(path, "--write")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_the_repo_profile_turns_on_code_names(self):
        cfg = self.write('[repo."a/b".code_names]\nstates = ["passed"]\n', "cfg.toml")
        path = self.draft("It passed.\n")
        self.assertEqual(self.run_fix(path, FURBISH_CONFIG=cfg).stdout, "")
        r = self.run_fix(path, "--repo", "a/b", "--write", FURBISH_CONFIG=cfg)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read(path), b"It `passed`.\n")

    def test_template_lines_from_the_profile_are_left_alone(self):
        tpl = self.write("It passed here.\n", "tpl.md")
        cfg = self.write(f'[repo."a/b"]\npr_template = {json.dumps(tpl)}\n[repo."a/b".code_names]\nstates = ["passed"]\n', "cfg.toml")
        path = self.draft("It passed here.\n\nThen it passed again.\n")
        self.run_fix(path, "--repo", "a/b", "--write", FURBISH_CONFIG=cfg)
        self.assertEqual(self.read(path), b"It passed here.\n\nThen it `passed` again.\n")

    def test_the_footer_from_the_profile_is_left_alone(self):
        cfg = self.write(f'[repo."a/b"]\nfooter = {json.dumps(FOOTER)}\n[repo."a/b".code_names]\nstates = ["passed"]\n', "cfg.toml")
        path = self.draft("It passed.\n\n-- Sent from the made-up example footer\n")
        self.run_fix(path, "--repo", "a/b", "--write", FURBISH_CONFIG=cfg)
        self.assertEqual(self.read(path), b"It `passed`.\n\n-- Sent from the made-up example footer\n")

    def test_things_that_cannot_run_exit_2_with_a_plain_message(self):
        path = self.draft()
        for args in ((os.path.join(self.tmp, "missing.md"),), (path, "--repo", "x/y")):
            r = self.run_fix(*args)
            self.assertEqual((r.returncode, r.stdout), (2, ""), args)
            self.assertTrue(r.stderr.startswith("furbish: "), r.stderr)
            self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(self.run_fix().returncode, 2)

    def test_a_draft_that_is_not_utf8_is_never_rewritten(self):
        path = self.draft("")
        with open(path, "wb") as f:
            f.write(b"Caf\xe9 `abc1234`.\n")
        for extra in ((), ("--write",)):
            r = self.run_fix(path, *extra)
            self.assertEqual((r.returncode, r.stdout), (2, ""))
            self.assertIn("UTF-8", r.stderr)
        self.assertEqual(self.read(path), b"Caf\xe9 `abc1234`.\n")

    def test_control_characters_are_not_printed(self):
        path = self.draft("Esc \x1b[mred\x1b]t\x07 `abc1234` \u202e done.\n", "d\x1b[31mx.md")
        r = self.run_fix(path)
        self.assertEqual(r.returncode, 0)
        for bad in ("\x1b", "\x07", "\u202e"):
            self.assertNotIn(bad, r.stdout)
        self.assertIn("red", r.stdout)

    def test_crlf_and_the_file_mode_survive_a_write_and_nothing_is_left_behind(self):
        path = self.draft("")
        with open(path, "wb") as f:
            f.write(b"One `abc1234`.\r\nTwo.\r\n")
        os.chmod(path, 0o640)
        before = sorted(os.listdir(self.tmp))
        r = self.run_fix(path, "--write")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.read(path), b"One abc1234.\r\nTwo.\r\n")
        self.assertNotIn("\r", r.stdout)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o640)
        self.assertEqual(sorted(os.listdir(self.tmp)), before)

    def test_a_symlinked_draft_is_written_through_the_link(self):
        real = self.draft("One `abc1234`.\n", "real.md")
        link = os.path.join(self.tmp, "link.md")
        os.symlink(real, link)
        self.assertEqual(self.run_fix(link, "--write").returncode, 0)
        self.assertTrue(os.path.islink(link))
        self.assertEqual(self.read(real), b"One abc1234.\n")

    def test_a_relative_path_is_found(self):
        self.draft("One `abc1234`.\n")
        self.assertEqual(self.run_fix("draft.md", "--write", cwd=self.tmp).returncode, 0)
        self.assertEqual(self.read(os.path.join(self.tmp, "draft.md")), b"One abc1234.\n")

    def test_the_diff_shows_context_and_groups_nearby_changes(self):
        path = self.draft("A `abc1234`.\nB.\nC `def5678`.\nD.\nE.\nF.\nG `0123abc`.\n")
        r = self.run_fix(path)
        self.assertEqual(r.stdout.splitlines()[2:], ["@@ -1,4 +1,4 @@", "-A `abc1234`.", "+A abc1234.", " B.", "-C `def5678`.", "+C def5678.", " D.", "@@ -6,2 +6,2 @@", " F.", "-G `0123abc`.", "+G 0123abc."])

    def test_help_lists_fix_as_working(self):
        r = subprocess.run([sys.executable, "-I", SCRIPT, "--help"], capture_output=True, text=True, env=self.env())
        self.assertNotIn("planned: safe mechanical edits", r.stdout)
        self.assertIn("--write", self.run_fix("--help").stdout)

    def test_a_closed_pipe_does_not_lose_the_write(self):
        path = self.draft("One `abc1234`.\n")
        cmd = f"set -o pipefail; {shlex.quote(sys.executable)} -I {shlex.quote(SCRIPT)} fix {shlex.quote(path)} --write | head -c0; echo ${{PIPESTATUS[0]}}"
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env=self.env())
        self.assertEqual(r.stdout.strip(), "0")
        self.assertNotIn("Exception", r.stderr)
        self.assertEqual(self.read(path), b"One abc1234.\n")

    def test_a_262_kb_draft_through_the_command_takes_under_two_seconds(self):
        with open(os.path.join(DRAFTS, "pr-body.md"), encoding="utf-8") as f:
            body = f.read()
        path = self.draft((body * (262000 // len(body) + 1))[:262000] + "\nFixed in `abc1234`.\n")
        t = time.perf_counter()
        r = self.run_fix(path, "--write")
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        self.assertLess(time.perf_counter() - t, 2.0)


SPLIT_A = "The configuration loader reads every key and reports each mistake with the path of the file"
SPLIT_B = "the command line prints only the problems that it finds in the draft."


def sg(text, profile=None, exempt=frozenset()):
    return furbish.split_suggestions(text, profile, exempt)


class TestSplitBreaks(unittest.TestCase):
    def test_the_places_a_sentence_can_be_cut(self):
        b = furbish._breaks
        self.assertEqual(b("Run the tests; then push it."), [(13, 15)])
        self.assertEqual(b("It is slow - and it fails."), [(10, 13)])
        self.assertEqual(b("It ran \u2014 and failed."), [(6, 9)])
        self.assertEqual(b("It ran \u2013 and failed."), [(6, 9)])
        self.assertEqual(b("It is slow, and it fails, but it runs."), [(10, 12), (24, 26)])
        self.assertEqual(b("A, so B, or C, yet D."), [(1, 3), (7, 9), (13, 15)])

    def test_things_that_are_not_places_to_cut(self):
        b = furbish._breaks
        for t in ("It is slow and it fails.", "It is slow, which is bad.", "It is slow, because it fails.", "It is slow, And it fails.", "It is slow,and it fails.", "It is slow-and it fails.", "; start.", "end;", "end; ", "It is slow, and", "A-B and C.", "Run it: then stop."):
            self.assertEqual(b(t), [], t)

    def test_marks_inside_code_links_urls_tags_and_quotes_are_ignored(self):
        b = furbish._breaks
        self.assertEqual(b("Use `a; b` here; then stop."), [(15, 17)])
        self.assertEqual(b("See [a, and b](http://x.y) now, and go."), [(30, 32)])
        self.assertEqual(b("See http://x.y/a;b now; go."), [(22, 24)])
        self.assertEqual(b('He said "a; b" and left; later.'), [(23, 25)])
        self.assertEqual(b("A <b title='x; y'>b</b> c; d."), [(25, 27)])

    def test_a_cut_cannot_leave_a_bracket_or_emphasis_open(self):
        b = furbish._breaks
        self.assertEqual(b("A (b; c) d; e."), [(10, 12)])
        self.assertEqual(b("A **b; c** d; e."), [(12, 14)])
        self.assertEqual(b("A *b; c* d; e."), [(10, 12)])

    def test_hostile_text_stays_fast(self):
        for d in ("a; " * 86000, "a, and " * 37000, "(" * 130000 + "; x", "a - " * 65000, "", '"a; ' * 65000, "*" * 200000 + "; b", "[a, and " * 30000, "`a; " * 65000, "<a; " * 65000):
            t = time.perf_counter()
            furbish._breaks(d)
            self.assertLess(time.perf_counter() - t, 2.0, d[:12])


class TestSplitSuggestions(unittest.TestCase):
    def one(self, text, **kw):
        found = sg(text, **kw)
        self.assertEqual(len(found), 1, found)
        return found[0]

    def test_a_hard_sentence_is_cut_where_both_halves_read_easier(self):
        x = self.one(f"{SPLIT_A}, and {SPLIT_B}\n")
        self.assertEqual((x.line, x.sid, round(x.grade)), (1, "S1", 15))
        self.assertEqual(x.first, SPLIT_A + ".")
        self.assertEqual(x.second, "And " + SPLIT_B)
        self.assertEqual([round(g) for g in x.grades], [9, 5])

    def test_every_kind_of_mark_can_be_the_cut(self):
        for mid, word in ((";", "The"), (" -", "The"), (" \u2014", "The"), (",", "So"), (", or", "Or"), (", yet", "Yet"), (", but", "But")):
            text = f"{SPLIT_A}{mid}{' ' if mid.endswith(';') else ' '}{SPLIT_B if word == 'The' else word.lower() + ' ' + SPLIT_B}"
            if mid == ",":
                text = f"{SPLIT_A}, so {SPLIT_B}"
            x = self.one(text + "\n")
            self.assertEqual(x.first, SPLIT_A + ".", mid)
            self.assertTrue(x.second.startswith(word if word != "The" else "The command"), (mid, x.second))

    def test_the_best_cut_is_the_one_with_the_easier_harder_half(self):
        text = "The configuration loader reads every key, and it reports each mistake with the path of the file, but the command line prints only the problems that it finds in the draft.\n"
        x = self.one(text)
        self.assertEqual(x.first, "The configuration loader reads every key, and it reports each mistake with the path of the file.")
        self.assertEqual(x.second, "But the command line prints only the problems that it finds in the draft.")

    def test_a_cut_that_makes_a_half_harder_is_not_suggested(self):
        for t in ("Unquestionably, the implementation's architectural characteristics necessitate comprehensive reconsideration; however, nobody noticed the problem until the maintainers examined the repository.", "The authentication middleware implementation validates cryptographic signatures - and the infrastructure monitoring subsystem records everything.", "Run the tests first, but remember that the continuous integration pipeline sometimes takes considerably longer than expected."):
            self.assertGreaterEqual(furbish.ari(furbish._cleaned(t)), 10)
            self.assertEqual(sg(t + "\n"), [], t)

    def test_easy_sentences_and_sentences_with_no_mark_are_left_alone(self):
        for t in ("The unit tests all pass on Linux, so the build is fine.", "Unquestionably, the implementation's architectural characteristics necessitate comprehensive reconsideration.", f"{SPLIT_A} and {SPLIT_B}", f"{SPLIT_A}, which {SPLIT_B}"):
            self.assertEqual(sg(t + "\n"), [], t)

    def test_a_half_with_fewer_than_three_words_is_not_a_half(self):
        self.assertEqual(sg("Done, and the continuous integration infrastructure configuration validates comprehensively every authentication repository.\n"), [])
        self.assertEqual(sg("The continuous integration infrastructure configuration validates comprehensively every authentication repository; done.\n"), [])

    def test_marks_in_code_links_urls_and_quotes_are_not_used(self):
        for mark in ("`path; of; the; file`", "[the path, and the file](http://x.y)", "http://x.y/a;b;c", '"a; b; c"'):
            t = f"The configuration loader reads every key and reports each mistake with {mark} and the command line prints only the problems that it finds in the draft."
            self.assertEqual(sg(t + "\n"), [], mark)
            t = f"The configuration loader reads every key and reports each mistake with {mark}; the command line prints only the problems that it finds in the draft."
            x = self.one(t + "\n")
            self.assertTrue(x.first.endswith(mark + "."), (mark, x.first))

    def test_a_cut_cannot_split_brackets_or_emphasis(self):
        t = f"{SPLIT_A} (which is shown in full; and which is clear) and {SPLIT_B}"
        self.assertEqual(sg(t + "\n"), [])
        t = f"{SPLIT_A} and **{SPLIT_B[:-1]}; in full** here."
        self.assertEqual(sg(t + "\n"), [])

    def test_headings_checkboxes_templates_footer_and_labels(self):
        hard = f"{SPLIT_A}; {SPLIT_B}"
        self.assertEqual(sg(f"# {hard}\n"), [])
        self.assertEqual(sg(f"- [ ] {hard}\n"), [])
        self.assertEqual(sg(f"{hard}\n", None, frozenset({hard})), [])
        self.assertEqual(sg(f"Fine.\n\n{hard}\n", {"footer": "^" + re.escape(hard) + "$"}), [])
        x = self.one(f"**Result:** {hard}\n")
        self.assertEqual(x.first, "**Result:** " + SPLIT_A + ".")

    def test_a_quote_and_a_list_item_are_looked_at(self):
        self.assertEqual(len(sg(f"- {SPLIT_A}; {SPLIT_B}\n")), 1)
        self.assertEqual(len(sg(f"> {SPLIT_A}; {SPLIT_B}\n")), 1)

    def test_one_suggestion_for_each_hard_sentence_in_line_order(self):
        d = f"Fine one.\n\n{SPLIT_A}; {SPLIT_B}\n\nAnother fine one.\n\n{SPLIT_A}, so {SPLIT_B}\n"
        found = sg(d)
        self.assertEqual([(x.line, x.sid) for x in found], [(3, "S2"), (7, "S4")])

    def test_a_sentence_over_2000_characters_is_skipped(self):
        part = f"{SPLIT_A}; {SPLIT_B[:-1]} "
        long = (part * 20).strip() + "."
        self.assertGreater(len(long), 2000)
        self.assertEqual(sg(long + "\n"), [])
        self.assertEqual(len(sg(part.strip() + "\n")), 1)

    def test_the_second_half_keeps_its_own_markup(self):
        x = self.one(f"{SPLIT_A}; `code` {SPLIT_B}\n")
        self.assertTrue(x.second.startswith("`code` the"), x.second)
        x = self.one(f"{SPLIT_A}; [the](http://x.y) command line prints only the problems that it finds in the draft.\n")
        self.assertTrue(x.second.startswith("[the](http://x.y)"), x.second)

    def test_the_ids_are_the_ones_check_prints(self):
        d = f"Fine one.\n\n{SPLIT_A}; {SPLIT_B}\n"
        self.assertEqual([x.sid for x in sg(d)], ["S2"])
        self.assertEqual([p.sid for p in furbish.check(d, None, True) if p.rule == "grade"], ["S2"])

    def test_a_262_kb_draft_takes_under_a_second(self):
        with open(os.path.join(DRAFTS, "pr-body.md"), encoding="utf-8") as f:
            body = f.read()
        big = (body * (262000 // len(body) + 1))[:262000]
        t = time.perf_counter()
        sg(big, {"footer": FOOTER})
        self.assertLess(time.perf_counter() - t, 1.0)

    def test_hostile_text_stays_fast(self):
        hard = f"{SPLIT_A}, and {SPLIT_B[:-1]}; and "
        cases = ["a, and " * 37000, "a; " * 86000, (hard * 12).strip() + ". ", "Yes. " * 52000, (hard * 15).strip() + ".\n", "`a; " * 65000, "(" * 130000 + "; x", f"{SPLIT_A}; {SPLIT_B}\n" * 1500]
        for d in cases:
            for text in (d, (d + "\n") * (260000 // (len(d) + 1) if len(d) < 3000 else 1)):
                t = time.perf_counter()
                sg(text[:262000], {"footer": FOOTER})
                self.assertLess(time.perf_counter() - t, 2.0, d[:14])


class TestSplitReviewFixes(unittest.TestCase):
    A = "Several different sentences should remain readable under every possible circumstance"
    B = "because nobody wants complicated paragraphs without obvious breaking points anywhere"
    R = "these tiny planes hold about eight small cakes while those large crews bake fresh bread under every green hill"

    def found(self, text):
        return sg(text + "\n")

    def test_the_worst_case_of_many_marks_in_many_long_sentences_stays_fast(self):
        part = (("`c` [l](u) ; " * 200)[:1999].rstrip(" ;-,") + ". ")
        big = (part * 200)[:260000]
        t = time.perf_counter()
        sg(big)
        self.assertLess(time.perf_counter() - t, 2.0)

    def test_a_cut_is_never_made_inside_an_open_bracket_or_emphasis(self):
        self.assertEqual(self.found(self.A.replace("remain ", "remain (readable ") + "; " + self.B + ")."), [])
        self.assertEqual(self.found("*Several different sentences should remain readable under every possible circumstance; " + self.B + "*."), [])
        self.assertEqual(self.found("*Several different `a*b` sentences should remain readable under every possible circumstance; " + self.B + "*."), [])

    def test_brackets_and_stars_in_code_urls_and_a_stray_close_do_not_block_a_cut(self):
        b = furbish._breaks
        self.assertEqual(len(b(self.A + " :) ; " + self.B + ".")), 1)
        self.assertEqual(len(b("1) " + self.A + "; " + self.B + ".")), 1)
        self.assertEqual(len(b("Use `(` here; " + self.B + ".")), 1)
        self.assertEqual(len(b("Use `a*b` here; " + self.B + ".")), 1)
        self.assertEqual(len(b("Use https://x.io/a*b here; " + self.B + ".")), 1)
        self.assertEqual(len(b("Use [a (b](http://x.io/(c) here; " + self.B + ".")), 1)

    def test_a_quote_that_runs_over_sentences_is_never_cut(self):
        self.assertEqual(self.found('The log says "' + self.A + "; " + self.B + '. Done."'), [])
        self.assertEqual(self.found(self.A + "; " + self.B + '." Then it stopped.'), [])
        self.assertEqual(self.found("The log says \u201c" + self.A + "; " + self.B + ". Done.\u201d"), [])
        self.assertEqual(len(self.found(self.A + "; " + self.B + ' "ok".')), 1)

    def test_a_link_with_a_closing_bracket_inside_is_never_torn(self):
        for inner in ("\\]", "`]`", "\\["):
            self.assertEqual(self.found(f"See [Several different sentences should remain readable {inner} under every possible circumstance; " + self.B + "](http://x.io/page)."), [], inner)
        self.assertEqual(furbish._brackets("a [b \\] c](u) d"), [(2, 10)])
        self.assertEqual(furbish._brackets("a [b `]` c](u) d"), [(2, 11)])

    def test_a_second_half_that_starts_with_a_url_keeps_its_case_and_one_that_starts_with_a_name_is_not_offered(self):
        for first in ("https://example.com/x/y.md", "http://example.com"):
            x = sg(self.A + "; " + first + " " + self.B + ".\n")
            self.assertEqual(len(x), 1, first)
            self.assertTrue(x[0].second.startswith(first), (first, x[0].second))
        for first in ("www.example.com", "example.com/x", "readme.md", "a_b", "x@y.io", "co-op"):
            self.assertEqual(sg(self.A + "; " + first + " " + self.B + ".\n"), [], first)
        x = sg(self.A + "; " + self.B + ".\n")
        self.assertTrue(x[0].second.startswith("Because"))

    def test_the_grades_shown_are_the_grades_of_the_sentences_shown(self):
        for mid in ("; ", " - ", ", but ", "; https://github.com/example/project/blob/main/documentation/architecture/overview.md "):
            for x in sg(self.A + mid + self.B + ".\n"):
                self.assertAlmostEqual(furbish.ari(furbish._cleaned(x.first)), x.grades[0], places=6)
                self.assertAlmostEqual(furbish.ari(furbish._cleaned(x.second)), x.grades[1], places=6)

    def test_the_first_half_never_ends_in_two_full_stops(self):
        for tail in (" etc.", " e.g.", "!", "?", " ...", " \u2026"):
            x = sg(self.A + tail + ", but " + self.B + ".\n")
            self.assertEqual(len(x), 1, tail)
            self.assertFalse(x[0].first.endswith(".."), x[0].first) if not tail.endswith("...") else None
            self.assertEqual(x[0].first.count(". ."), 0)
        self.assertTrue(sg(self.A + " etc., but " + self.B + ".\n")[0].first.endswith("etc."))

    def test_the_first_half_keeps_a_hyphen_or_colon_that_belongs_to_its_last_word(self):
        x = sg(self.A + " see https://example.com/my-page-; " + self.B + ".\n")
        self.assertTrue(x[0].first.endswith("my-page-."), x[0].first)

    def test_an_html_entity_is_not_a_mark(self):
        self.assertEqual(furbish._breaks("A &amp; B &#38; C &lt; D."), [])
        self.assertEqual(furbish._breaks("A &nbsp; B."), [])
        self.assertEqual(len(furbish._breaks("A &amp; B; C.")), 1)
        self.assertEqual(self.found(self.A + " &amp; " + self.B + " &amp; " + self.B + "."), [])

    def test_a_half_needs_three_real_words(self):
        self.assertEqual(self.found("Banana mangoes ...; " + self.R + "."), [])
        self.assertEqual(self.found("Great news \U0001F389; " + self.R + "."), [])
        self.assertIsNone(furbish._half("Banana mangoes ..."))
        self.assertIsNotNone(furbish._half("Banana mangoes taste great"))

    def test_the_exemptions_know_a_bom_ordered_checkboxes_and_odd_line_breaks_in_templates(self):
        hard = self.A + "; " + self.B + "."
        for d in ("\ufeff# " + hard, "\ufeff- [ ] " + hard, "1. [ ] " + hard, "1) [x] " + hard, "10. [ ] " + hard):
            self.assertEqual(sg(d + "\n"), [], d)
            self.assertEqual([p for p in furbish.check(d + "\n", None, True) if p.rule == "grade"], [], d)
        self.assertEqual(len(sg("1. " + hard + "\n")), 1)


class TestTemplateLines(ConfigCase):
    def lines(self, body):
        path = self.write(body, "tpl.md")
        return furbish._template_lines({"pr_template": path})

    def test_a_template_is_read_line_by_line_on_newlines_only(self):
        got = self.lines("A line\u2028with a break.\x0bAnd more.\x85Even more.\nNext line.\r\nThird.\n")
        self.assertEqual(got, frozenset({"A line\u2028with a break.\x0bAnd more.\x85Even more.", "Next line.", "Third."}))

    def test_a_template_with_a_byte_order_mark_still_matches_its_first_line(self):
        self.assertIn("First line.", self.lines("\ufeffFirst line.\nSecond.\n"))


FA = "Several different sentences should remain readable under every possible circumstance"
FB = "because nobody wants complicated paragraphs without obvious breaking points anywhere"


class TestFableReview(ConfigCase):
    def test_a_table_without_a_leading_pipe_is_not_prose(self):
        t = "Name | Count\n---|---\nThe first row has text. | one\nThe second row. | two\n"
        self.assertEqual(texts(t), [])
        t = "Intro.\n\n| a | b |\n|---|---|\nfoo | bar\nbaz\n\nAfter the table.\n"
        self.assertEqual(texts(t), ["Intro.", "After the table."])
        self.assertEqual(texts("Intro.\nName | Count\n--- | ---\nrow | 1\n\nEnd here.\n"), ["Intro.", "End here."])
        self.assertEqual(texts("A | B\n--|--\nx | y\n# Heading\nProse after.\n"), ["Heading", "Prose after."])
        self.assertEqual(texts("Fine | it is\nand done.\n"), ["Fine | it is and done."])

    def test_set_cannot_destroy_a_table_without_a_leading_pipe(self):
        t = "Name | Count\n---|---\nThe first row has text. | one\nThe second row. | two\n"
        with self.assertRaises(furbish.ConfigError):
            furbish.set_sentence(t, "S1", "New sentence.")

    def test_indented_code_is_not_prose_and_not_checked(self):
        t = "Run this:\n\n    @someone `abc1234` is in the code. The thing never ran at all today.\n\nDone.\n"
        self.assertEqual(texts(t), ["Run this:", "Done."])
        self.assertEqual(furbish.check(t), [])
        self.assertEqual(texts("One.\n\n    code one\n\n    code two\n\nBack.\n"), ["One.", "Back."])
        self.assertEqual(texts("One.\n\n\tcode\n\nBack.\n"), ["One.", "Back."])
        with self.assertRaises(furbish.ConfigError):
            furbish.set_sentence(t, "S3", "Rewritten here.")

    def test_four_spaces_are_not_code_in_a_list_a_continuation_or_a_wrapped_paragraph(self):
        self.assertEqual(texts("- item\n\n    continued paragraph of the item.\n\nAfter.\n"), ["item", "continued paragraph of the item.", "After."])
        self.assertEqual(texts("A line\n    wrapped under it.\n"), ["A line wrapped under it."])
        self.assertEqual(texts("1. one\n   two\n\n    three\n"), ["one two", "three"])

    def test_a_details_tag_inside_code_does_not_fold_the_rest_of_the_post(self):
        p = {"tldr": "required", "tldr_words": 5, "tldr_max_sentences": 3}
        d = "Use the `<details>` tag for long logs.\n\n" + "Many words here indeed. " * 20 + "\n"
        self.assertEqual([x.rule for x in furbish.check(d, p)], ["tldr"])

    def test_the_tldr_rule_reads_a_prefix_a_byte_order_mark_and_a_heading_after_the_tldr(self):
        pp = {"first_line_prefix": "Example:", "tldr": "required", "tldr_words": 1, "tldr_max_sentences": 3}
        self.assertEqual(furbish.check("Example: **TL;DR:** Fixed it.\n\nBody.\n", pp), [])
        self.assertEqual(furbish.check("Example:**TL;DR:** Fixed it.\n\nBody.\n", pp), [])
        self.assertEqual(furbish.check("\ufeffExample: **TL;DR:** Fixed it.\n", pp), [])
        q = {"tldr": "required", "tldr_words": 1, "tldr_max_sentences": 2}
        self.assertEqual(furbish.check("**TL;DR:** One. Two.\n## Heading here\n\nBody.\n", q), [])
        self.assertEqual(len(furbish.check("**TL;DR:** One. Two. Three.\n## Heading here\n", q)), 1)

    def test_one_grader_for_check_and_split(self):
        d = "Press <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> to open it quickly.\n"
        self.assertEqual(furbish.check(d, None, True), [])
        self.assertEqual(furbish._cleaned("Run ``a ` b`` now and `x`."), "Run code now and code.")
        self.assertEqual(furbish._cleaned("A <b>bold</b> move with [a link](http://x.y) and http://x.y/z."), "A bold move with a link and link")
        self.assertFalse(hasattr(furbish.read_prose("One here.")[0], "grade"))

    def test_every_kind_of_heading_is_exempt_from_the_grade_and_from_split(self):
        hard = FA + "; " + FB + "."
        for d in ("# " + hard, "   ## " + hard, hard + "\n===", hard + "\n---", "\ufeff# " + hard):
            self.assertEqual([p for p in furbish.check(d + "\n", None, True) if p.rule == "grade"], [], d)
            self.assertEqual(sg(d + "\n"), [], d)
        self.assertEqual(len([p for p in furbish.check(hard + "\n", None, True) if p.rule == "grade"]), 1)

    def test_mentions_are_found_next_to_punctuation_but_not_in_links_urls_emails_or_code(self):
        for s in ('"@someone"', "'@someone'", "\u2014@someone", "[@someone]", "*@someone*", "hi,@someone", ">@someone", "(@someone)", "@someone", "a @someone b"):
            self.assertEqual([p.rule for p in furbish.check(s + "\n")], ["mention"], s)
        for s in ("[@x](http://y.z)", "a@b.com", "https://github.com/@x/y", "`@x`", "![@x](a.png)", "[see @x](http://y.z)"):
            self.assertEqual(furbish.check(s + "\n"), [], s)

    def test_the_licence_message_gives_an_example_that_fits(self):
        got = {p.message.split(" ")[0] + " " + p.message.split(" ")[1]: p.message.rsplit("for example ", 1)[1] for p in furbish.check("Under Apache 2.0 and BSD 3-Clause and BSD 2-Clause and GPLv2.\n")}
        self.assertEqual(sorted(got.values()), ["Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "GPL-2.0-only"])

    def test_a_missing_template_names_the_config_key(self):
        cfg = self.write('[repo."a/b"]\npr_template = "/nonexistent/tpl.md"\n', "cfg.toml")
        r = subprocess.run([sys.executable, "-I", SCRIPT, "check", "--repo", "a/b", self.write("Hi.\n", "d.md")], capture_output=True, text=True, env={"HOME": self.tmp, "PATH": "/usr/bin:/bin", "FURBISH_CONFIG": cfg})
        self.assertEqual(r.returncode, 2)
        self.assertIn("pr_template in the config", r.stderr)

    def test_the_details_message_says_formatted_not_displayed(self):
        d = "<details>\n<summary>x</summary>\nText.\n</details>\n"
        self.assertTrue(all("will not be formatted" in p.message for p in furbish.check(d)))

    def test_a_sha_that_starts_a_sentence_splits_the_same_bare_or_in_code(self):
        a = "Reverted the change. `abc1234` was the bad commit, which introduced the regression in the loader.\n\nThe test suite passes again.\n"
        b = furbish.fix_text(a).text
        self.assertEqual([x.text for x in furbish.read_prose(b)][:1], ["Reverted the change."])
        self.assertEqual(len(furbish.read_prose(b)), len(furbish.read_prose(a)))
        self.assertEqual(len(furbish.read_prose("See the doc. https://example.com/a explains it.")), 2)
        self.assertEqual(len(furbish.read_prose("See e.g. abc more. Then stop.")), 2)

    def test_fix_never_changes_how_many_sentences_there_are_unless_code_names_empty_one(self):
        import random
        rnd = random.Random(3)
        bits = ["Fixed in", "`abc1234`", "`https://e.com/a`", "was the bad commit.", "It broke.", "see", "and then", "Then it ran.", "`x`", "text here", "[l](http://e.com)", "More words follow here.", "<details>", "</details>", "<summary>x</summary>", "", "- item", "> q"]
        for _ in range(2500):
            d = "\n".join(" ".join(rnd.choice(bits) for _ in range(rnd.randint(1, 5))) for _ in range(rnd.randint(1, 7))) + "\n"
            try:
                once = fx(d)
            except furbish.Refused:
                continue
            self.assertEqual([x.text.replace("`", "") for x in furbish.read_prose(once)], [x.text.replace("`", "") for x in furbish.read_prose(d)], d)

    def test_a_split_applied_with_set_gives_two_sentences_to_the_reader(self):
        for mid in ("; ", " - ", ", but ", "; https://example.com/documentation "):
            for x in sg(FA + mid + FB + ".\n"):
                self.assertEqual(len(furbish.read_prose(x.first + " " + x.second)), 2, (mid, x.first, x.second))

    def test_a_cut_is_never_made_inside_underscore_or_strikethrough_emphasis(self):
        b = furbish._breaks
        self.assertEqual(b("A _b; c_ d."), [])
        self.assertEqual(b("A ~~b; c~~ d."), [])
        self.assertEqual(len(b("A snake_case_name; and more.")), 1)
        self.assertEqual(len(b("A _b_ c; d.")), 1)
        self.assertEqual(sg("_The configuration loader reads every key and reports each mistake with the path of the file; the command line prints only the problems that it finds_ in the draft.\n"), [])


class TestDiffsWithoutAFinalNewline(ConfigCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True, text=True, env={"HOME": self.tmp, "PATH": "/usr/bin:/bin"})

    def test_fix_marks_a_last_line_with_no_newline(self):
        path = self.write("A `abc1234` b.\nSecond line here.\nThird `def5678` end", "d.md")
        r = self.run_cli("fix", path)
        self.assertEqual(r.stdout.splitlines()[2:], ["@@ -1,3 +1,3 @@", "-A `abc1234` b.", "+A abc1234 b.", " Second line here.", "-Third `def5678` end", "\\ No newline at end of file", "+Third def5678 end", "\\ No newline at end of file"])

    def test_fix_marks_an_unchanged_last_line_that_is_context(self):
        path = self.write("A `abc1234` b.\nlast line no newline", "d.md")
        r = self.run_cli("fix", path)
        self.assertEqual(r.stdout.splitlines()[2:], ["@@ -1,2 +1,2 @@", "-A `abc1234` b.", "+A abc1234 b.", " last line no newline", "\\ No newline at end of file"])

    def test_set_marks_a_last_line_with_no_newline_and_only_then(self):
        path = self.write("One here. Two here.", "d.md")
        self.assertEqual(self.run_cli("set", path, "S2", "Deux.").stdout.splitlines()[3:], ["-One here. Two here.", "\\ No newline at end of file", "+One here. Deux.", "\\ No newline at end of file"])
        path = self.write("One here. Two here.\n", "e.md")
        self.assertEqual(self.run_cli("set", path, "S2", "Deux.").stdout.splitlines()[3:], ["-One here. Two here.", "+One here. Deux."])
        path = self.write("One here.\nTwo here.\nThree here.", "f.md")
        self.assertEqual(self.run_cli("set", path, "S1", "Un.").stdout.splitlines()[3:], ["-One here.", "+Un."])

    @unittest.skipUnless(shutil.which("patch"), "patch is not installed")
    def test_the_diffs_apply_with_patch(self):
        for body, args in (("A `abc1234` b.\nSecond line here.\nThird `def5678` end", ("fix",)), ("A `abc1234` b.\nlast `def5678`\n", ("fix",)), ("One here. Two here.", ("set", "S2", "Deux."))):
            path = self.write(body, "p.md")
            diff = self.write(self.run_cli(args[0], path, *args[1:]).stdout, "p.diff")
            r = subprocess.run(["patch", "--dry-run", path, diff], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, (body, r.stdout, r.stderr))
            self.assertNotIn("FAILED", r.stdout + r.stderr)
            self.assertNotIn("fuzz", r.stdout + r.stderr)


class TestSplitCli(ConfigCase):
    HARD = f"{SPLIT_A}, and {SPLIT_B}"

    def env(self, **extra):
        e = {"HOME": self.tmp, "PATH": "/usr/bin:/bin"}
        e.update(extra)
        return e

    def run_split(self, *args, cwd=None, **extra):
        return subprocess.run([sys.executable, "-I", SCRIPT, "split", *args], capture_output=True, text=True, env=self.env(**extra), cwd=cwd)

    def draft(self, text=None, name="draft.md"):
        return self.write(f"Fine one.\n\n{self.HARD}\n" if text is None else text, name)

    def test_it_prints_the_id_the_grades_and_the_two_sentences(self):
        path = self.draft()
        r = self.run_split(path)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.splitlines(), [f"{path}:3: S2: reading grade 15. As two sentences it would read at grade 9 and 5:", f"    {SPLIT_A}.", f"    And {SPLIT_B}"])
        self.assertEqual(r.stderr, "")

    def test_it_never_changes_the_file(self):
        path = self.draft()
        with open(path, "rb") as f:
            before = f.read()
        self.run_split(path)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(self.run_split(path, "--write").returncode, 2)

    def test_with_nothing_to_suggest_it_prints_nothing_and_exits_0(self):
        r = self.run_split(self.draft("A short clean note.\n"))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_the_repo_profile_gives_the_footer_and_the_template(self):
        tpl = self.write(self.HARD + "\n", "tpl.md")
        cfg = self.write(f'[repo."a/b"]\npr_template = {json.dumps(tpl)}\nfooter = {json.dumps(FOOTER)}\n', "cfg.toml")
        path = self.draft(f"{self.HARD}\n\n{SPLIT_A}; {SPLIT_B}\n\n-- Sent from the made-up example footer\n")
        self.assertEqual(len(self.run_split(path).stdout.splitlines()), 6)
        r = self.run_split(path, "--repo", "a/b", FURBISH_CONFIG=cfg)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(r.stdout.splitlines()), 3)
        self.assertIn(":3: S2:", r.stdout)

    def test_things_that_cannot_run_exit_2_with_a_plain_message(self):
        path = self.draft()
        for args in ((os.path.join(self.tmp, "missing.md"),), (path, "--repo", "x/y")):
            r = self.run_split(*args)
            self.assertEqual((r.returncode, r.stdout), (2, ""), args)
            self.assertTrue(r.stderr.startswith("furbish: "), r.stderr)
            self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(self.run_split().returncode, 2)

    def test_a_draft_that_is_not_utf8_is_still_read(self):
        path = self.draft("")
        with open(path, "wb") as f:
            f.write(b"Caf\xe9.\n\n" + self.HARD.encode() + b"\n")
        r = self.run_split(path)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(r.stdout.splitlines()), 3)

    def test_control_characters_are_not_printed(self):
        path = self.draft(f"{SPLIT_A} \x1b[31m\u202e; {SPLIT_B}\n", "d\x1b[31mx.md")
        r = self.run_split(path)
        self.assertEqual(r.returncode, 0)
        for bad in ("\x1b", "\u202e"):
            self.assertNotIn(bad, r.stdout)
        self.assertIn("?", r.stdout)

    def test_a_relative_path_is_found(self):
        self.draft()
        self.assertEqual(len(self.run_split("draft.md", cwd=self.tmp).stdout.splitlines()), 3)

    def test_help_lists_split_and_nothing_as_planned(self):
        r = subprocess.run([sys.executable, "-I", SCRIPT, "--help"], capture_output=True, text=True, env=self.env())
        self.assertIn("split", r.stdout)
        self.assertNotIn("planned", r.stdout)
        self.assertIn("never changes the draft", self.run_split("--help").stdout.replace("\n", " ").replace("  ", " "))

    def test_a_closed_pipe_makes_no_traceback(self):
        path = self.draft()
        cmd = f"set -o pipefail; {shlex.quote(sys.executable)} -I {shlex.quote(SCRIPT)} split {shlex.quote(path)} | head -c0; echo ${{PIPESTATUS[0]}}"
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env=self.env())
        self.assertEqual(r.stdout.strip(), "0")
        self.assertNotIn("Exception", r.stderr)

    def test_a_262_kb_draft_through_the_command_takes_under_two_seconds(self):
        with open(os.path.join(DRAFTS, "pr-body.md"), encoding="utf-8") as f:
            body = f.read()
        path = self.draft((body * (262000 // len(body) + 1))[:262000] + "\n\n" + self.HARD + "\n")
        t = time.perf_counter()
        r = self.run_split(path)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        self.assertLess(time.perf_counter() - t, 2.0)


class TestKindCli(ConfigCase):
    CFG = '[repo."a/b"]\ntldr = "required"\ntldr_words = 100\ntldr_max_sentences = 3\n[repo."a/b".kinds.release]\ntldr = "off"\ngrade_skip = ["configuration loader"]\n'

    def env(self, **extra):
        e = {"HOME": self.tmp, "PATH": "/usr/bin:/bin"}
        e.update(extra)
        return e

    def run_cli(self, *args, **extra):
        return subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True, text=True, env=self.env(**extra))

    def test_kind_on_check_switches_off_the_tldr_rule(self):
        cfg = self.write(self.CFG, "cfg.toml")
        path = self.write(words(120) + "\n", "draft.md")
        r = self.run_cli("check", "--repo", "a/b", path, FURBISH_CONFIG=cfg)
        self.assertEqual(r.returncode, 1)
        self.assertIn("TL;DR", r.stdout)
        r = self.run_cli("check", "--repo", "a/b", "--kind", "release", path, FURBISH_CONFIG=cfg)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_a_kinds_grade_skip_applies_to_check_and_split(self):
        cfg = self.write(self.CFG, "cfg.toml")
        path = self.write(f"{SPLIT_A}, and {SPLIT_B}\n", "draft.md")
        self.assertEqual(self.run_cli("check", "--post", "--repo", "a/b", path, FURBISH_CONFIG=cfg).returncode, 1)
        r = self.run_cli("check", "--post", "--repo", "a/b", "--kind", "release", path, FURBISH_CONFIG=cfg)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(len(self.run_cli("split", "--repo", "a/b", path, FURBISH_CONFIG=cfg).stdout.splitlines()), 3)
        r = self.run_cli("split", "--repo", "a/b", "--kind", "release", path, FURBISH_CONFIG=cfg)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_every_command_takes_kind_and_refuses_an_unknown_one(self):
        cfg = self.write(self.CFG, "cfg.toml")
        path = self.write("Body.\n", "draft.md")
        for cmd in (["check", path], ["fix", path], ["split", path], ["set", path, "S1", "New words here."]):
            r = self.run_cli(cmd[0], "--repo", "a/b", "--kind", "nope", *cmd[1:], FURBISH_CONFIG=cfg)
            self.assertEqual((r.returncode, r.stdout), (2, ""), cmd)
            self.assertIn("has no kind nope", r.stderr, cmd)
            self.assertNotIn("Traceback", r.stderr, cmd)

    def test_a_kind_with_no_repo_or_no_config_says_so(self):
        path = self.write("Body.\n", "draft.md")
        r = self.run_cli("check", "--kind", "release", path)
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn("no config file was found, so there is no kind release", r.stderr)
        cfg = self.write('[repo."a/b".kinds.release]\ntldr = "off"\n', "cfg.toml")
        r = self.run_cli("check", "--kind", "release", path, FURBISH_CONFIG=cfg)
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn("a kind needs a repo profile: pass --repo or set default_repo", r.stderr)

    def test_help_explains_kind_on_each_command(self):
        for cmd in ("check", "set", "fix", "split"):
            r = self.run_cli(cmd, "--help")
            self.assertEqual(r.returncode, 0, cmd)
            self.assertIn("--kind", r.stdout, cmd)
            self.assertIn("a kind inside the repo profile, such as tracker; it overrides only the keys it names", " ".join(r.stdout.split()), cmd)


if __name__ == "__main__":
    unittest.main()
