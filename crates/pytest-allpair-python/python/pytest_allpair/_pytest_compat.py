"""Keep pytest's parameter row and ID conventions at the collection boundary."""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import pytest
from _pytest.mark.structures import ParameterSet


@dataclass(frozen=True, slots=True)
class Level:
    values: tuple[object, ...]
    marks: tuple[pytest.Mark | pytest.MarkDecorator, ...]
    # None here means the resolved fragment was HIDDEN_PARAM.
    id: str | None


def parameter_rows(
    argnames: str | Sequence[str],
    argvalues: Iterable[object],
    ids: Iterable[object] | Callable[[Any], object] | None,
    *,
    metafunc: pytest.Metafunc,
) -> tuple[tuple[str, ...], tuple[Level, ...]]:
    """Read a factor without creating pytest calls or expanding its empty row."""
    parsed, force_tuple = ParameterSet._parse_parametrize_args(argnames, argvalues)
    names = tuple(parsed)
    if not names or any(not isinstance(name, str) or not name for name in names):
        raise ValueError("a factor must have nonempty parameter names")
    sets = [ParameterSet.extract_from(value, force_tuple=force_tuple) for value in argvalues]
    for index, parameters in enumerate(sets):
        if len(parameters.values) != len(names):
            raise ValueError(f"candidate {index} must specify {len(names)} values for {names!r}")

    if not sets:
        return names, ()

    # Let pytest own fallback IDs, its ID hook, escaping, and per-factor duplicates.
    resolved = metafunc._resolve_parameter_set_ids(names, ids, sets, metafunc.definition.nodeid)
    return names, tuple(
        Level(tuple(parameters.values), tuple(parameters.marks), fragment if isinstance(fragment, str) else None)
        for parameters, fragment in zip(sets, resolved, strict=True)
    )
