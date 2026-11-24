"""Keep pytest's parameter row and ID conventions at the collection boundary."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Literal, Never, TypeAlias, TypeGuard

import pytest
from _pytest.mark.structures import ParameterSet

FixtureScope: TypeAlias = Literal["function", "class", "module", "package", "session"]
ParameterIds: TypeAlias = Iterable[object] | Callable[[object], object] | None


@dataclass(frozen=True, slots=True)
class Level:
    """Keep the values, marks, and resolved ID fragment for a single factor level."""

    values: tuple[object, ...]
    marks: tuple[pytest.Mark | pytest.MarkDecorator, ...]
    # None here means the resolved fragment was HIDDEN_PARAM.
    id: str | None


def _are_parameter_names(names: tuple[object, ...]) -> TypeGuard[tuple[str, ...]]:
    return bool(names) and all(isinstance(name, str) and name for name in names)


def fail_collection(message: str) -> Never:
    """Report a collection failure without a Python traceback."""
    # pytest 8.4's decorator obscures the call signature of pytest.fail.
    raise pytest.fail.Exception(message, pytrace=False) from None


def parameter_rows(
    argnames: str | Sequence[str],
    argvalues: Iterable[object],
    ids: ParameterIds,
    *,
    metafunc: pytest.Metafunc,
) -> tuple[tuple[str, ...], tuple[Level, ...]]:
    """Read a factor without creating pytest calls or expanding its empty row."""
    parsed, force_tuple = ParameterSet._parse_parametrize_args(argnames, argvalues)
    names = tuple(parsed)
    if not _are_parameter_names(names):
        message = "a factor must have nonempty parameter names"
        raise ValueError(message)
    sets = [ParameterSet.extract_from(value, force_tuple=force_tuple) for value in argvalues]
    for index, parameters in enumerate(sets):
        if len(parameters.values) != len(names):
            message = f"candidate {index} must specify {len(names)} values for {names!r}"
            raise ValueError(message)

    if not sets:
        return names, ()

    # Let pytest own fallback IDs, its ID hook, escaping, and per-factor duplicates.
    resolved = metafunc._resolve_parameter_set_ids(names, ids, sets, metafunc.definition.nodeid)
    return names, tuple(
        Level(
            tuple(parameters.values),
            tuple(parameters.marks),
            fragment if isinstance(fragment, str) else None,
        )
        for parameters, fragment in zip(sets, resolved, strict=True)
    )


def register_rows(
    metafunc: pytest.Metafunc,
    names: Sequence[str],
    rows: Iterable[Sequence[Level]],
    *,
    indirect: Sequence[str],
    scope: FixtureScope | None,
) -> None:
    """Register generated rows with the factor IDs already resolved by pytest."""
    parameters = []
    ids = []
    for row in rows:
        parameters.append(
            pytest.param(
                *(value for level in row for value in level.values),
                marks=tuple(mark for level in row for mark in level.marks),
            )
        )
        visible_ids = [level.id for level in row if level.id is not None]
        # Pytest accepts named objects as IDs and uses their name verbatim.
        # Raw strings would escape the already-resolved factor IDs a second time.
        ids.append(
            SimpleNamespace(__name__="-".join(visible_ids)) if visible_ids else pytest.HIDDEN_PARAM
        )
    definition = metafunc.definition
    fixtureinfo = definition._fixtureinfo
    direct_names = [name for name in names if name not in indirect]
    for name in direct_names:
        # Preserve pytest's duplicate error before a direct value shadows the fixture.
        for fixture in reversed(fixtureinfo.name2fixturedefs.get(name, ())):
            if fixture.params is not None:
                fail_collection(f"In {definition.nodeid}: duplicate parametrization of {name!r}")
            if name not in fixture.argnames:
                break

    metafunc.parametrize(names, parameters, ids=ids, indirect=indirect, scope=scope)
    if direct_names:
        # Pytest ordinarily prunes after all generate-tests hooks. It needs the
        # reduced closure now, before its fixture hook parametrizes dependencies
        # of the fixtures replaced by the direct values.
        fixtureinfo.prune_dependency_tree()
