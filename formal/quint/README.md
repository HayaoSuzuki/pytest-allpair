# 枝刈りの有限モデル

二値の因子 A、B、C に対し、A と B が両方 0 の行を除外する。部分割当ての未確定値は `-1` で表す。`SoundPrune` は、捨てた割当てがどの有効な完全ケースにも延長できないことを、合法な行の列挙で確認する。

Quint 0.33.1 と Java 21 で実行する。

```sh
quint typecheck formal/quint/pruning.qnt
quint verify formal/quint/pruning.qnt --backend=tlc --main Pruning --invariants SoundPrune
quint verify formal/quint/pruning.qnt --backend=tlc --main PruningMutant --invariants SoundPrune
```

`Pruning` は 27 の到達可能状態を検査して違反がなかった。`PruningMutant` は A または B のどちらか一方が 0 の時点で枝を捨てる。`B=0, C=0` の部分割当てを捨てた反例が得られた。この割当ては `A=1` で合法な行にできる。

同じ性質の違反を ITF に書き出すには、Apalache を使う。コマンドは違反を報告して終了する。

```sh
quint verify formal/quint/pruning.qnt --backend=apalache --main PruningMutant \
    --invariants SoundPrune --max-steps=1 --out-itf=pruning-mutant.itf.json
```

Rust の `covers_feasible_pairs` は同じ因子と制約で公開関数を呼び、合法な行から得られる 11 組のペアを照合する。隔離したコピーで Rust の枝刈りを「全項に一致」から「一部でも一致」に変えると、網羅集合の差でこのテストが失敗した。通常の回帰検証にはこの公開関数のテストを使い、ITF はモデルの反例を調査するときに生成する。

TLC の結果は、この有限モデルで記述した枝刈りの条件に対するものである。任意の因子数や Rust の探索全体は、網羅の照合器とファズテストで検証する。
