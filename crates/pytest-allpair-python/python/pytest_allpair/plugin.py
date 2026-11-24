"""Collect declared factors and publish the generated cases through pytest."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pytest

from . import _native
from ._pytest_compat import Level, parameter_rows

_DEFAULT_ORDER = object()


@dataclass(frozen=True, slots=True)
class Factor:
    names: tuple[str, ...]
    levels: tuple[Level, ...]
    indirect: tuple[str, ...]
    scope: str | None


def _factor(argnames, argvalues, *, ids=None, indirect=False, scope=None, metafunc) -> Factor:
    names, levels = parameter_rows(argnames, argvalues, ids, metafunc=metafunc)
    if isinstance(indirect, bool):
        indirect_names = names if indirect else ()
    elif (
        isinstance(indirect, Sequence)
        and not isinstance(indirect, (str, bytes))
        and all(name in names for name in indirect)
    ):
        indirect_names = tuple(indirect)
    else:
        raise ValueError("indirect must be a boolean or a sequence of parameter names from the factor")
    if scope is not None and scope not in ("function", "class", "module", "package", "session"):
        raise ValueError("scope must be a pytest fixture scope")
    return Factor(names, levels, indirect_names, scope)


def _options(*, order=_DEFAULT_ORDER, exclude=()) -> tuple[object, object]:
    return order, exclude


def _order(order: object, count: int) -> int:
    if order is _DEFAULT_ORDER:
        return min(2, count)
    if isinstance(order, str) and order == "max":
        return count
    if isinstance(order, int) and not isinstance(order, bool) and 1 <= order <= count:
        return order
    raise ValueError(f"order must be an integer between 1 and {count}, or 'max'")


def _matching_levels(factor: Factor, column: int, name: str, wanted: object) -> set[int]:
    try:
        matching = {
            index
            for index, level in enumerate(factor.levels)
            if level.values[column] == wanted
        }
    except Exception as error:
        # Python values are opaque to Rust. Equality may raise or have no scalar truth value.
        raise ValueError(f"cannot evaluate equality for excluded parameter {name!r}: {error}") from error
    if not matching and factor.levels:
        raise ValueError(f"excluded value for parameter {name!r} matches no candidate")
    return matching


def _exclusions(factors: Sequence[Factor], exclude: object) -> list[list[tuple[int, list[int]]]]:
    """Compile conjunctions into level sets, intersecting columns of the same factor."""
    if not isinstance(exclude, Sequence) or isinstance(exclude, (str, bytes)):
        raise ValueError("exclude must be a sequence of nonempty mappings")
    positions = {
        name: (axis, column)
        for axis, factor in enumerate(factors)
        for column, name in enumerate(factor.names)
    }
    rules = []
    for entry in exclude:
        if not isinstance(entry, Mapping) or not entry:
            raise ValueError("each exclusion must be a nonempty mapping")
        by_factor: dict[int, set[int]] = {}
        for name, wanted in entry.items():
            if name not in positions:
                raise ValueError(f"exclusion refers to unknown parameter {name!r}")
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


def _parameter_set(factors: Sequence[Factor], row: Sequence[int]):
    levels = [factor.levels[index] for factor, index in zip(factors, row, strict=True)]
    visible_ids = [level.id for level in levels if level.id is not None]
    return pytest.param(
        *(value for level in levels for value in level.values),
        marks=tuple(mark for level in levels for mark in level.marks),
        id="-".join(visible_ids) if visible_ids else pytest.HIDDEN_PARAM,
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "pairwise_parametrize(argnames, argvalues, *, ids=None, indirect=False, scope=None): "
        "declare a factor in an n-way covering array",
    )
    config.addinivalue_line(
        "markers",
        "pairwise(*, order, exclude): configure generation for a single test function",
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    definition = metafunc.definition
    marks = list(definition.iter_markers("pairwise_parametrize"))
    options = list(definition.iter_markers_with_node("pairwise"))
    if not marks and not options:
        return

    try:
        if any(node is not definition for node, _ in options):
            raise ValueError("pairwise may only be applied to a test function")
        if len(options) > 1:
            raise ValueError("only one pairwise configuration is allowed per test function")
        if not marks:
            raise ValueError("pairwise configuration requires at least one pairwise_parametrize factor")

        factors = [_factor(*mark.args, **mark.kwargs, metafunc=metafunc) for mark in marks]
        names = [name for factor in factors for name in factor.names]
        if len(names) != len(set(names)):
            raise ValueError("duplicate parameter name in pairwise factors")
        scope = factors[0].scope
        if any(factor.scope != scope for factor in factors):
            raise ValueError("scope must be the same for every pairwise factor")

        if options:
            config = options[0][1]
            requested_order, exclude = _options(*config.args, **config.kwargs)
        else:
            requested_order, exclude = _options()
        order = _order(requested_order, len(factors))
        forbidden = _exclusions(factors, exclude)
        counts = [len(factor.levels) for factor in factors]
        rows = [] if 0 in counts else _native.generate(counts, order, forbidden)
    except (TypeError, ValueError) as error:
        pytest.fail(f"{definition.nodeid}: {error}", pytrace=False)

    metafunc.parametrize(
        names,
        [_parameter_set(factors, row) for row in rows],
        indirect=[name for factor in factors for name in factor.indirect],
        scope=scope,
    )
