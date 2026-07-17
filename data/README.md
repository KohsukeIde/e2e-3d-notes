# 保存データの出所

## `raw/dvlt_r1_r2_r3_summary.json`

T36のABCI実行から保存された全集計JSONの複製である．ETH3D 13系列の評価指標と，反復中の内部状態に関する集計を含む．公開モデルやデータセットの画像は含まない．

元の保存場所:

```text
_theme_exploration/projects/ongoing/T36_convergent_geometry/
  outputs/dvlt_repro_abci/r1_r2_r3_summary.json
```

注意: 実行時に残す予定だった完全な設定記録がなく，使用した上流コードと公開モデルの版をこのリポジトリから確認できない．値を推測せず，欠けた再現情報として残す．

## `dvlt_k_sweep.csv`

上のJSONから，図に必要な三つの評価指標だけを抽出したデータである．図生成スクリプトがJSONとの一致を検査する．

## `t36_sequence_summary.json`

監査後の訂正版を構造化した集計データである．元の系列単位の集計スクリプトが必要とする一部の実行結果は，保存データに含まれない．このため数値の出所は示せるが，リポジトリ単体での再集計はできない．

## `set_relative_filter_geometry.json`

RobustVGGTの公開scoreを使い，TartanAirの4画像系列で入力集合の構成を変えた比較の集計である．各系列について，別environmentを写した別scene画像4枚を含む条件と，その4枚を同じsceneの近傍画像へ置換した条件を保存する．共通する正しい画像の保持判定，同一forwardのscoreを再正規化した反実仮想，基準側から見えず，基準側と遠方側の両方に重なる画像から見える表面の3D completenessを含む．

## `iterative_filter_cascade.json`

上の8入力条件へ同じ公開filterを固定点まで反復適用したcharacterizationの集計である．各roundの入力枚数，新規に棄却された画像の役割，固定点で残った画像の役割を保存する．RobustVGGTの公開pipelineはfilterを一回だけ適用するため，これは公開手法の通常実行結果ではなく，scoreをview validityとして再利用できるかを調べた追加実験である．

## `distractor_subset_law.json`

4画像系列の各々について，4枠を別scene画像または同じsceneの近傍画像へ置き換えた全16組合せ，合計64回のVGGT推論を集計したデータである．遠方側の正しい2画像が保持された組合せ，同じ枚数でのscoreの幅，各別scene画像候補を追加した効果を含む．また，各推論の内部表現を固定したまま，別scene画像をscoreの尺度決めからだけ除いた反実仮想も含む．

## `shared_output_projectivity.json`

同じ正しい8画像だけを入力した条件，同一入力の再実行，別scene画像4枚を追加した条件，同じsceneの近傍画像4枚を追加した条件を，TartanAirの4画像系列で比較した集計である．基準画像と大きく重なる5画像だけでglobal Sim(3)を合わせた後の，共通camera，depth，point mapの変位と，ground truthに対する共通point map誤差を含む．4条件×4画像系列の16推論である．

## `qualitative_forest2.json` / `qualitative_forest2.npz`

森林2の代表例について，実際の入力画像と画像除外の結果，および同じ遠方画像のpoint map変位を図示するためのpacketである．JSONには画像ごとのscore，保持・除外判定，point map変位の集計を保存する．NPZには12枚×2条件の縮小画像，共通する遠方画像，別scene画像または同じsceneの近傍画像を追加したときのpoint map変位を保存する．元解像度のTartanAir画像，depth，model checkpointは含まない．

## データを読むときの単位

- Déjà View反復実験: ETH3D 13系列．同じ系列集合を各反復回数で評価する．
- VGGT対応点診断: 29系列．
- 誤差関数，初期値の摂動，画像枚数の変更: 同じ系列内の反復測定であり，独立標本として数えない．
- 視点差が大きい画像でbundle adjustmentの結果を採用できなかった割合57.5% / 87.5%: 個々の試行を単位とする値である．分子，分母，系列と試行の対応表は保存データに残っていない．系列単位の初期姿勢中央値との関係は検証できない．
- 正解対応点による改善上限: 必要な処理結果が揃う24系列．
- Set-relative filter比較: TartanAir 4画像系列．同じ系列に対する2入力条件はpaired comparisonであり，8独立系列とは数えない．
- Filter反復: 上と同じ4画像系列に対する8 chain．独立単位は4画像系列であり，round数やchain数を独立標本とは数えない．
- 別scene画像の部分集合: 上と同じ4画像系列に対する各16組合せ．64回の推論や組合せを独立標本とは数えず，画像系列ごとの応答曲線として扱う．
- 共通3D出力のprojectivity: 上と同じ4画像系列に対する各4条件．16回の推論を独立標本とは数えず，画像系列ごとの対応づけた比較として扱う．
