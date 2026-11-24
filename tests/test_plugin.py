from __future__ import annotations

import json
from typing import Literal

import pytest

pytest_plugins = ("pytester",)


@pytest.mark.parametrize("order", [None, 1, 3, "max"])
def test_generated_cases_match_every_feasible_interaction(
    pytester: pytest.Pytester, order: Literal["max"] | int | None
) -> None:
    options: dict[str, object] = {"exclude": [{"a": 0, "b": 0}]}
    if order is not None:
        options["order"] = order
    strength = 2 if order is None else (4 if order == "max" else order)
    pytester.makepyfile(
        f"""
        from itertools import combinations, product
        import pytest

        cases = []

        @pytest.fixture(scope="session", autouse=True)
        def verify_coverage():
            yield
            allowed = [row for row in product(range(2), repeat=4) if row[:2] != (0, 0)]
            indices = list(combinations(range(4), {strength}))

            def interactions(rows):
                return {{(axes, tuple(row[i] for i in axes)) for axes in indices for row in rows}}

            assert len(cases) == len(set(cases))
            assert set(cases) <= set(allowed)
            assert interactions(cases) == interactions(allowed)

        @pytest.mark.pairwise(**{options!r})
        @pytest.mark.pairwise_parametrize("a", [0, 1])
        @pytest.mark.pairwise_parametrize("b", [0, 1])
        @pytest.mark.pairwise_parametrize("c", [0, 1])
        @pytest.mark.pairwise_parametrize("d", [0, 1])
        def test_matrix(a, b, c, d):
            cases.append((a, b, c, d))
        """
    )
    result = pytester.runpytest_subprocess("-q")
    assert result.ret == pytest.ExitCode.OK
    assert result.parseoutcomes()["passed"] > 0


def test_grouped_values_and_ids(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.pairwise_parametrize(
            "name", ["default", "other"], ids=[pytest.HIDDEN_PARAM, "label"]
        )
        @pytest.mark.pairwise_parametrize("value, expected", [
            (1, 2),
            pytest.param(2, 9, id="known", marks=pytest.mark.xfail(strict=True)),
        ], ids=lambda value: f"v{value}")
        def test_matrix(name, value, expected):
            assert value * 2 == expected
        """
    )
    collected = pytester.runpytest_subprocess("--collect-only", "-q")
    assert collected.ret == pytest.ExitCode.OK
    ids = [
        line.split("::test_matrix", 1)[1]
        for line in collected.stdout.lines
        if "::test_matrix" in line
    ]
    assert set(ids) == {"[v1-v2]", "[v1-v2-label]", "[known]", "[known-label]"}
    pytester.runpytest_subprocess("-q").assert_outcomes(passed=2, xfailed=2)


def test_joined_ids_are_unique(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.pairwise_parametrize("right", [0, 1], ids=["c", "b-c"])
        @pytest.mark.pairwise_parametrize("left", [0, 1], ids=["a-b", "a"])
        def test_matrix(left, right):
            assert left in (0, 1) and right in (0, 1)
        """
    )
    result = pytester.runpytest_subprocess("--collect-only", "-q")
    assert result.ret == pytest.ExitCode.OK
    names = [line for line in result.stdout.lines if "::test_matrix" in line]
    assert len(names) == len(set(names)) == 4


