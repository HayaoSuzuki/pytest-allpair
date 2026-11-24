# クイックスタート

通常ビルドの CPython 3.11〜3.15 と pytest 8.4 系または 9 系を使います。リポジトリをチェックアウト済みなら、ルートで次を実行します。その場でソースをビルドする場合は Rust ツールチェーンも必要です。

```sh
uv venv
uv pip install .
uv run --no-sync pytest
```

二値の3因子を宣言すると、既定では異なるどの2因子を選んでも、4通りの値のペアを少なくとも一度実行するケースが収集されます。

```python
import pytest


@pytest.mark.pairwise_parametrize("backend", ["sqlite", "pg"])
@pytest.mark.pairwise_parametrize("cache", [False, True])
@pytest.mark.pairwise_parametrize("mode", ["read", "write"])
def test_storage(backend, cache, mode): ...
```

`pytest --collect-only -q` で生成したケースを確認できます。3因子ごとの組を網羅するには `order=3` を指定します。無効な組は引数名と値で指定します。

```python
@pytest.mark.pairwise(order=3, exclude=[{"backend": "sqlite", "replicas": 3}])
@pytest.mark.pairwise_parametrize("backend", ["sqlite", "pg"])
@pytest.mark.pairwise_parametrize("replicas", [1, 3])
@pytest.mark.pairwise_parametrize("cache", [False, True])
@pytest.mark.pairwise_parametrize("mode", ["read", "write"])
@pytest.mark.parametrize("user", ["staff", "guest"])
def test_distributed_storage(backend, replicas, cache, mode, user): ...
```

`user` は標準マークで指定したため、生成された各ケースを `staff` と `guest` の両方で実行します。マークの詳細は[リファレンス](../reference/markers.md)に記載しています。
