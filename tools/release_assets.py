"""Validate release wheels and bind their CycloneDX SBOMs to the release inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

NATIVE_BOM = "pytest-allpair-python.cyclonedx.json"
PLATFORMS = {
    "linux": r"manylinux_2_28_x86_64",
    "macos": r"macosx_[0-9]+_[0-9]+_arm64",
    "windows": r"win_amd64",
}
_TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def release_version(tag: str) -> str:
    """Require a stable version tag and return the package version."""
    if _TAG.fullmatch(tag) is None:
        message = f"expected a stable release tag, got {tag!r}"
        raise ValueError(message)
    return tag[1:]


def manifest_tag(source: str | None = None) -> str:
    """Read the release tag from the project's package version."""
    if source is None:
        source = Path("pyproject.toml").read_text(encoding="utf-8")
    metadata: object = tomllib.loads(source)
    version = object_map(object_map(metadata).get("project")).get("version")
    if not isinstance(version, str):
        message = "missing project.version"
        raise TypeError(message)
    tag = f"v{version}"
    release_version(tag)
    return tag


def object_map(value: object) -> dict[str, object]:
    """Read a JSON or TOML mapping with string keys."""
    if isinstance(value, dict):
        return {key: item for key, item in value.items() if isinstance(key, str)}
    message = "expected a structured object"
    raise TypeError(message)


def digest(path: Path) -> str:
    """Compute the SHA-256 digest of a file."""
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def platform_wheel(wheel: Path, version: str) -> str:
    """Identify a wheel using the exact supported release tags."""
    prefix = f"pytest_allpair-{version}-cp311-abi3-"
    for platform, pattern in PLATFORMS.items():
        if re.fullmatch(re.escape(prefix) + pattern + r"\.whl", wheel.name):
            return platform
    message = f"unexpected wheel for {version}: {wheel.name}"
    raise ValueError(message)


def wheel_documents(wheel: Path, version: str) -> dict[str, bytes]:
    """Check the distribution metadata and return its embedded BOMs."""
    platform_wheel(wheel, version)
    dist_info = f"pytest_allpair-{version}.dist-info"
    prefix = f"{dist_info}/sboms/"
    with ZipFile(wheel) as archive:
        metadata = BytesParser().parsebytes(archive.read(f"{dist_info}/METADATA"))
        if metadata["Name"] != "pytest-allpair" or metadata["Version"] != version:
            message = f"unexpected name or version in {wheel.name} metadata"
            raise ValueError(message)
        if (
            metadata["License-Expression"] != "MIT"
            or metadata["License-File"] != "LICENSE"
            or not archive.read(f"{dist_info}/licenses/LICENSE").strip()
        ):
            message = f"{wheel.name} is missing its MIT license metadata or license file"
            raise ValueError(message)
        names = [name for name in archive.namelist() if name.startswith(prefix)]
        documents = {name.removeprefix(prefix): archive.read(name) for name in names}
    if len(names) != len(documents) or not documents.keys() <= {NATIVE_BOM, "auditwheel.cdx.json"}:
        message = f"unexpected SBOM inventory in {wheel.name}"
        raise ValueError(message)
    if NATIVE_BOM not in documents:
        message = f"{wheel.name} is missing the Cargo SBOM"
        raise ValueError(message)

    for name, data in documents.items():
        bom = object_map(json.loads(data))
        if bom.get("bomFormat") != "CycloneDX" or bom.get("specVersion") not in {"1.4", "1.5"}:
            message = f"{wheel.name} contains an invalid CycloneDX document: {name}"
            raise ValueError(message)
    native = object_map(json.loads(documents[NATIVE_BOM]))
    root = object_map(object_map(native.get("metadata")).get("component"))
    components = native.get("components")
    if (
        native.get("specVersion") != "1.5"
        or root.get("name") != "pytest-allpair-python"
        or root.get("version") != version
        or not isinstance(components, list)
        or not any(
            object_map(component).get("name") == "pytest-allpair-core"
            and object_map(component).get("version") == version
            for component in components
        )
    ):
        message = f"{wheel.name} contains an unexpected Cargo dependency graph"
        raise ValueError(message)
    return documents


def release_wheels(directory: Path, tag: str) -> dict[str, Path]:
    """Require exactly one release wheel per platform."""
    version = release_version(tag)
    wheels = sorted(directory.glob("*.whl"))
    by_platform = {platform_wheel(wheel, version): wheel for wheel in wheels}
    if len(wheels) != len(PLATFORMS) or by_platform.keys() != PLATFORMS.keys():
        message = f"unexpected wheel inventory in {directory}"
        raise ValueError(message)
    return by_platform


def checksum_text(assets: list[Path]) -> str:
    """Compute a stable checksum manifest for the provided files."""
    return "".join(f"{digest(asset)}  {asset.name}\n" for asset in sorted(assets))


def release_inventory(directory: Path, tag: str, *, verify: bool) -> None:
    """Extract wheel SBOMs or verify an existing release inventory."""
    version = release_version(tag)
    assets = list(release_wheels(directory, tag).values())
    for wheel in assets.copy():
        for name, data in wheel_documents(wheel, version).items():
            sbom = directory / f"{wheel.name}.{name}"
            assets.append(sbom)
            if not verify:
                sbom.write_bytes(data)
            elif sbom.read_bytes() != data:
                message = f"SBOM differs from the document embedded in {wheel.name}"
                raise ValueError(message)
    checksum = directory / "SHA256SUMS"
    contents = checksum_text(assets)
    if not verify:
        checksum.write_text(contents, encoding="ascii")
    elif checksum.read_text(encoding="ascii") != contents:
        message = "release checksums do not match the wheel and SBOM files"
        raise ValueError(message)
    if set(directory.iterdir()) != {*assets, checksum}:
        message = f"unexpected files in the release inventory at {directory}"
        raise ValueError(message)


class _Options(argparse.Namespace):
    command: str
    tag: str | None
    path: Path | None
    platform: str | None


def main() -> None:
    """Expose the checks used by CI and the release workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("tag", "wheel", "prepare", "verify", "platform"))
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--platform", choices=PLATFORMS)
    options = parser.parse_args(namespace=_Options())
    command = options.command
    tag = options.tag or manifest_tag()
    path = options.path
    if command == "tag":
        if tag != manifest_tag():
            parser.error("release tag must match project.version")
        print(tag)  # noqa: T201 -- The workflow consumes the computed tag.
        return
    if path is None:
        parser.error("path is required")
    match command:
        case "wheel":
            wheel_documents(path, release_version(tag))
        case "prepare" | "verify":
            release_inventory(path, tag, verify=command == "verify")
        case "platform":
            platform = options.platform
            if platform is None:
                parser.error("--platform is required")
            print(release_wheels(path, tag)[platform])  # noqa: T201 -- Workflow output.


if __name__ == "__main__":
    main()
