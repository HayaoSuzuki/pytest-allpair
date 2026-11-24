# Quick start

Use a standard (GIL-enabled) build of CPython 3.11 through 3.15 and pytest 8.4.x or 9.x. You need the Rust toolchain to build from source. Run these commands from the root of the checkout.

```sh
uv venv
uv pip install .
uv run --no-sync pytest
```

Declare three factors with two values each. By default, the collected cases exercise all four pairs of values for any two factors you choose.

```python
import pytest


@pytest.mark.pairwise_parametrize("backend", ["sqlite", "pg"])
@pytest.mark.pairwise_parametrize("cache", [False, True])
@pytest.mark.pairwise_parametrize("mode", ["read", "write"])
def test_storage(backend, cache, mode): ...
```

Run `pytest --collect-only -q` to inspect the generated cases. Set `order=3` to cover combinations of three factors. Specify invalid combinations by argument name and value.

```python
@pytest.mark.pairwise(order=3, exclude=[{"backend": "sqlite", "replicas": 3}])
@pytest.mark.pairwise_parametrize("backend", ["sqlite", "pg"])
@pytest.mark.pairwise_parametrize("replicas", [1, 3])
@pytest.mark.pairwise_parametrize("cache", [False, True])
@pytest.mark.pairwise_parametrize("mode", ["read", "write"])
@pytest.mark.parametrize("user", ["staff", "guest"])
def test_distributed_storage(backend, replicas, cache, mode, user): ...
```

Because `user` uses the standard `parametrize` marker, pytest runs each generated case with both `staff` and `guest`. See the [marker reference](../reference/markers.md) for the full options.
