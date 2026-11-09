import os, subprocess, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "furbish.py")


def run(*args):
    return subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True, text=True)


class TestCli(unittest.TestCase):
    def test_version(self):
        r = run("--version")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "furbish 0.1.0.dev0")

    def test_no_args_exits_2(self):
        r = run()
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage: furbish", r.stderr)


if __name__ == "__main__":
    unittest.main()
