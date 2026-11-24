from collections.abc import Sequence
from typing import TypeAlias

ForbiddenRule: TypeAlias = Sequence[tuple[int, Sequence[int]]]

def generate(
    level_counts: Sequence[int], order: int, forbidden: Sequence[ForbiddenRule]
) -> list[list[int]]: ...
