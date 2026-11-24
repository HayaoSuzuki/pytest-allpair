"""Stage GitHub release wheels and verify the distribution bytes and PyPI evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

from pypi_attestations import (
    Attestation,
    AttestationType,
    Distribution,
    GitHubPublisher,
    Provenance,
)
from sigstore.models import Bundle

from .release_assets import digest, object_map, release_version, release_wheels

REPOSITORY = "HayaoSuzuki/pytest-allpair"
WORKFLOW = "release.yml"
SLSA = AttestationType.SLSA_PROVENANCE_V1
PUBLISH = AttestationType.PYPI_PUBLISH_V1
INDEXES = {
    "testpypi": ("test.pypi.org", "test-files.pythonhosted.org"),
    "pypi": ("pypi.org", "files.pythonhosted.org"),
}
_VERIFY_ATTEMPTS = 30
_NOT_FOUND = 404


def verify_build(wheel: Path, bundle: Path, commit: str) -> None:
    """Pin an original GitHub build signature to the tag's commit."""
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        message = "expected the full release commit"
        raise ValueError(message)
    gh = shutil.which("gh")
    if gh is None:
        message = "GitHub CLI is required to verify the build signature"
        raise FileNotFoundError(message)
    subprocess.run(  # noqa: S603 -- Fixed executable and explicit argv.
        [
            gh,
            "attestation",
            "verify",
            str(wheel.resolve()),
            "--bundle",
            str(bundle.resolve()),
            "--repo",
            REPOSITORY,
            "--signer-workflow",
            f"{REPOSITORY}/.github/workflows/{WORKFLOW}",
            "--source-ref",
            "refs/heads/main",
            "--source-digest",
            commit,
            "--signer-digest",
            commit,
            "--deny-self-hosted-runners",
            "--predicate-type",
            SLSA,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        timeout=120,
    )


def stage(directory: Path, output: Path, tag: str, commit: str) -> None:
    """Convert already signed single-wheel bundles to the PyPI upload format."""
    wheels = release_wheels(directory, tag).values()
    publisher = GitHubPublisher(repository=REPOSITORY, workflow=WORKFLOW)
    with tempfile.TemporaryDirectory() as temporary:
        staged = Path(temporary) / "wheels"
        staged.mkdir()
        for wheel in wheels:
            bundle = wheel.with_suffix(".whl.sigstore.json")
            verify_build(wheel, bundle, commit)
            attestation = Attestation.from_bundle(Bundle.from_json(bundle.read_bytes()))
            kind, _ = attestation.verify(publisher, Distribution.from_file(wheel))
            if kind != SLSA:
                message = f"expected a single-wheel SLSA statement for {wheel.name}"
                raise ValueError(message)
            shutil.copy2(wheel, staged / wheel.name)
            (staged / f"{wheel.name}.slsa.attestation").write_text(
                attestation.model_dump_json(), encoding="utf-8"
            )
        shutil.copytree(staged, output)


def read_bytes(url: str, *, limit: int = -1) -> bytes:
    """Read an index response using an explicitly selected HTTPS host."""
    with urlopen(url, timeout=30) as response:  # noqa: S310 -- Fixed HTTPS hosts.
        body: object = response.read(limit)
    if not isinstance(body, bytes):
        message = "expected a binary HTTP response"
        raise TypeError(message)
    return body


def index_files(index: str, version: str) -> dict[str, object]:
    """Return the published file URLs, rejecting duplicate filenames."""
    host, _ = INDEXES[index]
    data = object_map(json.loads(read_bytes(f"https://{host}/pypi/pytest-allpair/{version}/json")))
    records = data.get("urls")
    if not isinstance(records, list):
        message = f"{index} returned an invalid file inventory"
        raise TypeError(message)
    files: dict[str, object] = {}
    for value in records:
        record = object_map(value)
        name = record.get("filename")
        if not isinstance(name, str) or name in files:
            message = f"{index} returned a missing or duplicate filename"
            raise ValueError(message)
        files[name] = record.get("url")
    return files


def verify_download(wheel: Path, url: object, download_host: str) -> None:
    """Compare the actual bytes served by an index with the release wheel."""
    if not isinstance(url, str) or not url.startswith(f"https://{download_host}/packages/"):
        message = f"unexpected download URL for {wheel.name}"
        raise ValueError(message)
    published = read_bytes(url, limit=wheel.stat().st_size + 1)
    if hashlib.sha256(published).hexdigest() != digest(wheel):
        message = f"published bytes differ from the release wheel {wheel.name}"
        raise ValueError(message)


def verify_provenance(wheel: Path, provenance: Provenance, index: str, commit: str) -> None:
    """Check both predicates, the index publisher, and the original build identity."""
    publisher = GitHubPublisher(repository=REPOSITORY, workflow=WORKFLOW, environment=index)
    if len(provenance.attestation_bundles) != 1:
        message = f"expected one publisher bundle for {wheel.name}"
        raise ValueError(message)
    (bundle,) = provenance.attestation_bundles
    if bundle.publisher != publisher:
        message = f"unexpected publisher of {wheel.name} on {index}"
        raise ValueError(message)
    distribution = Distribution.from_file(wheel)
    predicates: list[str] = []
    for attestation in bundle.attestations:
        kind, _ = attestation.verify(publisher, distribution)
        predicates.append(kind)
        if kind == SLSA:
            with tempfile.TemporaryDirectory() as temporary:
                original = Path(temporary) / "build.sigstore.json"
                original.write_text(attestation.to_bundle().to_json(), encoding="utf-8")
                verify_build(wheel, original, commit)
    if sorted(predicates) != sorted((SLSA, PUBLISH)):
        message = f"expected one SLSA and one publish attestation for {wheel.name}"
        raise ValueError(message)


def _verify_index_files(
    wheels: list[Path], files: dict[str, object], index: str, version: str, commit: str
) -> None:
    host, download_host = INDEXES[index]
    if files.keys() != {wheel.name for wheel in wheels}:
        message = f"{index} files do not match the release inventory"
        raise ValueError(message)
    for wheel in wheels:
        verify_download(wheel, files[wheel.name], download_host)
        endpoint = (
            f"https://{host}/integrity/pytest-allpair/{version}/{quote(wheel.name)}/provenance"
        )
        provenance = Provenance.model_validate_json(read_bytes(endpoint))
        verify_provenance(wheel, provenance, index, commit)


def verify_index(directory: Path, index: str, tag: str, commit: str, *, inspect: bool) -> bool:
    """Verify all published files, permitting an absent version only before upload."""
    wheels = list(release_wheels(directory, tag).values())
    version = release_version(tag)
    for attempt in range(_VERIFY_ATTEMPTS):
        try:
            files = index_files(index, version)
        except HTTPError as error:
            if error.code == _NOT_FOUND and inspect:
                return False
            if error.code != _NOT_FOUND or attempt == _VERIFY_ATTEMPTS - 1:
                raise
        else:
            try:
                _verify_index_files(wheels, files, index, version, commit)
            except HTTPError as error:
                if error.code != _NOT_FOUND or inspect or attempt == _VERIFY_ATTEMPTS - 1:
                    raise
            else:
                return True
        time.sleep(10)
    message = f"{index} verification exceeded its retry budget"
    raise RuntimeError(message)


class _Options(argparse.Namespace):
    command: str
    directory: Path
    tag: str
    commit: str
    index: str | None
    output: Path | None


def main() -> None:
    """Stage or verify a tagged release."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("stage", "inspect", "verify"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--index", choices=INDEXES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(namespace=_Options())
    if args.command == "stage":
        if args.output is None:
            parser.error("--output is required for stage")
        stage(args.directory, args.output, args.tag, args.commit)
        return
    if args.index is None:
        parser.error("--index is required for inspect and verify")
    exists = verify_index(
        args.directory, args.index, args.tag, args.commit, inspect=args.command == "inspect"
    )
    print("true" if exists else "false")  # noqa: T201 -- The caller consumes the result.


if __name__ == "__main__":
    main()
