"""Derive a release version from main history and stamp the build checkout."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from .release_assets import manifest_tag, release_version

if TYPE_CHECKING:
    from collections.abc import Iterable

_BOOTSTRAP = "v0.1.0"
_VERSION_FIELDS = {
    "Cargo.toml": (r'(\[workspace\.package\]\nversion = ")[^"]+(")',),
    "pyproject.toml": (r'(\[project\]\nname = "pytest-allpair"\nversion = ")[^"]+(")',),
    "Cargo.lock": (
        r'(\[\[package\]\]\nname = "pytest-allpair-core"\nversion = ")[^"]+(")',
        r'(\[\[package\]\]\nname = "pytest-allpair-python"\nversion = ")[^"]+(")',
    ),
    "fuzz/Cargo.lock": (r'(\[\[package\]\]\nname = "pytest-allpair-core"\nversion = ")[^"]+(")',),
    "uv.lock": (r'(\[\[package\]\]\nname = "pytest-allpair"\nversion = ")[^"]+(")',),
}


def _parts(tag: str) -> tuple[int, int, int]:
    major, minor, patch = release_version(tag).split(".")
    return int(major), int(minor), int(patch)


def tag_after(base: str, minimums: Iterable[str]) -> str:
    """Advance one patch per commit, honoring a higher committed version."""
    major, minor, patch = _parts(base)
    for minimum in minimums:
        major, minor, patch = max((major, minor, patch + 1), _parts(minimum))
    return f"v{major}.{minor}.{patch}"


def _git(*args: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        message = "Git is required to compute the release version"
        raise FileNotFoundError(message)
    return subprocess.run(  # noqa: S603 -- Git commands use fixed argv and validated refs.
        [executable, *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    ).stdout.strip()


def automatic_tag(commit: str) -> str:
    """Map a commit to its tag independently of other releases in progress."""
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        message = "expected the full main commit SHA"
        raise ValueError(message)
    bootstrap = _git("rev-parse", f"{_BOOTSTRAP}^{{commit}}")
    history = _git("rev-list", "--first-parent", commit).splitlines()
    try:
        boundary = history.index(bootstrap)
    except ValueError as error:
        message = f"{_BOOTSTRAP} must be on the commit's first-parent history"
        raise ValueError(message) from error
    if boundary == 0:
        message = "the initial release already has a tag"
        raise ValueError(message)
    minimums = (
        manifest_tag(_git("show", f"{sha}:pyproject.toml")) for sha in reversed(history[:boundary])
    )
    return tag_after(_BOOTSTRAP, minimums)


def stamp_version(tag: str) -> None:
    """Set the temporary checkout's version consistently without resolving dependencies."""
    version = release_version(tag)
    if _parts(tag) < _parts(manifest_tag()):
        message = f"release tag {tag} is below the committed package version"
        raise ValueError(message)
    updates: dict[Path, str] = {}
    for filename, fields in _VERSION_FIELDS.items():
        path = Path(filename)
        source = path.read_text(encoding="utf-8")
        for field in fields:
            source, count = re.subn(field, rf"\g<1>{version}\g<2>", source)
            if count != 1:
                message = f"expected one version field for {field} in {filename}"
                raise ValueError(message)
        updates[path] = source
    for path, source in updates.items():
        path.write_text(source, encoding="utf-8", newline="\n")


class _Options(argparse.Namespace):
    command: str
    value: str


def main() -> None:
    """Print a deterministic tag or stamp that tag into a build checkout."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("tag", "stamp"))
    parser.add_argument("value")
    options = parser.parse_args(namespace=_Options())
    if options.command == "tag":
        print(automatic_tag(options.value))  # noqa: T201 -- Workflow output.
    else:
        stamp_version(options.value)


if __name__ == "__main__":
    main()
