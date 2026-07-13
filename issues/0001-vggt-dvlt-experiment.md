# [Experiment] VGGTのbundle adjustment改善を分解する：対応点診断と反復計算のstress test

> - Snapshot: 2026-07-10 / 監査後の訂正版
> - Evidence: `local-reproduction` + `local-experiment`
> - Reproducibility: Déjà ViewはB，VGGT対応点診断はC寄りのB
> - Status: 観測結果は有効．正解情報を使わないmeasurement修復は未実装

## 1．背景と研究の問い

VGGTは，同じ場面を撮影した複数画像を一度networkへ通し，各画像のカメラ姿勢，奥行き，3D点を推定するモデルである．**Evidence: paper.** [VGGT論文](https://arxiv.org/abs/2503.11651)は，この一回の推論へbundle adjustmentを加えると，RealEstate10Kのカメラ姿勢スコアが85.3から93.5へ，CO3Dv2では88.2から91.8へ上がると報告している．

Bundle adjustmentは，複数画像で同じ3D点を写した画素の組をmeasurementとして受け取り，それらの再投影誤差が小さくなるようにカメラ姿勢と3D点を調整する．処理には，少なくとも次の三要素が必要である．

1. VGGTが出力した初期カメラ姿勢と3D点
2. どの画素同士が同じ3D点かを表すmeasurement
3. measurementを固定してカメラ姿勢と3D点を調整するsolver

したがって，論文の改善量だけから「何を直せばさらに改善するか」は決まらない．本実験では，次の説明を区別する．

- **初期姿勢が制限要因である．** VGGTの初期カメラ姿勢がsolverの収束域から遠い．
- **現在のsolverが固定measurement上の誤差を残す．** Learned measurementを変えなくても，現在のbundle adjustmentを行えば改善する．
- **measurement構築が制限要因である．** 同じ初期値と同じsolverでも，measurementを作る経路を変えると到達結果が変わる．
- **場面ごとに最良処理が異なる．** 元の推定を返す，既存measurementで最適化する，measurementを交換して最適化する，という選択問題が生じる．

別の方向として，外部solverを使わずに反復をmodel内へ組み込んだDéjà Viewを調べる．問いは，一つの公開checkpointに対し，学習範囲の少し外側の挙動から，さらに長い反復の安全性を判断できるか，である．

![Experiment design](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/experiment_design.png?raw=1)

*図1．上段では入力画像，VGGT推定，solverを固定し，measurementの作り方を交換する．下段では同じDéjà View checkpointに適用する反復回数だけを変える．上段はmeasurement経路全体の寄与を調べる実験であり，対応の正しさだけを単独で変える実験ではない．数値入力を持たない概念図で，[図生成script](../blob/main/scripts/make_figures.py)から`make figures`で生成する．*

## 2．実験は何を変え，何を固定したか

### 2.1 VGGTのmeasurement診断

VGGT-1Bが出力したカメラ姿勢と奥行きを共通の初期値とし，同じbundle-adjustment実装へ次の三種類のmeasurementを与えた．

- VGGT公式のbundle-adjustment経路が用いる強い外部トラッカー
- VGGT自身が出力するpoint track
- 正解カメラと正解奥行きから投影したmeasurement

最後の経路は実用手法ではない．正解情報を使える場合の診断上限である．Query位置，点数，track長，空間被覆は三経路で一致させていないため，この比較はmeasurement構築経路全体の交換である．誤対応率だけの効果とは解釈しない．正解measurementと正解初期値を組み合わせ，現在のsolverが正解付近で動くことも確認した．

評価対象は29のbase sequenceである．CO3D 12系列とReplica 3系列を標準条件，ETH3D 13系列とTartanAir 1系列をwide-baseline中心のstress条件として集計した．Robust lossの有無，初期値の微小摂動，10枚と30枚の入力は同一系列内の反復測定であり，独立したsampleには数えていない．

必要な観測数を満たさない，または最適化後の残差検査を通らない実行を「拒否」と数えた．拒否は数値発散だけでなく，measurement不足や品質検査による中止を含む．

### 2.2 Déjà Viewの反復stress test

[Déjà View](https://arxiv.org/abs/2605.30215)は，同じTransformer blockを繰り返し適用するモデルである．公開checkpointは8回から16回の反復で学習されている．ETH3Dの同じ13系列に対し，8，12，16，20，24，32，48，64回の反復を行った．

17回以上は学習範囲外であり，同じblockをより細かいtime partitionで適用する．「学習時の17段目以降を実行する」という意味ではない．状態を記録するhookは出力を変更しない読み取り専用とし，16回反復でhookの有無による出力差が0であることを確認した．

## 3．主要な設定

| 項目 | VGGT measurement診断 | Déjà View反復実験 |
|---|---|---|
| Checkpoint | `facebook/VGGT-1B` | `nvidia/dvlt`，117M parameters |
| 入力 | 最大辺1024 px，model入力518 px | 公式ETH3D評価入力 |
| Measurement | 最大4096点，8 query frames，visibility 0.2 | Model内部のdense prediction |
| 最適化 | intrinsics固定，soft-L1，最大80 iterations | 同一blockを8回から64回適用 |
| 幾何規約 | OpenCV，world-to-camera，PINHOLE | 公式実装 |
| 実行環境 | ABCI single GPU | Python 3.12，PyTorch 2.5.1，CUDA 12.4，ABCI single GPU |

VGGT側では，12 pxを超える初期再投影誤差を除外し，track length 2以上，1画像あたり16点以上を要求した．姿勢評価にはPose AUC@30を用いた．値域は0から1で，高いほどよい．Déjà Viewの奥行き評価には相対絶対誤差を用いた．こちらは低いほどよい．

## 4．結果

### 問1．stress条件の拒否は，初期姿勢の低さだけで説明できるか

**答え．Evidence: local-experiment.** stress条件におけるVGGT単体の姿勢スコア中央値は，base sequence単位で0.933であった．同じstress条件で，外部トラッカーを使う経路は57.5%，VGGT自身のtrackを使う経路は87.5%の試行を拒否した．

前者は系列単位，後者は試行単位であり，保存dataには両者を系列ごとに結ぶ表がない．したがって，同一系列での共起は証明できない．言えるのは，stress集合全体の失敗を「初期姿勢が一様に悪い」ことだけでは説明しにくく，初期姿勢とmeasurement経路の健全性を別々に測る必要がある，という範囲である．拒否には観測不足や品質検査も含まれるため，誤対応だけが原因とも断定しない．

![Correspondence diagnostics](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/correspondence_diagnostics.png?raw=1)

*図2．左は標準条件で正解measurementからlearned measurementを引いた姿勢スコアの系列中央値であり，高いほど未回収差が大きい．外部トラッカー14系列，VGGT自身のtrack 15系列について，各系列内の差を先に求め，系列間の中央値を取った．右はstress条件の試行単位拒否率であり，高いほど悪い．二つのpanelは解析単位が異なり，paired relationを表さない．入力は[VGGT縮約集計](../blob/main/data/t36_sequence_summary.json)，SHA-256は`eb86b3845c19115e46331079fa70e4eba193fcba6db77a47c03a3a0aa3b9c0f4`である．右panelの分子と分母は縮約artifactに残っていない．`make figures`で生成する．*

### 問2．標準条件では，measurement構築経路による差が残るか

**答え．Evidence: local-experiment.** 正解measurementと外部トラッカーの姿勢スコア差は14系列中13系列で正であり，中央値は0.0244であった．VGGT自身のtrackとの差は15系列すべてで正であり，中央値は0.0325であった．

利用可能な系列で観測された中央値は，外部トラッカーの方がVGGT自身のtrackより小さかった．ただし標本は14系列と15系列で一致せず，同一系列だけを使ったtracker間のpaired順位ではない．差は約0.02から0.03であり，標準条件だけから大きな実用上限を主張する結果でもない．また，正解measurementは点数と被覆も異なり得るため，差をmatch correctnessだけへ帰属させない．

### 問3．三処理を事後に選べる場合，complete caseの上限はどれだけか

**答え．Evidence: local-experiment.** 必要な出力が揃う24系列では，三処理の事後最良値が元のVGGT出力を全系列で上回った．改善中央値はPose AUC@30で0.051であった．最良処理は，21系列で正解measurementへの交換，3系列で既存measurementを固定した最適化であり，元の推定をそのまま返す処理は0系列であった．

![Complete-case intervention ceiling](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/oracle_action_ceiling.png?raw=1)

*図3．左は，各系列で三処理の最良値を選んだ後，元のVGGT出力との差を系列間で中央値集計した値であり，高いほど診断上の上限が大きい．右は各処理が最良となった系列数である．入力は[VGGT縮約集計](../blob/main/data/t36_sequence_summary.json)，SHA-256は`eb86b3845c19115e46331079fa70e4eba193fcba6db77a47c03a3a0aa3b9c0f4`である．必要な出力が揃う24系列だけを含み，missingと拒否時のfallbackは含まない．`make figures`で生成する．*

21/24は，正解measurementを使う処理が最良となった系列数である．measurementが総利得の何割を生んだかを表す数値ではない．正解情報と事後選択を使うため，現実のtrackerまたはselectorの性能でもない．

### 問4．一つのDéjà View checkpointへ長い反復を加えるとどうなるか

**答え．Evidence: local-reproduction.** 16回から24回のaggregate metricは同程度であり，統計的不確実性を評価していないため，小差を有意な改善とは扱わない．32回から16回基準を下回り，64回では姿勢スコアが0.954から0.021へ低下した．奥行きの相対絶対誤差は0.0182から0.3126へ増え，約17.2倍となった．

![Déjà View iteration sweep](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/dvlt_k_sweep.png?raw=1)

*図4．同じ公開checkpointとETH3D 13系列に対し，反復回数だけを変えた公式evaluation stackのaggregate metricである．姿勢は高いほど，奥行き誤差は低いほどよい．青い領域は学習範囲，赤い線の32回は16回基準を初めて下回った評価点である．入力は[公式評価の全集計](../blob/main/data/raw/dvlt_r1_r2_r3_summary.json)，SHA-256は`55dbfeecf4c61aae37a4787f1dfc83b42a272023e4460eac3d3d8d4677ff039f`，および[図用の縮約値](../blob/main/data/dvlt_k_sweep.csv)，SHA-256は`c589ed886f012cde4b8f342ba20c5b57b87e6e80b53bde24ea5f92caeae35940`である．各反復回数で同じ13系列を使い，missingは記録されていない．`make figures`で生成する．*

この結果は，一つのcheckpoint，ETH3D 13系列，8回から64回という有限範囲の観測である．Déjà View一般または学習型反復一般の発散を示さない．非自明なのは，学習上限を少し超えた20回から24回では破綻が見えず，それだけでは長い反復のfailureを発見できなかった点である．

## 5．探索的なnegative result：学習型refiner

正解measurementを使わずに姿勢を改善するため，VGGTの初期推定とtrackから姿勢補正を予測するrefinerを試した．仮説は，正しいtrackと壊れたtrackを区別できれば，measurement経路の失敗を姿勢改善へ変換できるというものであった．

最初のrefinerは，trackを消す，または入れ替えても出力がほとんど変わらず，ETH3Dの良い初期姿勢を悪化させた．何も変更しないgateを加えると悪化は減ったが，同じsceneの正しいtrackと壊したtrackのpairがなく，track差を学ぶlossが機能しなかった．Pairを加えるとtrackへの感度は得られたが，教師更新が投影Jacobianに基づかないheuristicであったため，姿勢精度は改善しなかった．

**Evidence: local-experiment. Scope: exploratory，artifact不完全．** これは「trackを使っていること」と「幾何目的を改善すること」が別の条件だというnegative resultである．ただし，この試行の定量値，解析単位，checkpointを再集計するartifactは本repositoryにない．投影Jacobianから更新を計算するhybrid設計は，結論ではなく次に検証する仮説である．

## 6．何が非自明か

第一に，stress集合では系列単位の初期姿勢中央値0.933と，試行単位の高い拒否率が別々に観測された．両者の系列対応がないため，初期姿勢からbundle adjustmentの適用可能性を予測できるかは未検証である．現段階では，二つの指標を集合レベルで別々に報告すべきことを示唆する．

第二に，同じ初期値と同じsolverを使っても，measurement構築経路を変えるとcomplete-case上限が変わった．24系列の事後最良値はすべて正で，21系列では正解measurementを使う処理が最良だった．次に調べるべきものはsolver反復だけではなく，対応精度，観測数，空間被覆，画像間接続のどれが差を作るかである．

第三に，反復modelの学習範囲を一度だけ超える試験では，長い外挿のfailureを見逃す．今回のDéjà View checkpointは20回から24回では16回と同程度だったが，64回で大きく崩れた．反復回数を運用時に変えるなら，想定最大値までのstress testまたは停止条件が必要である．この含意は今回のcheckpointに限定される．

第四に，入力trackへの感度を学習しても，幾何改善にはならなかった．入力依存性のcontrolと，再投影誤差を下げる更新のcontrolを分ける必要がある．

## 7．次の決定的な実験

1. 同じquery位置，点数，track長，空間被覆を保ったまま対応だけを正解または破壊し，measurementのどの性質が差を生むかを調べる．
2. 拒否時に元のVGGT出力へ戻す規則を含め，全29系列で処理選択後のutilityを評価する．

**Evidence: inference.** 設計候補は，学習器がmeasurementの信頼度，外れ値重み，damping，対応候補，処理ごとの改善見込みを予測し，姿勢更新を投影Jacobianに基づくGauss-NewtonまたはLevenberg-Marquardtで計算する構成である．これは未検証の次仮説であり，今回の実験が必要性を証明したものではない．

## 8．限界と撤回事項

- 初期値について測ったのはカメラ姿勢であり，depthと3D点を含む初期3D推定全体の品質ではない．
- 初期姿勢中央値と拒否率の解析単位が異なり，系列ごとの共起を確認できない．拒否率の分子と分母も縮約artifactに残っていない．
- 正解measurementは対応精度だけでなく点数と被覆も変えるため，どの性質が差を生んだかは未識別である．
- solverの種類，反復上限，dampingを振っておらず，より強いsolverとの比較ではない．
- 24系列の結果はcomplete-caseの事後上限である．全29系列のfallback後utilityと実用selectorは未評価である．
- π³とMapAnythingで同じ診断は完了していない．
- Déjà Viewの17回以上は学習範囲外であり，一つの公開checkpointの外挿耐性を測った結果である．
- 初期集計では設定違いの510実行を独立sampleとして扱っていた．これは誤りであり，現在はbase sequence内で先に集約している．
- 初期の学習型refinerには収束保証があると報告したが，保証条件を別のsolverへ誤適用していた．この主張は撤回済みである．
- 87.5%はVGGT自身のtrack，57.5%は外部トラッカーの拒否率であり，単一値として扱わない．
- 最適化に成功した系列だけの評価にはcomplete-case biasがある．運用性能を名乗るには拒否時のfallbackを含める必要がある．

## 9．再現artifact

```bash
pip install -r requirements.txt
make check
```

`make check`は，保存済みJSON，縮約CSV，headline値，SHA-256，figureの相互整合性を検証する．model inferenceやbundle adjustmentを再実行するcommandではない．

- [詳細レポート](../blob/main/reports/2026-07-10-vggt-dvlt-correspondence.md)
- [Déjà Viewの保存済み全集計](../blob/main/data/raw/dvlt_r1_r2_r3_summary.json)
- [VGGTの訂正版系列集計](../blob/main/data/t36_sequence_summary.json)
- [レポート保存契約](../blob/main/docs/reporting_contract.md)

Déjà View実行時のexact upstream commit，checkpoint revision，config dumpが残っていない．VGGT診断も，一部raw JSON，系列と試行の対応表，run manifestが残っていない．このためDéjà Viewは再現性grade B，VGGTはC寄りのBである．主要数値と図は再生成できるが，全実行をrawから再構築できない．

## 一次資料

- [VGGT paper](https://arxiv.org/abs/2503.11651) / [official code](https://github.com/facebookresearch/vggt)
- [Déjà View paper](https://arxiv.org/abs/2605.30215) / [official code](https://github.com/nv-tlabs/dvlt) / [checkpoint](https://huggingface.co/nvidia/dvlt)
- [π³ official code](https://github.com/yyfz/Pi3)
- [MapAnything official code](https://github.com/facebookresearch/map-anything)