def test_exclusions_match_every_equal_level(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        options = {"data": [[1], [1], [2]], "ids": ["first", "second", "third"]}

        @pytest.mark.pairwise_parametrize("data", options["data"], ids=options["ids"])
        def test_unfiltered(data):
            assert data

        @pytest.mark.pairwise(exclude=[{"data": [1]}])
        @pytest.mark.pairwise_parametrize("data", options["data"], ids=options["ids"])
        def test_filtered(data):
            assert data == [2]
        """
    )
    result = pytester.runpytest_subprocess("--collect-only", "-q")
    assert result.ret == pytest.ExitCode.OK
    names = {line.partition("::")[2] for line in result.stdout.lines if "::" in line}
    assert names == {
        "test_unfiltered[first]",
        "test_unfiltered[second]",
        "test_unfiltered[third]",
        "test_filtered[third]",
    }
    pytester.runpytest_subprocess("-q").assert_outcomes(passed=4)


@pytest.mark.parametrize("setting", ["skip", "fail_at_collect"])
def test_empty_factor_follows_pytest_ini(
    pytester: pytest.Pytester, setting: Literal["skip", "fail_at_collect"]
) -> None:
    pytester.makeini(f"[pytest]\nempty_parameter_set_mark = {setting}\n")
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.pairwise_parametrize("a", [])
        @pytest.mark.pairwise_parametrize("b", [1, 2])
        def test_matrix(a, b):
            pytest.fail("the empty model must not execute")
        """
    )
    result = pytester.runpytest_subprocess("-q")
    if setting == "skip":
        result.assert_outcomes(skipped=1)
    else:
        result.assert_outcomes(errors=1)
        assert "empty parameter set" in result.stdout.str().lower()


@pytest.mark.parametrize("indirect", [True, ["db"]])
def test_fixtures_and_standard_parametrize(
    pytester: pytest.Pytester, *, indirect: bool | list[str]
) -> None:
    pytester.makepyfile(
        f"""
        import pytest

        @pytest.fixture(params=["plain", "tls"])
        def transport(request):
            return request.param

        @pytest.fixture
        def db(request):
            return "db-" + request.param

        @pytest.mark.parametrize("user", ["admin", "staff"])
        @pytest.mark.pairwise_parametrize("db", ["pg", "sqlite"], indirect={indirect!r})
        @pytest.mark.pairwise_parametrize("cache", [True, False])
        def test_matrix(transport, user, db, cache):
            assert db in ("db-pg", "db-sqlite")
        """
    )
    pytester.runpytest_subprocess("-q").assert_outcomes(passed=16)


def test_duplicate_indirect_fixture_parameter(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture(params=["pg"])
        def db(request):
            return request.param

        @pytest.mark.pairwise_parametrize("db", ["sqlite"], indirect=True)
        def test_matrix(db):
            pass
        """
    )
    result = pytester.runpytest_subprocess("-q")
    result.assert_outcomes(errors=1)
    assert "duplicate" in result.stdout.str().lower()


def test_class_and_module_factors(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        pytestmark = pytest.mark.pairwise_parametrize("operating_system", ["linux", "macos"])

        @pytest.mark.pairwise_parametrize("layout", [0, 1])
        class TestMatrix:
            @pytest.mark.pairwise(order="max", exclude=[{"operating_system": "macos", "layout": 0}])
            @pytest.mark.pairwise_parametrize("driver", ["a", "b"])
            def test_matrix(self, operating_system, layout, driver):
                assert (operating_system, layout) != ("macos", 0)
        """
    )
    pytester.runpytest_subprocess("-q").assert_outcomes(passed=6)


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        ("@pytest.mark.pairwise(order=0)", "order must"),
        ("@pytest.mark.pairwise(order=True)", "order must"),
        ("@pytest.mark.pairwise(order=3)", "order must"),
        ("@pytest.mark.pairwise()\n@pytest.mark.pairwise()", "one pairwise"),
        ('@pytest.mark.pairwise(exclude=[{"z": 0}])', "unknown parameter"),
        ('@pytest.mark.pairwise(exclude=[{"a": 9}])', "matches no candidate"),
        ('@pytest.mark.pairwise(exclude=[{"a": Bad()}])', "equality"),
        ("@pytest.mark.pairwise(exclude=[{}])", "nonempty"),
        ('@pytest.mark.pairwise_parametrize("a", [0], scope="module")', "scope must"),
        ('@pytest.mark.pairwise_parametrize("a", [0], scope="session")', "scope must"),
        ('@pytest.mark.pairwise(exclude=[{"a": 0}, {"a": 1}])', "no valid cases"),
    ],
)
def test_invalid_declarations(pytester: pytest.Pytester, declaration: str, message: str) -> None:
    axis = "" if "scope=" in declaration else '@pytest.mark.pairwise_parametrize("a", [0, 1])'
    scope = ', scope="module"' if 'scope="session"' in declaration else ""
    pytester.makepyfile(
        f"""
        import pytest

        class Bad:
            def __eq__(self, other):
                raise ValueError("no truth value")

        {declaration.replace(chr(10), chr(10) + "        ")}
        {axis}
        @pytest.mark.pairwise_parametrize("b", [0, 1]{scope})
        def test_matrix(a, b):
            pass
        """
    )
    result = pytester.runpytest_subprocess("-q")
    result.assert_outcomes(errors=1)
    assert "test_matrix" in result.stdout.str()
    assert message in result.stdout.str().lower()


