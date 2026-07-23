from __future__ import annotations

import tomllib
from pathlib import Path

import secop_intelligence


def test_package_version_matches_project_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert secop_intelligence.__version__ == project["project"]["version"]
    assert secop_intelligence.__version__ == "0.1.0"
