# Data provenance

## `raw/dvlt_r1_r2_r3_summary.json`

T36のABCI実行から保存された全集計JSONのcopyである．全13 ETH3D sequenceのmetricと，反復状態の診断集計を含む．checkpointやdataset画像は含まない．

元のworkspace path:

```text
_theme_exploration/projects/ongoing/T36_convergent_geometry/
  outputs/dvlt_repro_abci/r1_r2_r3_summary.json
```

注意: 実行時に作る設計だったconfig dumpは保存snapshotに残っておらず，exact upstream commitとcheckpoint revisionをこのrepositoryから回収できない．値を推測せず，artifact gapとして残す．

## `dvlt_k_sweep.csv`

上のJSONから，figureに必要な3 metricだけを抽出したdataである．Figure scriptがJSONとの一致を検査する．

## `t36_sequence_summary.json`

監査後の訂正版を構造化した縮約dataである．元のsequence-level集計scriptが必要とする一部raw JSONは保存snapshotに含まれない．このため数値のprovenanceは明示できるが，repository単体での再集計はできない．

## データを読むときの単位

- Déjà View反復実験: ETH3D 13 base sequences．同じsequence集合を各反復回数で評価する．
- VGGT対応点診断: 29 base sequences．
- robust kernel，初期値の摂動，frame数の変更: 同じsequence内の反復測定であり，独立標本として数えない．
- stress条件の拒否率57.5% / 87.5%: 個々の試行を単位とする運用上の統計である．分子，分母，系列と試行の対応表は縮約artifactに残っていない．系列単位の初期姿勢中央値との共起は検証できない．
- 完全対応点による改善上限: 必要な処理結果が揃う24 base sequences．

`SHA256SUMS`は，このsnapshotでfigureとheadlineの根拠にしたraw / reduced dataを固定する．
