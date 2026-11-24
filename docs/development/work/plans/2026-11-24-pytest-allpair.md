# pytest-allpair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** pytest の収集時に、宣言した因子から制約付きの n 因子網羅ケースを生成する MIT ライセンスのプラグインを作る。

**Architecture:** Python が pytest マークを候補行番号と除外条件へ変換し、Rust が有効な網羅ケースを選ぶ。Python が各行の値、マーク、ID を復元し、`Metafunc.parametrize` にまとめて登録する。

**Tech Stack:** Rust 2024、PyO3 0.30.1 の `abi3-py311`、maturin、uv、pytest、cargo-fuzz。Quint と TLC は独立した枝刈り検証の試行に使う。

**Spec:** [pytest-allpair の設計](../../architecture/pairwise-plugin.md)

## Global Constraints

- 通常ビルドの CPython 3.11〜3.15 と pytest 8.4 系・9 系を対象とする。
- Linux、macOS、Windows では wheel をインストールし、自動読み込みとテストの実行まで確認する。
- 初版の生成オプションは `order` と `exclude` とする。ライセンスは MIT とする。
- 同じバージョンで、因子と候補の順序、次数、除外条件が同じなら、生成結果の行と順序は同じになる。
- 完全ケースの直積を中間表として全件保持する処理を避ける。参照照合器の入力は小さなモデルに限定する。
- 各タスクを独立したテストとコミットで完了させる。発行用アカウントへの公開は別の作業とする。

## Review Focus

- 複数の除外条件によって初めて不可能になる n 因子の組を網羅要求から外し、完成可能な組はすべて覆う（Task 1）。
- `ids` の連結結果が同じ文字列になっても、生成行の node ID を一意にする（Task 3）。
- 等値だが異なる候補行を区別し、同じ値を指定した除外は一致する全行に適用する（Task 3）。
- `indirect=True` と `fixture(params=...)` が同じ引数に値を与えたら、収集エラーにする（Task 3）。
- ソースツリー外の新規環境で wheel をインストールすると、標準のプラグイン自動読み込みでテストを実行できる（Task 2、5）。

---

## ファイル構成

| 場所 | 責務 |
| --- | --- |
| `Cargo.toml`、`Cargo.lock`、`rust-toolchain.toml`、`.cargo/config.toml` | ワークスペース、固定ツールチェーン、Rust の開発設定 |
| `crates/pytest-allpair-core/src/lib.rs` | 候補番号の検証、制約付き探索、網羅行の選択 |
| `crates/pytest-allpair-python/src/lib.rs` | Rust の生成関数を PyO3 で公開し、失敗を Python 例外に変換 |
| `crates/pytest-allpair-python/python/pytest_allpair/` | `plugin.py` が pytest フックとモデルの組み立て、`_pytest_compat.py` が pytest のバージョン差を担当 |
| `pyproject.toml`、`uv.lock`、`prek.toml` | maturin と pytest エントリポイント、Python 開発環境と検査設定 |
| `formal/coverage_oracle.rs`、`fuzz/`、`formal/quint/` | 独立な総当たり照合、ファズテスト、枝刈りのモデル検査 |
| `tests/`、`tools/`、`infra/`、`.github/workflows/` | pytest 統合テスト、配布物の検証、CI の設定 |
| `README.md`、`LICENSE`、`docs/user/`、`docs/development/` | インストールと利用方法、ライセンス、開発と検証の手順 |

### Task 1: 制約付き網羅と総当たり照合

**Files:** Create `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`, `.cargo/config.toml`, `crates/pytest-allpair-core/{Cargo.toml,src/lib.rs,tests/coverage.rs}`, `formal/coverage_oracle.rs`.

**Interfaces:** 次の公開関数と型を生成器の契約とする。禁止規則の各項は因子番号と候補番号の集合であり、規則の全項に一致する完全ケースを除外する。`formal/coverage_oracle.rs` の `check(level_counts: &[usize], order: usize, forbidden: &[ForbiddenRule], result: &Result<Vec<Vec<usize>>, GenerateError>) -> (usize, usize)` は、不適合時に失敗し、有効な行数と必要な組の数を返す。

