# pytest-allpair

pytest-allpair generates test cases during pytest collection to cover every feasible n-way combination. By default, it covers pairs of factors. The plugin uses pytest's handling of Python values, fixtures, test IDs, and marks.

## Installation

Use a standard (GIL-enabled) build of CPython 3.11 through 3.15. Add a released version from PyPI as a development dependency in your project.

```sh
uv add --dev pytest-allpair
```

Release builds target Linux x86-64 (manylinux 2.28), macOS Arm64, and Windows x86-64.

## Usage

```python
import pytest


@pytest.mark.pairwise(exclude=[{"os": "linux", "filesystem": "ntfs"}])
@pytest.mark.pairwise_parametrize("os", ["linux", "windows"])
@pytest.mark.pairwise_parametrize("filesystem", ["ext4", "ntfs"])
@pytest.mark.pairwise_parametrize("cache", [False, True])
def test_storage(os, filesystem, cache):
    assert (os, filesystem) != ("linux", "ntfs")
```

If the same test also uses `pytest.mark.parametrize`, each of its parameter sets runs with every generated case.

- [Quick start](docs/user/guides/quickstart.md)
- [Marker reference](docs/user/reference/markers.md)
- [Generator and pytest integration design](docs/development/architecture/pairwise-plugin.md)
- [Verification guide](docs/development/guides/verification.md)
- [License](LICENSE)
