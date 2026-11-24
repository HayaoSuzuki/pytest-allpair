# GitHub の設定

現行の [HayaoSuzuki/hoimin](https://github.com/HayaoSuzuki/hoimin/rules) に合わせ、[pytest-allpair のルールセット](https://github.com/HayaoSuzuki/pytest-allpair/rules)を適用済み。

| 対象 | 保護 |
| --- | --- |
| 既定ブランチ `main` | 削除と force push を禁止 |
| `pytest-allpair-release-state` | 削除と force push を禁止 |
| `v*` タグ | 既存タグの更新と削除を禁止 |

ルールセットのバイパス対象は空とする。`main` の必須 CI チェックは空で、CI は `CI result` を報告する。マージ後のブランチ自動削除、PR ブランチの更新、Discussions を有効にし、Wiki と Projects を無効にする。

`Wheel builds` ワークフローは成果物として wheel を保存する。将来、リリース状態を Git に記録する場合は `pytest-allpair-release-state` を使う。