```rust
pub struct ForbiddenRule {
    pub terms: Vec<(usize, Vec<usize>)>,
}
pub enum GenerateError {
    InvalidModel(String),
    NoValidCases,
}
pub fn generate(
    level_counts: &[usize],
    order: usize,
    forbidden: &[ForbiddenRule],
) -> Result<Vec<Vec<usize>>, GenerateError>;
```

- [ ] ワークスペースとテストを作る。ルートの Cargo resolver は `3`、Rust は hoimin と同じ `1.100.0` とし、別ワークスペースの `fuzz/` を除外する。照合器は小さな直積を列挙して行の合法性と網羅集合の一致を判定する。`coverage.rs` は `#[path]` で照合器を読む。
- [ ] 回帰テスト `covers_feasible_pairs` を先に書く。`[2, 2, 2]`、次数 2、禁止規則 `[(0,[0]), (1,[0])]` で、照合器の有効行数が 6、必要な組が 11 であり、生成行がすべて有効であることを検証する。
- [ ] `multiple_rules_block_one_projection` では、同じモデルで `(A,B,C)=(0,0,0),(0,0,1)` を別規則として除外し、必要な組が 11 になることを照合する。`supports_order_one_three_and_full` では `[2,3,2,2]` に対して次数 1、3、4 を照合する。`rejects_invalid_or_unsatisfiable_models` では次数 0 と因子数超過を `InvalidModel`、全水準を除外する制約を `NoValidCases` と区別する。
- [ ] `cargo test -p pytest-allpair-core --test coverage` を実行し、生成器が未実装のため失敗することを確認する。
- [ ] `generate` を実装する。次数分の因子と水準の組を順に列挙し、未網羅の組を種に深さ優先探索で有効行を探す。候補の順序は新たに網羅できる組の数と因子・水準の位置で決める。禁止規則の全項が確定して一致した時点でその枝を捨て、候補が尽きるまで探索しても有効行がなければ、その組を網羅対象から外す。見つけた完全ケースで覆う組を記録し、次の未網羅の組に進む。次数が因子数と等しい場合は合法な行を順に列挙する。
- [ ] `deterministic_on_large_cartesian_space` を追加する。二値20因子、次数2で結果を2回比較し、全760ペアを覆うことと、行が760件以下であることを検証する。このテストでは期待集合を二因子の値から作る。
- [ ] `cargo fmt --all --check`、`cargo test --locked -p pytest-allpair-core`、`cargo clippy --locked -p pytest-allpair-core --all-targets -- -D warnings` が成功したら、生成器と照合器をコミットする。

### Task 2: インストールできる Python パッケージと Rust 接続

**Files:** Modify `Cargo.toml`, `Cargo.lock`, `.gitignore`. Create `pyproject.toml`, `uv.lock`, `LICENSE`, `crates/pytest-allpair-python/{Cargo.toml,src/lib.rs,python/pytest_allpair/__init__.py,python/pytest_allpair/plugin.py}`, `tests/test_native.py`.

**Interfaces:** `pytest_allpair._native.generate(level_counts: list[int], order: int, forbidden: list[list[tuple[int, list[int]]]]) -> list[list[int]]`。Task 1 の `generate` を呼び、Rust の無解と不正モデルは Python の `ValueError` に変換する。

