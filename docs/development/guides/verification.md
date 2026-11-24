# 網羅の検証

Rust の生成器は各因子の候補数、次数、除外規則を受け取り、選んだ候補の番号を返す。小さなモデルでは、完全ケースを総当たりして有効な行を求め、そこに含まれる n 因子の組を生成結果と比較できる。`formal/coverage_oracle.rs` は、生成器の探索や枝刈りを共有せずに期待結果を計算する。

## プロパティテストとランダムなテスト順

Rust の proptest は、因子数・水準・次数・除外規則を変えながら網羅集合を照合する。意味の等しい除外規則を並べ替えた場合も、生成行と順序が一致することを検査する。Python の Hypothesis は、同じ因子に複数の引数を持つモデルを生成し、pytest が収集したケースと、値の比較から求めた合法なケースを照合する。

```sh
cargo test --workspace --locked
PROPTEST_CASES=1024 PROPTEST_RNG_SEED=812 cargo test --locked -p pytest-allpair-core --test coverage_properties
uv run --locked pytest --hypothesis-show-statistics
```

CI では pytest-randomly がテスト順を変え、Rust は固定した nightly でもシャッフルを実行する。失敗時はログに出たシードで再現できる。Rust のシードはテストバイナリごとに表示される。

```sh
uv run --locked pytest --randomly-seed=812
cargo +nightly-2026-11-23 test --workspace --locked -- -Z unstable-options --shuffle
cargo +nightly-2026-11-23 test --locked -p pytest-allpair-core --test coverage_properties -- -Z unstable-options --shuffle-seed 812
```

## カバレッジに基づくファズテスト

最大5因子、各因子は最大3水準のモデルを対象に、libFuzzer が探索した入力を総当たり結果と照合する。`fuzz/` の Cargo ロックは独立して管理する。PR の CI は1,000回実行する。定期実行は60秒、手動実行は30・60・300秒から選べる。CI は発見したコーパスを再利用し、ログと失敗入力を成果物として保存する。

```sh
cargo install cargo-fuzz --version 0.13.2 --locked
cargo +nightly-2026-11-23 fuzz run coverage -- -runs=1000 -seed=812
```

[Quint と TLC の試行](https://github.com/HayaoSuzuki/pytest-allpair/blob/main/formal/quint/README.md)では、三つの二値因子に対して枝刈りの条件を検査する。モデルで得た反例は Rust の回帰例に対応付ける。テストで使う照合器とプラグインの実行には Java や Quint は不要である。
