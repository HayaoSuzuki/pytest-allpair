# pytest-allpair

pytest の収集時に、制約を満たす n 因子の組を網羅するテストケースを生成するプラグインです。既定では因子を二つずつ組み合わせて網羅します。Python の値、fixture、ID、マークは pytest を通じて扱います。

ソースからインストールするには Rust と通常ビルドの CPython 3.11〜3.15 が必要です。

```sh
uv pip install .
```

```python
import pytest


@pytest.mark.pairwise(exclude=[{"os": "linux", "filesystem": "ntfs"}])
@pytest.mark.pairwise_parametrize("os", ["linux", "windows"])
@pytest.mark.pairwise_parametrize("filesystem", ["ext4", "ntfs"])
@pytest.mark.pairwise_parametrize("cache", [False, True])
def test_storage(os, filesystem, cache):
    assert (os, filesystem) != ("linux", "ntfs")
```

通常の `pytest.mark.parametrize` を同じテストに使うと、その候補は生成された全ケースと組み合わさります。

- [クイックスタート](docs/user/guides/quickstart.md)
- [マークの仕様](docs/user/reference/markers.md)
- [生成器と pytest の設計](docs/development/architecture/pairwise-plugin.md)
- [検証手順](docs/development/guides/verification.md)
- [ライセンス](LICENSE)
