# マークの仕様

## pairwise_parametrize

`pytest.mark.pairwise_parametrize(argnames, argvalues, *, ids=None, indirect=False, scope=None)` は一つの因子を宣言します。クラスやモジュールにも置けます。複数の引数をまとめた因子では、候補行全体を一つの水準として扱います。同じ値を持つ候補行も位置で区別します。

候補の `pytest.param` に付いたマークと ID は、生成行に引き継がれます。`ids` は列または関数を指定できます。`pytest.HIDDEN_PARAM` を使った候補は、生成行の ID からその部分を省きます。`indirect` を指定すると、対応する fixture は `request.param` で候補値を受け取ります。`scope` を明示する場合は網羅対象の全因子に同じ値を指定します。

通常のマークと fixture のパラメータ化は網羅で生成された行と直積を取ります。同じ引数を網羅対象と通常の `parametrize` または `fixture(params=...)` の両方から指定すると収集エラーになります。

## pairwise

`pytest.mark.pairwise(*, order=..., exclude=...)` は一つのテスト関数に一つ指定できます。省略時の次数は因子数と2の小さい方です。`order=1` は有効な各水準、`order="max"` はすべての有効な完全ケースを生成します。数値の次数は1から因子数までです。

`exclude` には辞書の列を渡します。一つの辞書で指定した値がすべて一致すればそのケースを除外します。複数の辞書のいずれかに一致すれば除外の対象になります。等値比較には通常の Python の規則を使います。

網羅の対象は、有効な完全ケースの少なくとも一つに含まれる n 因子の組です。`-k` や `-m` による選択は、その後の pytest の実行範囲を決めます。生成時に候補リストが空なら pytest の `empty_parameter_set_mark` に従います。全因子に候補があるものの制約を満たすケースがゼロなら、収集時にエラーを報告します。
