"""Collect declared factors and publish the generated cases through pytest."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeGuard

import pytest

from . import _native
from ._pytest_compat import (
    FixtureScope,
    Level,
    ParameterIds,
    fail_collection,
    parameter_rows,
    register_rows,
)

if TYPE_CHECKING:
    from ._native import ForbiddenRule

_DEFAULT_ORDER = object()


@dataclass(frozen=True, slots=True)
class Factor:
    """Keep a factor's pytest arguments, candidate levels, and fixture settings."""

    names: tuple[str, ...]
    levels: tuple[Level, ...]
    indirect: tuple[str, ...]
    scope: FixtureScope | None


def _is_indirect_names(value: object, names: tuple[str, ...]) -> TypeGuard[Sequence[str]]:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and all(isinstance(name, str) and name in names for name in value)
    )


def _is_fixture_scope(value: object) -> TypeGuard[FixtureScope]:
    return isinstance(value, str) and value in ("function", "class", "module", "package", "session")


# The signature follows the marker and takes the current pytest collection context.
def _factor(  # noqa: PLR0913
    argnames: str | Sequence[str],
    argvalues: Iterable[object],
    *,
    ids: ParameterIds = None,
    indirect: object = False,
    scope: object = None,
    metafunc: pytest.Metafunc,
) -> Factor:
    names, levels = parameter_rows(argnames, argvalues, ids, metafunc=metafunc)
    if isinstance(indirect, bool):
        indirect_names = names if indirect else ()
    elif _is_indirect_names(indirect, names):
        indirect_names = tuple(indirect)
    else:
        message = "indirect must be a boolean or a sequence of parameter names from the factor"
        raise ValueError(message)
    if scope is None or _is_fixture_scope(scope):
        return Factor(names, levels, indirect_names, scope)
    message = "scope must be a pytest fixture scope"
    raise ValueError(message)


def _options(*, order: object = _DEFAULT_ORDER, exclude: object = ()) -> tuple[object, object]:
    return order, exclude


def _order(order: object, count: int) -> int:
    if order is _DEFAULT_ORDER:
        return min(2, count)
    if isinstance(order, str) and order == "max":
        return count
    if isinstance(order, int) and not isinstance(order, bool) and 1 <= order <= count:
        return order
    message = f"order must be an integer between 1 and {count}, or 'max'"
    raise ValueError(message)


def _matching_levels(factor: Factor, column: int, name: object, wanted: object) -> set[int]:
    try:
        matching = {
            index for index, level in enumerate(factor.levels) if level.values[column] == wanted
        }
    except Exception as error:
        # Python values are opaque to Rust. Equality may raise or have no scalar truth value.
        message = f"cannot evaluate equality for excluded parameter {name!r}: {error}"
        raise ValueError(message) from error
    if not matching and factor.levels:
        message = f"excluded value for parameter {name!r} matches no candidate"
        raise ValueError(message)
    return matching


def _exclusions(factors: Sequence[Factor], exclude: object) -> list[ForbiddenRule]:
    """Compile conjunctions into level sets, intersecting columns of the same factor."""
    if not isinstance(exclude, Sequence) or isinstance(exclude, (str, bytes)):
        message = "exclude must be a sequence of nonempty mappings"
        raise TypeError(message)
    positions: dict[object, tuple[int, int]] = {
        name: (axis, column)
        for axis, factor in enumerate(factors)
        for column, name in enumerate(factor.names)
    }
    rules = []
    for entry in exclude:
        if not isinstance(entry, Mapping) or not entry:
            message = "each exclusion must be a nonempty mapping"
            raise ValueError(message)
        by_factor: dict[int, set[int]] = {}
        for name, wanted in entry.items():
            if name not in positions:
                message = f"exclusion refers to unknown parameter {name!r}"
                raise ValueError(message)
            axis, column = positions[name]
            matching = _matching_levels(factors[axis], column, name, wanted)
            if axis in by_factor:
                by_factor[axis].intersection_update(matching)
            else:
                by_factor[axis] = matching
        # A conjunction that cannot match any level of one factor forbids no rows.
        if all(by_factor.values()):
            rules.append([(axis, sorted(levels)) for axis, levels in sorted(by_factor.items())])
    return rules


def pytest_configure(config: pytest.Config) -> None:
    """Register the covering-array markers with pytest."""
    config.addinivalue_line(
        "markers",
        "pairwise_parametrize(argnames, argvalues, *, ids=None, indirect=False, scope=None): "
        "declare a factor in an n-way covering array",
    )
    config.addinivalue_line(
        "markers",
        "pairwise(*, order, exclude): configure generation for a single test function",
    )


def _collect_cases(
    metafunc: pytest.Metafunc,
) -> tuple[list[Factor], list[str], list[list[int]]] | None:
    """Validate the test's declarations and return its factors and selected rows."""
    definition = metafunc.definition
    marks = list(definition.iter_markers("pairwise_parametrize"))
    options = list(definition.iter_markers_with_node("pairwise"))
    if not marks and not options:
        return None
    if any(node is not definition for node, _ in options):
        message = "pairwise may only be applied to a test function"
        raise ValueError(message)
    if len(options) > 1:
        message = "only one pairwise configuration is allowed per test function"
        raise ValueError(message)
    if not marks:
        message = "pairwise configuration requires at least one pairwise_parametrize factor"
        raise ValueError(message)

    factors = [_factor(*mark.args, **mark.kwargs, metafunc=metafunc) for mark in marks]
    names = [name for factor in factors for name in factor.names]
    if len(names) != len(set(names)):
        message = "duplicate parameter name in pairwise factors"
        raise ValueError(message)
    scope = factors[0].scope
    if any(factor.scope != scope for factor in factors):
        message = "scope must be the same for every pairwise factor"
        raise ValueError(message)

    if options:
        config = options[0][1]
        requested_order, exclude = _options(*config.args, **config.kwargs)
    else:
        requested_order, exclude = _options()
    order = _order(requested_order, len(factors))
    forbidden = _exclusions(factors, exclude)
    counts = [len(factor.levels) for factor in factors]
    rows = [] if 0 in counts else _native.generate(counts, order, forbidden)
    return factors, names, rows


@pytest.hookimpl(tryfirst=True)
def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Register the legal covering cases for this test function."""
    try:
        cases = _collect_cases(metafunc)
    except (TypeError, ValueError) as error:
        fail_collection(f"{metafunc.definition.nodeid}: {error}")

    if cases is None:
        return
    factors, names, rows = cases
    selected = (
        [factor.levels[index] for factor, index in zip(factors, row, strict=True)] for row in rows
    )
    register_rows(
        metafunc,
        names,
        selected,
        indirect=[name for factor in factors for name in factor.indirect],
        scope=factors[0].scope,
    )
