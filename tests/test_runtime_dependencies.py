import tomllib
from pathlib import Path


def test_runtime_dependencies_include_tzdata_for_zoneinfo_on_windows() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert any(dependency.lower().startswith("tzdata") for dependency in dependencies)
