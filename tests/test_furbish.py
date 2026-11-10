import importlib.util, json, os, re, subprocess, sys, tempfile, time, unittest

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


HARD = "Unquestionably, the implementation's architectural characteristics necessitate comprehensive reconsideration."
EASY = "Run the tests before you push."


def prof(**kw):
    p = {
        "pr_template": None, "issue_template": None, "first_line_prefix": None, "footer": None,
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
        self.assertIn("planned: replace one sentence", r.stdout)


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


if __name__ == "__main__":
    unittest.main()
