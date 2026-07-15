# E2E 3D Notes

End-to-end / feed-forward multi-view 3D reconstructionについて，論文から生じた疑問，手元の検証結果，うまくいかなかった試み，後から訂正した主張を蓄積するリポジトリである．結論だけでなく，「なぜ実験したか」「何を比較したか」「結果から何が言えて，何はまだ言えないか」を残す．

## 現在のレポート

- [Issue #1: VGGTの精度をさらに上げるには，何を改善すべきか](https://github.com/KohsukeIde/e2e-3d-notes/issues/1) / [実験レポート](reports/2026-07-10-vggt-dvlt-correspondence.md)
- [Issue #2: 座標ではなく「幾何を満たす関係式」を予測するfeed-forward 3Dは有利か](https://github.com/KohsukeIde/e2e-3d-notes/issues/2) / [仮説と実験計画](reports/2026-07-15-constraint-native-feed-forward-3d.md)
- [実験レポートの保存契約](docs/reporting_contract.md)

![Experiment design](figures/experiment_design.png)

VGGTの初期出力とbundle adjustmentを固定し，画像間の対応点だけを変えた．三種類の結果が揃った24系列では，正解対応点を使う処理が21系列で最良だった．これは実用手法ではなく，対応点を理想化した場合の上限である．また，一つのDéjà View公開モデルを学習範囲外まで反復すると，64回で奥行き誤差が16回時の約17.2倍になった．

![Constraint-output hypothesis](figures/constraint_output_hypothesis.png)

次の研究候補として，camera，depth，pointmapを直接出す代わりに，局所的な幾何関係だけを予測し，cameraと観測3Dを一つのnullspaceから復元する仮説を記録した．これは実験結果ではない．座標から同じ関係式を作る強い比較対象が同等以上なら棄却する，という条件を先に固定している．

## 根拠の区分

検索と監査のため，各記録には次のラベルを付ける．本文中へ繰り返し挿入せず，冒頭または末尾の根拠一覧に置く．

| ラベル | 意味 |
|---|---|
| `paper` | 原論文または公式コードに明記された事実 |
| `local-reproduction` | 公開モデルを再実行して得た結果 |
| `local-experiment` | 条件を管理した手元の比較から得た結果 |
| `inference` | 観測結果から導いた解釈．追加検証が必要 |
| `retracted` | 後の監査で無効になった主張．理由とともに履歴を残す |

## リポジトリの構成

```text
data/       図の入力値，集計データ，出所
docs/       実験記録の契約
figures/    保存データから再生成した図
issues/     GitHub Issue本文の保存版
reports/    長文の実験レポート
scripts/    図の再生成と数値整合性の検査
```

## 数値と図の整合性検査

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
make check
```

`make check`は，保存データ，本文で使う集計値，生成した図の整合性を検査する．

## 今後蓄積するテーマ

- feed-forward 3Dと幾何最適化の役割分担
- 対応点の質，初期カメラ姿勢，最適化失敗の切り分け
- VGGT，π³，MapAnything，Déjà View，VGGT-Ωの再現と比較
- camera convention，scale，gauge，alignment，失敗時の扱いを含む評価設計
- 良い結果だけでなく，うまくいかなかった試行，撤回事項，欠けた再現情報の保存

学習済みモデル，データセット，上流コードは再配布しない．各データのライセンスは配布元に従う．
