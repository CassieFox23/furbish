import importlib.util, os, subprocess, sys, tempfile, time, unittest

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
        self.assertAlmostEqual(s[0].grade, furbish.ari("Run before you push."), places=6)
        self.assertAlmostEqual(s[1].grade, furbish.ari("The option is new."), places=6)

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
        self.assertAlmostEqual(s[0].grade, furbish.ari("See the guide for details."), places=6)
        self.assertAlmostEqual(s[1].grade, furbish.ari("Visit now."), places=6)

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
        self.assertAlmostEqual(s[0].grade, -7.42125, places=4)
        self.assertAlmostEqual(s[1].grade, furbish.ari("A bold move."), places=6)

    def test_crlf_line_endings(self):
        s = furbish.read_prose("Main one.\r\n\r\nNext one.\r\n\r\n-- Sent from the made-up example footer\r\n", FOOTER)
        self.assertEqual([(x.text, x.line) for x in s], [("Main one.", 1), ("Next one.", 3)])

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
        self.assertAlmostEqual(p.grade, furbish.ari("Please review the variable usage in the test scripts before deploying."), places=6)

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
            "pr_template": None, "issue_template": None, "first_line_prefix": None, "footer": None,
            "tldr": "off", "tldr_words": None, "tldr_max_sentences": None,
            "banned": [], "private": [], "keep_negation": [],
            "code_names": {"quoted_tests": False, "checks": [], "states": []},
            "external": [],
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
        self.bad("a = " + "[" * 5000 + "]" * 5000 + "\n")

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


if __name__ == "__main__":
    unittest.main()
