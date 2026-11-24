import pytest
from pytest_allpair import _native


def test_native_solves_two_by_two():
    assert {tuple(row) for row in _native.generate([2, 2], 2, [])} == {
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
    }


def test_native_reports_unsatisfiable_model():
    with pytest.raises(ValueError, match="no valid cases"):
        _native.generate([2], 1, [[(0, [0, 1])]])
