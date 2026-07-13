# Contributing

新しい知見は原則として GitHub Issue に保存し、再利用する数値や図だけをリポジトリに追加します。

## 新しい実験Issueの最低要件

1. 一文の主張と evidence status
2. 入力・出力・比較した action / arm
3. model、checkpoint、upstream commit、license
4. dataset、split、base sequence数、反復測定の軸
5. camera convention、scale / gauge、alignment
6. metricと「高い方が良いか」
7. refusal / crash / missing output の扱い
8. 強いcontrol、失敗例、撤回事項
9. raw artifact、集計script、figure生成scriptへの参照
10. 次に結論を変えうる make-or-break 実験

`.github/ISSUE_TEMPLATE/experiment-report.yml` を使うと、この項目が自動的に並びます。

## 図とデータ

- 論文図のスクリーンショットより、手元の数値から再生成した図を優先します。
- CSV / JSON に provenance と analysis unit を残します。
- checkpoint、dataset本体、上流ライセンスに抵触するassetはcommitしません。
- repeated measures を独立サンプル数として数えません。
- 無効になった結論は削除せず `retracted` と理由を追記します。
