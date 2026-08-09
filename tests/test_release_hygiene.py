from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from survey_insight.api import app


ROOT = Path(__file__).resolve().parents[1]


class ReleaseHygieneTests(unittest.TestCase):
    def test_readme_commands_and_health_entrypoints_work(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for command in [
            "python -m pip install -e .",
            "python -m unittest discover -s tests -v",
            "python -m compileall survey_insight tests",
            "python -m survey_insight.cli demo --out .\\out --seed 42",
            "python -m uvicorn survey_insight.api:app --host 127.0.0.1 --port 8001",
        ]:
            with self.subTest(command=command):
                self.assertIn(command, readme)

        result = subprocess.run(
            [sys.executable, "-m", "survey_insight.cli", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("demo", result.stdout)
        self.assertEqual(TestClient(app).get("/health").json(), {"status": "ok"})

    def test_generated_data_and_databases_are_not_git_tracked(self) -> None:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        tracked = [Path(line) for line in result.stdout.splitlines() if line.strip()]
        forbidden = [
            path
            for path in tracked
            if any(part.startswith("out") for part in path.parts)
            or path.suffix.casefold() in {".db", ".sqlite", ".sqlite3"}
        ]
        self.assertEqual(forbidden, [])

    def test_sample_data_has_no_obvious_contact_or_employee_id_patterns(self) -> None:
        sample_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "sample_data").glob("*")
            if path.suffix.casefold() in {".csv", ".txt", ".json"}
        )
        patterns = [
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            r"\b(?:010|011|016|017|018|019)[-. ]?\d{3,4}[-. ]?\d{4}\b",
            r"\b(?:사번|직번|employee\s*id)[:\s-]*[A-Za-z0-9-]{4,}\b",
        ]
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, sample_text, re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
