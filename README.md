# E2E 3D Notes

End-to-end / feed-forward multi-view 3D reconstructionについて，論文が作る期待，検証した仮説，再現実験，negative result，撤回事項を蓄積するrepositoryである．結論だけでなく，「なぜその実験を行ったか」「何を固定し，何を変えたか」「どの仮説が棄却されたか」を残す．

## Current report

- [Issue #1: VGGTのbundle adjustment改善を分解する](https://github.com/KohsukeIde/e2e-3d-notes/issues/1)
- [詳細レポート](reports/2026-07-10-vggt-dvlt-correspondence.md)
- [実験レポートの保存契約](docs/reporting_contract.md)

![Experiment design](figures/experiment_design.png)

VGGT論文は，一回のnetwork inferenceへbundle adjustmentを加えるとカメラ姿勢精度が上がると報告している．今回の実験は，入力画像，VGGTの初期値，solverを固定し，measurementを作る経路を交換した．必要な出力が揃う24系列では，三処理の事後最良値がすべて正であり，21系列で正解measurementを使う処理が最良となった．これは実用性能ではなくcomplete-caseの診断上限である．一方，一つのDéjà View checkpointを学習範囲外まで反復すると，64回で奥行き誤差が16回の約17.2倍となった．いずれも対象modelと保存artifactの範囲に限定した観測である．

## Evidence status

各claimには次のstatusを付ける．

| Status | 意味 |
|---|---|
| `paper` | 原論文または公式codeに明記された事実 |
| `local-reproduction` | 公開checkpointを再実行して得た結果 |
| `local-experiment` | 独自のcontrolled comparisonから得た結果 |
| `inference` | 観測結果から導いた解釈．追加検証が必要 |
| `retracted` | 後の監査で無効になった主張．理由とともに履歴を残す |

## Repository structure

```text
data/       図の入力値，縮約data，provenance
docs/       実験記録の契約
figures/    dataから再生成した図
issues/     GitHub Issue本文のsnapshot
reports/    長文の実験レポート
scripts/    図の再生成と数値整合性のcheck
```

## Reproduction check

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
make check
```

`make check`は，raw JSON，縮約CSV，headline値，SHA-256，生成figureの整合性を検査する．

## Themes to accumulate

- feed-forward 3D modelとclassical geometryの役割分担
- correspondence quality，camera initialization，solver failureの因果分解
- VGGT，π³，MapAnything，Déjà View，VGGT-Ωの再現と比較
- camera convention，scale，gauge，alignment，refusalを含む評価設計
- positive resultだけでなく，negative result，撤回，artifact gapの保存

Checkpoint，dataset，上流codeは再配布しない．各assetのlicenseは上流に従う．
