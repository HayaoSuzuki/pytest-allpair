"""Check plugin discovery and n-way coverage from an installed distribution."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
from venv import EnvBuilder

_SMOKE = """
from itertools import combinations, product

import pytest

cases = []


@pytest.fixture(scope="session", autouse=True)
def check_coverage():
    yield
    allowed = set(product((0, 1), repeat=3))
    assert 0 < len(cases) < len(allowed)
    assert set(cases) <= allowed
    for left, right in combinations(range(3), 2):
        assert {(row[left], row[right]) for row in cases} == set(product((0, 1), repeat=2))


@pytest.mark.pairwise_parametrize("a", [0, 1])
@pytest.mark.pairwise_parametrize("b", [0, 1])
@pytest.mark.pairwise_parametrize("c", [0, 1])
def test_installed_plugin(a, b, c):
    cases.append((a, b, c))
"""


def main(distribution: Path) -> None:
    """Install the distribution in a fresh environment and run the smoke test."""
    distribution = distribution.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="pytest-allpair-wheel-") as directory:
        project = Path(directory)
        environment = project / "venv"
        EnvBuilder(with_pip=True, symlinks=os.name != "nt").create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        # Install the supplied artifact with pip from the isolated environment.
        subprocess.run(  # noqa: S603
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "--disable-pip-version-check",
                "install",
                str(distribution),
            ],
            cwd=project,
            check=True,
        )
        (project / "test_wheel.py").write_text(dedent(_SMOKE), encoding="utf-8")
        env = os.environ.copy()
        env.pop("PYTEST_ADDOPTS", None)
        env.pop("PYTEST_PLUGINS", None)
        subprocess.run(  # noqa: S603
            [str(python), "-I", "-m", "pytest", "--strict-markers", "-q", "test_wheel.py"],
            cwd=project,
            env=env,
            check=True,
        )


if __name__ == "__main__":
    match sys.argv:
        case [_, distribution_path]:
            main(Path(distribution_path))
        case _:
            message = "usage: python tools/wheel_smoke.py DISTRIBUTION_PATH"
            raise SystemExit(message)
