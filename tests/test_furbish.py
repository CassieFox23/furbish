import importlib.util, os, subprocess, sys, time, unittest

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


if __name__ == "__main__":
    unittest.main()
