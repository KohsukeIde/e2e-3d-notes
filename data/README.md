# Data provenance

## `raw/dvlt_r1_r2_r3_summary.json`

T36のABCI実行から保存された `r1_r2_r3_summary.json` のコピーです。全13 ETH3D sequenceのmetricと、R1/R2/R3集計を含みます。checkpointやdataset画像は含みません。

元のworkspace path:

```text
_theme_exploration/projects/ongoing/T36_convergent_geometry/
  outputs/dvlt_repro_abci/r1_r2_r3_summary.json
```

注意: 実行時に作る設計だった `config_dump.json` は縮約review bundleに残っておらず、exact upstream commit / checkpoint revisionをこのrepositoryから回収できません。値を推測せず、artifact gapとして残しています。

## `dvlt_k_sweep.csv`

上のJSONから、図に必要な3 metricだけを抽出したものです。`scripts/make_figures.py` がJSONとの一致を検査します。

## `t36_sequence_summary.json`

外部review後の訂正版 `SEQ_REANALYSIS_RESULT.md` を構造化した縮約データです。元のsequence-level集計scriptは `outputs/d2/surface/*.json` を必要としますが、そのraw surface群はlocal review bundleに含まれません。このため、数値のprovenanceは明示できる一方、このrepository単体での再集計はできません。

## データを読むときの単位

- DVLT K-sweep: ETH3D 13 base sequences、同じsequence集合を各Kで評価
- VGGT diagnostic: 29 base sequences
- kernel / jitter / frame count: within-sequence repeated measures
- hard refusal 57.5% / 87.5%: attempt-level operational statistic
- oracle action ceiling: action候補が揃う24 base sequences

`SHA256SUMS` は、このsnapshotで図とheadlineの根拠にしたraw / reduced dataの固定用です。