def test_configuration_only_allowed_on_function(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        pytestmark = pytest.mark.pairwise()
        @pytest.mark.pairwise_parametrize("a", [0])
        def test_matrix(a):
            pass
        """
    )
    result = pytester.runpytest_subprocess("-q")
    result.assert_outcomes(errors=1)
    assert "test function" in result.stdout.str().lower()


@pytest.mark.parametrize("escaping_disabled", [False, True])
def test_node_ids_use_pytest_escaping_once(
    pytester: pytest.Pytester, *, escaping_disabled: bool
) -> None:
    pytester.makeini(
        f"[pytest]\ndisable_test_id_escaping_and_forfeit_all_rights_to_community_support = "
        f"{escaping_disabled}\n"
    )
    pytester.makeconftest(
        """
        import json
        from pathlib import Path

        def pytest_collection_finish(session):
            nodeids = [item.nodeid.split("::", 1)[1] for item in session.items]
            Path("nodeids.json").write_text(json.dumps(nodeids), encoding="utf-8")
        """
    )
    pytester.makepyfile(
        r"""
        import pytest

        values = [
            pytest.param("explicit", id="日本\\path"),
            "literal\\u65e5",
            "line\nbreak",
        ]

        @pytest.mark.parametrize("value", values)
        def test_native(value):
            pass

        @pytest.mark.pairwise_parametrize("value", values)
        def test_pairwise(value):
            pass
        """
    )
    result = pytester.runpytest_subprocess("--collect-only", "-q")
    assert result.ret == pytest.ExitCode.OK
    nodeids: object = json.loads((pytester.path / "nodeids.json").read_text(encoding="utf-8"))
    assert isinstance(nodeids, list)
    ids = [nodeid for nodeid in nodeids if isinstance(nodeid, str)]
    assert len(ids) == len(nodeids) == 6

    def parameter_ids(test_name: str) -> list[str]:
        return sorted(
            nodeid.removeprefix(test_name) for nodeid in ids if nodeid.startswith(test_name)
        )

    assert parameter_ids("test_native[") == parameter_ids("test_pairwise[")


@pytest.mark.parametrize("dependency_values", [[10, 20], []])
def test_direct_values_prune_only_unused_fixture_dependencies(
    pytester: pytest.Pytester, dependency_values: list[int]
) -> None:
    pytester.makepyfile(
        f"""
        import pytest

        @pytest.fixture(params={dependency_values!r})
        def dependency(request):
            return request.param

        @pytest.fixture
        def shadow(dependency):
            raise AssertionError("the direct value replaces this fixture")

        @pytest.mark.pairwise_parametrize("shadow", ["direct"])
        def test_direct(shadow):
            assert shadow == "direct"

        @pytest.mark.pairwise_parametrize("shadow", ["direct"])
        def test_still_requested(shadow, dependency):
            assert shadow == "direct"
            assert dependency in (10, 20)
        """
    )
    result = pytester.runpytest_subprocess("-q")
    result.assert_outcomes(
        passed=3 if dependency_values else 1, skipped=0 if dependency_values else 1
    )


def test_direct_values_reject_a_parametrized_fixture_with_the_same_name(
    pytester: pytest.Pytester,
) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture(params=["fixture"])
        def value(request):
            return request.param

        @pytest.mark.pairwise_parametrize("value", ["direct"])
        def test_matrix(value):
            pass
        """
    )
    result = pytester.runpytest_subprocess("-q")
    result.assert_outcomes(errors=1)
    assert "duplicate" in result.stdout.str().lower()