- [ ] `test_native_solves_two_by_two` を作り、`_native.generate([2, 2], 2, [])` が4行の全組を返すこと、`_native.generate([2], 1, [[(0, [0, 1])]])` が `ValueError` を出すことを検証する。混合パッケージと空の `_native` モジュールで先にビルドを通し、`uv run --locked pytest -q tests/test_native.py` が `generate` 未定義で失敗することを確認する。
- [ ] Python 側の配布名を `pytest-allpair`、モジュール名を `pytest_allpair._native` とし、PyO3 で Task 1 の入出力型を変換する。maturin の `manifest-path` は Python クレート、`python-source` はその中の `python/` を指す。エントリポイントは `[project.entry-points.pytest11]` の `allpair = "pytest_allpair.plugin"`。Python の範囲を `>=3.11,<3.16`、pytest の範囲を `>=8.4,<10` とする。 [maturin の構成](https://www.maturin.rs/project_layout.html) · [PyO3 の ABI](https://docs.rs/crate/pyo3/0.30.1/source/guide/src/features.md)
- [ ] MIT の `LICENSE` と配布メタデータを置く。`uv lock` と `uv sync --locked` を実行し、`uv run --locked pytest -q tests/test_native.py` が成功したらコミットする。

### Task 3: pytest のマーク、値、ID、fixture の接続

**Files:** Modify `crates/pytest-allpair-python/python/pytest_allpair/plugin.py`. Create `crates/pytest-allpair-python/python/pytest_allpair/_pytest_compat.py`, `tests/test_plugin.py`.

**Interfaces:** `pytest_configure(config: pytest.Config) -> None` と `pytest_generate_tests(metafunc: pytest.Metafunc) -> None`。互換モジュールの `parameter_rows(argnames, argvalues, ids, *, metafunc)` は因子の引数名と、各水準の値のタプル・マーク列・解決済み ID を返す。空の因子では候補行を空のまま返す。数値モデルは Task 2 のネイティブ関数に渡す。

- [ ] `pytest_plugins = ("pytester",)` を `tests/test_plugin.py` で宣言し、`pytester` で `test_pairwise_cases` を作る。二値3因子に既定の次数を適用し、収集した行から各ペアが4通り出ることを検証する。`test_order_and_exclusions` は二値4因子で `order=3` と `exclude=[{"a": 0, "b": 0}]` を使い、各行の合法性と、許可行の全3因子組との一致を検証する。
- [ ] `test_grouped_values_and_ids` で `(input, expected)` の対応、`ids` の列と callable、`pytest.param` の明示 ID と `xfail`、`pytest.HIDDEN_PARAM` を確認する。`test_joined_ids_are_unique` は `a-b` と `a`、`c` と `b-c` を因子 ID にして、連結後も node ID が4件とも一意であることを確認する。
- [ ] `test_exclusions_match_every_equal_level` は等値のリスト2件と別のリスト1件を用意する。除外なしでは両方の等値行の明示 ID を確認し、除外時は両方が除かれることを確認する。`test_empty_factor_follows_pytest_ini` は既定の skip と `empty_parameter_set_mark=fail_at_collect` の両方を試す。
- [ ] `test_fixtures_and_standard_parametrize` は標準マークと別名の `fixture(params=...)` が直積に加わり、`indirect` で指定した fixture が `request.param` を受け取ることを確認する。`test_duplicate_indirect_fixture_parameter` は `fixture(params=...)` と専用マークに同じ引数を指定し、収集エラーを確認する。`test_class_and_module_factors` は両方の階層で因子を宣言し、関数の設定が全因子に適用されることを確認する。
- [ ] `test_invalid_declarations` をパラメータ化し、範囲外の次数、設定マークの重複・誤配置、未知の除外キー・値、真偽を判定できない比較、空の除外辞書、`order=True`、異なる明示 `scope`、一部の因子だけに明示した `scope`、制約で有効行が無い場合を、それぞれテスト名と原因を含む収集エラーとして確認する。
- [ ] `uv run --locked pytest -q tests/test_plugin.py` を実行し、フックが未実装のため対象テストが失敗することを確認する。
- [ ] フックでマークを登録・検証する。因子と設定マークは `metafunc.definition.iter_markers_with_node` から取得する。引数形状・候補行・因子 ID の処理は互換モジュールに置き、公開 API で扱えない処理には pytest の `ParameterSet` と `IdMaker` を局所的に再利用する。普通の Python オブジェクトへのハッシュ要求を導入せず、除外対象を候補番号へ変換する。
- [ ] 選んだ行から値、マーク、ID を組み立てる。候補行が空なら引数形状と fixture 指定を保って `Metafunc.parametrize(..., [])` を呼ぶ。それ以外は隠す ID 部分を除いた結合 ID を使う。全因子の ID 部分を隠す行には `pytest.HIDDEN_PARAM` を渡し、最終的な ID の一意化は pytest に任せる。全因子の `indirect` を引数名に展開し、共通の `scope` と共に一度の `Metafunc.parametrize` で登録する。 [pytest 8.4 の ID の処理](https://docs.pytest.org/en/8.4.x/_modules/_pytest/python.html) · [現行の Metafunc API](https://docs.pytest.org/en/stable/reference/reference.html#pytest.Metafunc.parametrize)
- [ ] pytest 8.4 系と9系の範囲をそれぞれ `pytest>=8.4,<9` と `pytest>=9,<10` で指定し、新規 venv の Python に `uv pip install --python <venvのPython> -e . <pytestの範囲>` で入れる。各 venv で `python -m pytest -q tests/test_plugin.py tests/test_native.py` が成功したらコミットする。

### Task 4: ファズテストと Quint の試行

**Files:** Create `fuzz/{Cargo.toml,Cargo.lock,.gitignore,fuzz_targets/coverage.rs}`, `formal/quint/{pruning.qnt,README.md}`, `docs/development/guides/verification.md`. Task 1 の `formal/coverage_oracle.rs` を再利用する。

**Interfaces:** ファズ入力は因子数1〜5、水準数1〜3、次数と禁止規則に変換し、同じ `generate` に渡す。Quint モデルは参考として同じ形の禁止規則と部分割当てを使う。

- [ ] `fuzz_targets/coverage.rs` を作る。ルートとは別に Cargo ロックを管理し、`formal/coverage_oracle.rs` をテストから読む。`cargo +nightly fuzz run coverage -- -runs=1000` で、生成行の合法性、完全な n 因子網羅、無解の一致を確認する。失敗した入力は通常の Rust テストで再現できる具体値に変換する。
- [ ] `pruning.qnt` に、二値3因子、禁止条件 `A=0, B=0`、部分割当てを枝刈りする遷移を記述する。`SoundPrune` は、捨てた部分割当てに対応する有効な完全ケースが空であることを総当たりで判定する。
- [ ] `quint verify formal/quint/pruning.qnt --backend=tlc --main Pruning --invariants SoundPrune` が違反なしで完了し、同じコマンドの `--main PruningMutant` が「禁止規則の一部だけが一致したら捨てる」版の反例を出すことを確認する。たとえば `A=0` は `B=1` で完成できる。 [Quint CLI の検証オプション](https://quint.sh/docs/quint#command-verify)
- [ ] 反例のモデル入力から Rust の公開関数を呼ぶ回帰テストを組み立て、既存の網羅照合でその誤りを検出できるか記録する。ITF が必要な場合は、同じ不変条件を Apalache の `--out-itf` で検査する。結果、有限モデルの範囲、Rust の照合との役割分担を記録してコミットする。常設の ITF・MBT を追加する判断は試行結果に委ねる。

### Task 5: CI、wheel、利用と開発の手順

**Files:** Modify `README.md`, `pyproject.toml`. Create `prek.toml`, `mkdocs.yml`, `docs/index.md`, `docs/user/guides/quickstart.md`, `docs/user/reference/markers.md`, `tools/wheel_smoke.py`, `infra/README.md`, `.github/workflows/{ci.yml,non-linux-ci.yml,release.yml}`.

**Interfaces:** `python tools/wheel_smoke.py WHEEL_PATH` は指定の wheel を新規環境に入れ、外部の作業ディレクトリで pytest を呼び、プラグインの自動読み込みと収集・実行を確認する。

- [ ] wheel のスモークテストに二値3因子の利用例を置く。成功件数に加え、実行された行のペア集合が全12組であることを確認する。自動読み込みが無効な構成でスモークが失敗することを確かめ、通常構成で成功させる。
- [ ] `uv run` で Rust の検査と pytest の統合テストを再現できる手順を用意する。CI では CPython 3.11、3.12、3.13、3.14、3.15 と pytest 8.4 系・9 系を組み合わせて確認する。Linux、macOS、Windows で `maturin build --release --locked` から生成した wheel のスモークテストを走らせる。Linux の配布 wheel は manylinux 2.28 のビルド環境で作り、生成物の manylinux タグを確認する。hoimin の対応する検査・配布ワークフローに沿って責務を分け、配布用ビルドは成果物を保存する。
- [ ] 利用者向け文書に、インストール、基本例、`order=3` と `exclude`、通常の `parametrize` との混在、空の候補と収集エラーを掲載する。開発者向け文書に、網羅照合、ファズテスト、Quint の試行、wheel の確認手順を載せる。
- [ ] `cargo fmt --all --check`、`cargo clippy --workspace --all-targets --locked -- -D warnings`、`cargo test --workspace --locked`、`uv run --locked pytest -q`、対象環境での wheel スモークテストを実行する。公開する契約と実装の対応、pytest 固有の表現が Rust コアに入っていないこと、直積の中間表がないことをレビューし、検証結果を記録してコミットする。
