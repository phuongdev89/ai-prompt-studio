"""Catch JavaScript parse errors that prevent the UI from loading SQLite data."""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendSyntaxTests(unittest.TestCase):
    def test_javascript_assets_parse(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required to validate JavaScript syntax")
        scripts = sorted((ROOT / "app" / "static" / "js").rglob("*.js"))
        self.assertTrue(scripts, "No JavaScript assets found")
        for script in scripts:
            with self.subTest(script=script.name):
                result = subprocess.run(
                    [node, "--check", str(script)],
                    capture_output=True, text=True, encoding="utf-8",
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
