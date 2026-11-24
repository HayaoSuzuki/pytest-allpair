from __future__ import annotations

from pathlib import Path

import pytest

from tools import release_version
from tools.release_assets import manifest_tag


@pytest.mark.parametrize(
    ("minimums", "expected"),
    [
        ([], "v0.1.0"),
        (["v0.1.0"], "v0.1.1"),
        (["v0.1.0", "v0.1.0", "v0.1.0"], "v0.1.3"),
        (["v0.1.0", "v0.2.0", "v0.2.0"], "v0.2.1"),
        (["v0.1.9", "v0.1.9"], "v0.1.10"),
    ],
)
def test_tag_follows_the_order_of_main_commits(minimums: list[str], expected: str) -> None:
    assert release_version.tag_after("v0.1.0", minimums) == expected


def test_stamp_changes_distributions_and_local_locks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "fuzz").mkdir()
    manifests = (Path("Cargo.toml"), Path("Cargo.lock"), Path("pyproject.toml"), Path("uv.lock"))
    for relative in (*manifests, Path("fuzz/Cargo.lock")):
        (tmp_path / relative).write_bytes((root / relative).read_bytes())
    monkeypatch.chdir(tmp_path)

    tag = release_version.tag_after(manifest_tag(), ["v0.0.0"])
    release_version.stamp_version(tag)

    version = f'version = "{tag[1:]}"'
    assert version in Path("Cargo.toml").read_text(encoding="utf-8")
    assert version in Path("pyproject.toml").read_text(encoding="utf-8")
    uv_lock = Path("uv.lock").read_text(encoding="utf-8")
    assert f'name = "pytest-allpair"\n{version}' in uv_lock
    lock = Path("Cargo.lock").read_text(encoding="utf-8")
    assert f'name = "pytest-allpair-core"\n{version}' in lock
    assert f'name = "pytest-allpair-python"\n{version}' in lock
    fuzz_lock = Path("fuzz/Cargo.lock").read_text(encoding="utf-8")
    assert f'name = "pytest-allpair-core"\n{version}' in fuzz_lock
