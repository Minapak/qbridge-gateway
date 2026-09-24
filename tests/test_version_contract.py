"""v1.6.3 — version contract + claim registry guards.

- gateway_agent.__version__ == pyproject.toml [project].version == CHANGELOG head
  (the /health assert lives in tests/test_server.py::test_health_check_fields).
- _marketing/claims.yaml passes scripts/claims-check and every test it cites exists.
"""

import re
import subprocess
import sys
from pathlib import Path

import gateway_agent

ROOT = Path(__file__).resolve().parent.parent


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"', text, re.M)
    assert m, "pyproject.toml has no [project] version"
    return m.group(1)


def _changelog_head_version() -> str:
    head = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")[:400]
    m = re.search(r"v(\d+\.\d+\.\d+)", head)
    assert m, "CHANGELOG.md head must name a version"
    return m.group(1)


def test_version_single_source():
    assert (
        gateway_agent.__version__ == _pyproject_version() == _changelog_head_version()
    )


def test_claims_registry_passes_check():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "claims-check"), str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK" in proc.stdout


def test_claims_cite_existing_tests():
    yaml_text = (ROOT / "_marketing" / "claims.yaml").read_text(encoding="utf-8")
    refs = re.findall(r'kind:\s*test,\s*ref:\s*"([^"]+)"', yaml_text)
    assert len(refs) >= 8
    for ref in refs:
        path, _, symbol = ref.partition("::")
        assert (ROOT / path).exists(), path
        if symbol:
            name = symbol.split("::")[-1]
            assert name in (ROOT / path).read_text(
                encoding="utf-8"
            ), f"{name} not in {path}"
