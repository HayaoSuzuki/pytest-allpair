import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from tools.release_assets import NATIVE_BOM, release_inventory, release_version, release_wheels

_TAG = "v0.1.0"
_DIST_INFO = "pytest_allpair-0.1.0.dist-info"


def _wheel(directory: Path, platform: str, *, sbom: bool = True) -> Path:
    wheel = directory / f"pytest_allpair-0.1.0-cp311-abi3-{platform}.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"{_DIST_INFO}/METADATA",
            "Name: pytest-allpair\nVersion: 0.1.0\n"
            "License-Expression: MIT\nLicense-File: LICENSE\n",
        )
        archive.writestr(f"{_DIST_INFO}/licenses/LICENSE", "MIT license text")
        if sbom:
            archive.writestr(
                f"{_DIST_INFO}/sboms/{NATIVE_BOM}",
                json.dumps(
                    {
                        "bomFormat": "CycloneDX",
                        "specVersion": "1.5",
                        "metadata": {
                            "component": {"name": "pytest-allpair-python", "version": "0.1.0"},
                        },
                        "components": [{"name": "pytest-allpair-core", "version": "0.1.0"}],
                    }
                ),
            )
    return wheel


@pytest.fixture
def release_directory(tmp_path: Path) -> Path:
    """Create an unsigned release inventory for the three target platforms."""
    for platform in ("manylinux_2_28_x86_64", "macosx_11_0_arm64", "win_amd64"):
        _wheel(tmp_path, platform)
    return tmp_path


@pytest.mark.parametrize("tag", ["0.1.0", "v00.1.0", "v0.1.0rc1", "v0.1.0/other"])
def test_release_tags_must_be_stable(tag: str) -> None:
    with pytest.raises(ValueError, match="stable release tag"):
        release_version(tag)


def test_release_checksums_bind_wheels_and_sboms(release_directory: Path) -> None:
    release_inventory(release_directory, _TAG, verify=False)
    release_inventory(release_directory, _TAG, verify=True)
    assert len((release_directory / "SHA256SUMS").read_text().splitlines()) == 6


def test_release_rejects_changed_sbom(release_directory: Path) -> None:
    release_inventory(release_directory, _TAG, verify=False)
    for sbom in release_directory.glob("*.json"):
        sbom.write_bytes(b"{}")
    with pytest.raises(ValueError, match="differs from the document embedded"):
        release_inventory(release_directory, _TAG, verify=True)


def test_release_rejects_missing_wheel_sbom(release_directory: Path) -> None:
    _wheel(release_directory, "win_amd64", sbom=False)
    with pytest.raises(ValueError, match="missing the Cargo SBOM"):
        release_inventory(release_directory, _TAG, verify=False)


def test_release_rejects_duplicate_targets(release_directory: Path) -> None:
    _wheel(release_directory, "macosx_12_0_arm64")
    with pytest.raises(ValueError, match="unexpected wheel inventory"):
        release_wheels(release_directory, _TAG)
