# E2E 3D Notes

End-to-end / feed-forward multi-view 3D reconstruction の論文知識、再現実験、失敗、実装上の罠を、後から検証できる形で蓄積するリポジトリです。

対象読者は「2D computer vision / deep learning は分かるが、SfM・BA・3Dの座標系には詳しくない」研究者です。各記録では、結論だけでなく、モデル・checkpoint・データ・座標系・評価単位・失敗時の扱いまで残します。

## 最初に読むもの

- [Issue #1: VGGT / Déjà View実験で分かったこと](https://github.com/KohsukeIde/e2e-3d-notes/issues/1)
- [今回の詳細レポート](reports/2026-07-10-vggt-dvlt-correspondence.md)
- [CV研究者向け E2E 3D 入門](docs/e2e_3d_primer.md)
- [実験レポートの保存契約](docs/reporting_contract.md)

## 現時点の一文要約

VGGT後段の失敗は「最適化をもう少し回せば直る」という単純な solver 問題ではない。難しい系列では feed-forward pose がすでに良くても correspondence graph が壊れており、完全な対応点を仮定した oracle では 24/24 系列で改善し、最良 action は 21/24 で **REPAIR** だった。一方、Déjà View の反復回数 `K` は学習範囲外で安全な anytime knob ではなく、K=64 で深度 AbsRel が K=16 の約17倍、Pose AUC@30 が 0.954 から 0.021 に崩れた。

## Evidence status

Issueとレポートでは、主張を次の状態で区別します。

| status | 意味 |
|---|---|
| `paper` | 原論文・公式コードに明記された事実 |
| `local-reproduction` | 公開checkpointをこちらで再実行して得た結果 |
| `local-experiment` | 独自の比較実験・診断から得た結果 |
| `inference` | 観測結果からの解釈。追加検証が必要 |
| `retracted` | 後の監査で無効になった主張。削除せず理由を残す |

## リポジトリ構成

```text
data/       図の入力値、縮約データ、provenance
docs/       入門、用語、保存契約
figures/    データから再生成した図
issues/     GitHub Issue本文のスナップショット
reports/    長文の実験レポート
scripts/    図の再生成・整合性チェック
```

## 図の再生成

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
make check
```

`make check` は、DVLTの縮約CSVと元summary JSONの一致、今回の主要数値、図ファイルの生成を検査します。

## 今後ここで回すテーマ

- feed-forward 3D model と classical geometry の境界
- correspondence / track quality と pose・depth error の因果分解
- VGGT、π³、MapAnything、Déjà View、VGGT-Ωなどの再現・比較
- camera convention、scale/gauge、alignment、refusalを含む評価設計
- positive resultだけでなく、negative result・撤回・再現不能箇所

checkpointや上流コードは再配布しません。各資産のライセンスは上流に従ってください。
