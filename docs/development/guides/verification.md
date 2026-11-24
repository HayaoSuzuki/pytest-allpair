# 網羅の検証

Rust の生成器は各因子の候補数、次数、除外規則を受け取り、選んだ候補の番号を返す。量の小さいモデルでは、完全ケースを総当たりして有効な行を求め、そこに含まれる n 因子の組を生成結果と比較できる。`formal/coverage_oracle.rs` はモデルから期待結果を計算し、生成器の探索や枝刈りを共有しない。

```sh
cargo test --locked -p pytest-allpair-core
cargo clippy --workspace --all-targets --locked -- -D warnings
uv run --locked pytest -q
```

ファズテストは最大5因子、各因子は最大3水準のモデルを生成し、除外が複数ある場合も同じ照合器で検査する。実行には Rust の nightly と cargo-fuzz が必要になる。

```sh
cargo +nightly fuzz run coverage -- -runs=1000
```

pytest の統合テストは、マークと ID の取り扱い、fixture への値の受け渡し、標準のパラメータ化との混在を、実際の pytest 収集と実行で確認する。pytest 8.4 系と 9 系は別の仮想環境に入れて検証する。

[Quint と TLC の試行](https://github.com/HayaoSuzuki/pytest-allpair/blob/main/formal/quint/README.md)では、三つの二値因子に対して枝刈りの条件を検査する。モデルで得た反例は Rust の回帰例に対応付ける。テストで使う照合器とプラグインの実行には Java や Quint は不要である。
