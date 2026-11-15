import py_compile
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_PATTERNS = [
    re.compile(r"C:\\Users\\[A-Za-z0-9_]+", re.IGNORECASE),
    re.compile(r"C:/Users/[A-Za-z0-9_]+", re.IGNORECASE),
    re.compile(r"/home/[a-z0-9_-]+", re.IGNORECASE),
    re.compile(r"\b192\.168\.\d+\.\d+\b"),
    re.compile(r"\b100\.64\.\d+\.\d+\b"),
    re.compile(r"BEGIN OPENSSH PRIVATE KEY"),
]


class TestRepoHygieneAndCLI(unittest.TestCase):
    def test_no_personal_identifiers_or_hardcoded_user_paths(self):
        """Guarantees no file in the repository contains hardcoded personal paths or LAN IPs."""
        violations = []
        for path in REPO_ROOT.rglob("*"):
            if ".git" in path.parts or "__pycache__" in path.parts or path.is_dir():
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue

            for pat in FORBIDDEN_PATTERNS:
                match = pat.search(text)
                if match:
                    rel = path.relative_to(REPO_ROOT)
                    violations.append(f"{rel}: matched '{match.group(0)}'")

        self.assertEqual(violations, [], f"Found hardcoded personal/path identifiers: {violations}")

    def test_all_python_scripts_compile_and_support_help_flag(self):
        """Verifies every Python script compiles cleanly and responds to `--help` with exit code 0."""
        py_files = (
            list((REPO_ROOT / "recording").glob("*.py"))
            + list((REPO_ROOT / "post-processing").glob("*.py"))
            + list((REPO_ROOT / "youtube-gitops").glob("*.py"))
        )
        self.assertGreaterEqual(len(py_files), 8)

        for py_file in py_files:
            py_compile.compile(str(py_file), doraise=True)
            res = subprocess.run(
                [sys.executable, str(py_file), "--help"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(
                res.returncode,
                0,
                f"{py_file.name} --help failed with code {res.returncode}: {res.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
