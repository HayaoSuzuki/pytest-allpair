import re
import subprocess
import sys

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

_GroupedRow = tuple[list[int], int]
_Exclusion = tuple[list[int], int, int]
_Model = tuple[list[_GroupedRow], list[_Exclusion]]


@st.composite
def _grouped_factors(draw: st.DrawFn) -> _Model:
    rows = draw(
        st.lists(
            st.tuples(st.lists(st.integers(0, 1), max_size=2), st.integers(0, 2)),
            min_size=1,
            max_size=5,
        )
    )
    values = [value for value, _ in rows]
    expected = [number for _, number in rows]
    exclusions = draw(
        st.lists(
            st.tuples(st.sampled_from(values), st.sampled_from(expected), st.integers(0, 1)),
            max_size=4,
        )
    )
    return rows, exclusions


@given(model=_grouped_factors())
@settings(max_examples=24, deadline=None)
def test_grouped_exclusion_matches_explicit_pytest_cases(
    tmp_path_factory: pytest.TempPathFactory, model: _Model
) -> None:
    rows, exclusions = model
    restrictions = [
        {"value": value, "expected": expected, "backend": backend}
        for value, expected, backend in exclusions
    ]
    case = tmp_path_factory.mktemp("grouped_factors")
    (case / "test_model.py").write_text(
        f"""
import pytest

rows = {rows!r}

@pytest.mark.pairwise(exclude={restrictions!r})
@pytest.mark.pairwise_parametrize("backend", [0, 1], ids=["db0", "db1"])
@pytest.mark.pairwise_parametrize(
    "value, expected",
    [pytest.param(*row, id=f"row{{index}}") for index, row in enumerate(rows)],
)
def test_case(value, expected, backend):
    pass
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--strict-markers", "--collect-only", "-q"],
        cwd=case,
        capture_output=True,
        text=True,
        check=False,
    )

    # Two factors at the default order must produce exactly the legal rows,
    # including distinct candidate rows that contain equal Python values.
    expected = [
        f"row{index}-db{backend}"
        for index, (value, number) in enumerate(rows)
        for backend in (0, 1)
        if (value, number, backend) not in exclusions
    ]
    if not expected:
        assert result.returncode == pytest.ExitCode.INTERRUPTED, result.stdout + result.stderr
        assert "no valid cases" in result.stdout
    else:
        assert result.returncode == pytest.ExitCode.OK, result.stdout + result.stderr
        collected = re.findall(r"(?m)^test_model\.py::test_case\[(.*?)\]$", result.stdout)
        assert sorted(collected) == sorted(expected)
