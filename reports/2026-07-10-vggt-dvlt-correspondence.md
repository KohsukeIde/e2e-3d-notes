# VGGTのbundle adjustment改善を分解する：対応点診断と反復計算のstress test

- Snapshot: 2026-07-10
- Evidence: local-reproduction + local-experiment
- Status: 監査後の訂正版
- Reproducibility: Déjà ViewはB，VGGT対応点診断はC寄りのB

## 要約

[VGGT](https://arxiv.org/abs/2503.11651)は，複数画像からカメラ姿勢，奥行き，3D点を一回のnetwork inferenceで推定する．同論文では，この出力へbundle adjustmentを加えると，RealEstate10Kのカメラ姿勢スコアが85.3から93.5へ改善する．しかし，この差だけからは，初期カメラ姿勢，最適化へ渡す画像間measurement，solverのどれが改善を生んだか分からない．

本実験では，入力画像，VGGTの初期推定，bundle-adjustment solverを固定し，measurementを作る経路だけを三種類へ交換した．さらに，外部solverを使わず同じblockを反復する[Déjà View](https://arxiv.org/abs/2605.30215)について，一つの公開checkpointを学習範囲外の反復回数まで評価した．

得られた知見は，次の範囲に限定される．

1. stress条件では，VGGT単体の初期姿勢スコア中央値が0.933である一方，bundle-adjustment経路の拒否率は外部トラッカーで57.5%，VGGT自身のtrackで87.5%であった．前者は系列単位，後者は試行単位なので同一系列での共起は証明できないが，stress集合全体の失敗を「初期姿勢が一様に悪い」ことだけでは説明しにくい．
2. 三つの処理を事後に比較できた24系列では，最良処理による改善が全系列で正であった．最良処理は21系列で正解情報から作ったmeasurementへの交換，3系列で既存measurementを固定した最適化であった．これは実用手法の性能ではなく，complete caseにおける事後的な改善上限である．
3. Déjà Viewの一つのcheckpointをETH3D 13系列で評価すると，16回から24回のaggregate metricは同程度であったが，64回では奥行き誤差が16回の約17.2倍となり，姿勢スコアは0.954から0.021へ低下した．このcheckpointでは，学習範囲の少し外側だけを見て長い反復の安全性を判断できない．
4. 探索的な学習型refinerでは，trackを変えると出力が変わる性質を学習できても，姿勢精度は改善しなかった．入力への感度と，幾何目的を改善する更新は別の条件である．ただし，この結果を再集計する定量artifactは本repositoryにないため，設計上のnegative resultとして扱う．

![二つの診断実験の設計](../figures/experiment_design.png)

*図1．上段では入力画像，VGGT推定，solverを固定し，measurementの作り方を交換する．下段では同じDéjà View checkpointに適用する反復回数だけを変える．上段はmeasurement経路全体の寄与を調べる実験であり，対応の正しさだけを単独で変える実験ではない．数値入力を持たない概念図で，[図生成script](../scripts/make_figures.py)から`make figures`で生成する．*

## 1．背景

### 1.1 VGGTの出力と論文上の未解決点

従来のmulti-view 3D reconstructionは，画像特徴の検出，画像間matching，カメラ姿勢推定，3D点のtriangulation，bundle adjustmentを順番に実行する．VGGTは，同じ場面を撮影した複数画像を一度networkへ入力し，各画像のcamera intrinsics，camera extrinsics，depth map，point map，point trackをまとめて出力する．ここでfeed-forwardとは，sceneごとの反復最適化を行わず，一回のnetwork evaluationで結果を出すことを指す．

**Evidence: paper.** VGGT論文は，一回の推論だけでも高い精度を示す一方，推定結果をbundle adjustmentで調整するとさらに改善すると報告した．カメラ姿勢推定のAUC@30は，RealEstate10Kで85.3から93.5，CO3Dv2で88.2から91.8へ上昇する．論文はVGGTのcameraとdepthがbundle adjustmentの良い初期値になると説明している．

この結果は「bundle adjustmentを追加すればよい」という設計指針には直結しない．一つのbundle-adjustment runには，初期カメラ姿勢と3D点，複数画像で同じ3D点を表すmeasurement，それらを調整するsolverが同時に入るからである．論文表の前後差は，この三要素の寄与を分離していない．

### 1.2 Bundle adjustmentが前提とするmeasurement

Bundle adjustmentは，複数画像で同じ3D点を写している画素の組を観測として受け取り，3D点を各カメラへ投影した位置と観測画素のずれを小さくする．調整対象は主にカメラ姿勢と3D点である．

入力された画素の組が正しければ，カメラ姿勢や3D点のずれを修正できる．一方，別の物体を同一点として結ぶ誤対応が多い，観測点が少ない，画像間の接続が偏る，という場合には，solverは誤った観測を満たす解を探すか，品質検査で処理を中止する．反復回数を増やすだけでは，measurementの内容や被覆は変わらない．

本レポートでは，solverへ渡す対応点，その可視性，点数，画像間の接続をまとめてmeasurementと呼ぶ．正解投影から作るmeasurementは誤対応を除くだけでなく，点数や空間被覆も変え得る．したがって，今回の交換実験が識別するのはmeasurement構築経路全体の寄与であり，「対応の正しさ」だけの純粋な効果ではない．

## 2．研究質問と対立仮説

### 2.1 VGGTのbundle-adjustment経路は何に制限されるか

四つの説明を区別する．

**初期姿勢が制限要因であるという説明．** VGGTの初期カメラ姿勢が正解から遠いため，solverの収束域へ入らない．この説明だけでstress条件の失敗が生じるなら，初期姿勢スコアも低いはずである．今回測ったのは姿勢であり，初期depthや3D点の品質までは含まない．

**現在のsolverが固定measurement上の誤差を残すという説明．** Learned measurementを固定したまま現在のbundle adjustmentを実行することで，元のVGGT出力より改善できる．今回比較するのは「最適化しない」場合と「現在のsolverを使う」場合であり，solverの種類，反復上限，dampingを振る強度比較ではない．

**measurement構築が制限要因であるという説明．** 同じ初期値と同じsolverでも，measurementの構築経路を変えると到達する姿勢精度または拒否率が変わる．正解投影から作るmeasurementが大きな上限を示す場合，現在のtracker経路に未回収余地がある．ただし，正解measurementは対応精度と同時に点数や被覆も変えるため，どの性質が原因かは追加実験を要する．

**場面ごとに最良処理が異なるという説明．** 元の推定を返す，learned measurementを固定して最適化する，measurementを交換して最適化する，という事後的な最良処理が系列間で異なる．これは選択問題の存在を示唆するが，実際の選択器を学習または評価したことにはならない．

### 2.2 学習型の反復を学習範囲外で増やすとどうなるか

Déjà Viewは，同じTransformer blockを繰り返して3D推定を更新する．**Evidence: paper.** 論文は反復回数を推論時の計算量調整に使い，公開checkpointを8回から16回の反復で学習している．本実験の問いは，この一つのcheckpointに限り，16回近傍の挙動からさらに長い反復の挙動を予測できるか，というものである．Déjà View一般または学習型反復一般の収束性を検証する実験ではない．

## 3．実験設計

### 3.1 measurement構築経路の交換

入力画像，VGGT-1Bのfeed-forward出力，bundle-adjustment実装，品質判定，姿勢metricを固定し，solverへ渡すmeasurementの作り方を交換した．

- **強い外部トラッカー．** VGGT公式のbundle-adjustment経路と同じ系統であり，ALIKEDとSuperPointからquery pointを作り，fine trackingを行う．
- **VGGT自身のtrack．** VGGTが内部featureから直接出力するpoint trackである．
- **正解投影から作るmeasurement．** 正解カメラ姿勢と正解奥行きから3D点を別viewへ投影する．実用的なtrackerではなく，正解情報を使える場合の診断上限である．

最適化しないVGGT出力を基準とした．また，正解measurementと正解初期値を組み合わせ，現在のsolverが正解付近で動作することを確認した．一方，三経路のquery位置，点数，track長，空間被覆を一致させていない．したがって，これはmeasurement構築経路のcontrolled swapであり，match correctnessだけのcontrolled swapではない．

### 3.2 データと解析単位

解析対象は29のbase sequenceである．

| 条件 | Dataset | Base sequences | 目的 |
|---|---|---:|---|
| 標準条件 | CO3D，Replica | 12 + 3 | object-centricと屋内sceneにおける差の測定 |
| stress条件 | ETH3D，TartanAir | 13 + 1 | wide baseline，実画像，弱textureを含む失敗の測定 |

標準条件とstress条件はdatasetに基づく区分であり，結果から選別した区分ではない．robust kernel，初期値の微小摂動，入力画像10枚と30枚の違いは，同じbase sequence内の反復測定である．これらを独立したscene数へ加えていない．

すべての比較に必要な出力が揃った系列は24であった．この24系列の事後上限と，29系列全体における運用性能は別の量である．拒否時に元のVGGT出力へ戻す全29系列のutilityは，保存artifactから再構築できず，本レポートでは未報告である．

### 3.3 VGGT側の実行設定

| 項目 | 設定 |
|---|---|
| Model | `facebook/VGGT-1B` |
| 画像解像度 | 読み込み時最大辺1024 px，model入力518 px |
| Track query | 最大4096点，8 query frames，visibility threshold 0.2 |
| Camera | OpenCV world-to-camera，PINHOLE，intrinsics固定 |
| Robust loss | soft-L1，scale 4 px |
| Observation gate | 初期再投影誤差12 px以下，track length 2以上，1 frameあたり16 inliers以上 |
| Solver | 最大80 iterations，function・gradient・parameter toleranceは各1e-10 |
| Pose metric | pairwise relative rotation / translation AUC@30 |

Pose AUC@30は，画像対ごとの相対回転誤差と相対並進方向誤差を0度から30度までthresholdingし，正解率曲線の面積を取る．値域は0から1で，高いほどよい．世界座標の回転，並進，scaleに依存しないため，multi-view reconstructionのgauge ambiguityを避けられる．

最適化前に必要な観測数を満たさない場合，または最適化後のrobust reprojection errorが基準を超える場合，その出力を採用せず拒否とした．拒否はsolverの数値発散だけでなく，観測不足や品質検査による中止を含む．

### 3.4 Déjà View側の実行設定

公開された117M parameterの`nvidia/dvlt` checkpointと公式evaluation stackを用いた．Python 3.12，PyTorch 2.5.1，CUDA 12.4の環境で，ETH3D 13系列を同じ順序，同じ入力のまま評価した．反復回数は8，12，16，20，24，32，48，64である．

17回以上では，同じblockをより細かいtime partitionで適用する．「学習時の17段目以降を実行する」という意味ではない．反復ごとの状態を読むhookはtensorを変更せず，16回反復の固定batchでhookの有無による出力差が0であることを確認した．

## 4．結果

### 問1．stress条件の拒否は，初期姿勢の低さだけで説明できるか

**Evidence: local-experiment.** stress条件におけるVGGT単体のPose AUC@30中央値は，base sequence単位で0.933であった．同じstress条件で，外部トラッカーを使うbundle-adjustment経路は57.5%，VGGT自身のtrackを使う経路は87.5%の試行を拒否した．

この二つは解析単位が異なる．保存済み縮約dataには系列と各試行を結ぶ表がないため，「同じ系列で高い初期姿勢と拒否が共起した」とは主張できない．言えるのは，stress集合の初期姿勢中央値が高い一方で運用上の拒否が多く，集合全体の失敗を初期姿勢の低さだけへ還元する説明とは整合しにくい，という範囲である．拒否にはmeasurement不足と品質検査も含まれるため，「誤対応だけが原因」とも断定できない．

![標準条件の姿勢差とstress条件の拒否率](../figures/correspondence_diagnostics.png)

*図2．左は標準条件で正解measurementからlearned measurementを引いたPose AUC@30の系列中央値であり，高いほど未回収差が大きい．右はstress条件の試行単位拒否率であり，高いほど悪い．二つのpanelは解析単位が異なり，同一系列での共起を表さない．入力は[VGGT縮約集計](../data/t36_sequence_summary.json)，SHA-256は`eb86b3845c19115e46331079fa70e4eba193fcba6db77a47c03a3a0aa3b9c0f4`である．左は外部トラッカー14系列，VGGT自身のtrack 15系列のpaired差を系列間で中央値集計した．右は設定違いを含む試行率で，分子と分母は縮約artifactに残っていない．`make figures`で生成する．*

### 問2．標準条件では，measurement構築経路による差が残るか

**Evidence: local-experiment.** 正解measurementと外部トラッカーのPose AUC@30差は14系列中13系列で正であり，中央値は0.0244であった．VGGT自身のtrackとの差は15系列すべてで正であり，中央値は0.0325であった．

利用可能な系列で観測された中央値は，外部トラッカーの方がVGGT自身のtrackより小さかった．ただし標本は14系列と15系列で一致せず，同一系列だけを使ったtracker間のpaired順位ではない．差は0.02から0.03程度であり，標準条件だけから大きな実用性能の上限を主張する結果でもない．正解measurementは点数と被覆も異なり得るため，この差をmatch correctnessだけへ帰属させることもできない．

### 問3．三処理を事後に選べる場合，complete caseの改善上限はどれだけか

**Evidence: local-experiment.** 比較可能な各系列について，元の推定を返す，既存measurementを固定して最適化する，正解measurementへ交換して最適化する，という三処理からPose AUC@30が最も高いものを事後に選んだ．

| 区分 | 系列数 | 事後最良値の改善中央値 | 改善系列 | 最良処理の件数 |
|---|---:|---:|---:|---|
| All | 24 | +0.051 | 24/24 | 正解measurement 21，固定measurementの最適化 3，元の推定 0 |
| 標準条件 | 15 | +0.051 | 15/15 | 正解measurement 14，固定measurementの最適化 1，元の推定 0 |
| stress条件 | 9 | +0.049 | 9/9 | 正解measurement 7，固定measurementの最適化 2，元の推定 0 |

![三処理を事後選択したcomplete-case上限](../figures/oracle_action_ceiling.png)

*図3．左は，各系列で三処理の最良値を選んだ後，元のVGGT出力からの改善を系列間で中央値集計した値であり，高いほど診断上のheadroomが大きい．右は各処理が最良となった系列数である．入力は[VGGT縮約集計](../data/t36_sequence_summary.json)，SHA-256は`eb86b3845c19115e46331079fa70e4eba193fcba6db77a47c03a3a0aa3b9c0f4`である．必要な出力が揃う24系列だけを含み，missingまたはrefusalへのfallbackは含まない．`make figures`で生成する．*

正解measurementへの交換が21系列で最良だったため，現在の初期値とsolverを固定した条件では，measurement経路を変える余地が多くの系列にある．ただし，21/24は勝った系列数であり，総利得の何割がmeasurement由来かを表さない．また，これは正解情報を使った事後選択であり，現実のtrackerや選択器の性能ではない．

### 問4．一つのDéjà View checkpointへ学習範囲外の反復を加えるとどうなるか

**Evidence: local-reproduction.** ETH3D 13系列に対する公式evaluation stackのaggregate metricは次の通りである．統計的不確実性を比較していないため，16回から24回の小差を有意な改善とは扱わない．

| 反復回数 | Pose AUC@30 ↑ | Depth AbsRel ↓ | Depth Delta1 ↑ |
|---:|---:|---:|---:|
| 8 | 0.865 | 0.0325 | 0.986 |
| 12 | 0.940 | 0.0206 | 0.997 |
| 16 | 0.954 | 0.0182 | 0.997 |
| 20 | 0.957 | 0.0180 | 0.997 |
| 24 | 0.956 | 0.0184 | 0.997 |
| 32 | 0.938 | 0.0231 | 0.996 |
| 48 | 0.786 | 0.0529 | 0.980 |
| 64 | 0.021 | 0.3126 | 0.484 |

![Déjà Viewの反復回数stress test](../figures/dvlt_k_sweep.png)

*図4．同じ公開checkpointとETH3D 13系列に対し，適用回数だけを変えたaggregate metricである．姿勢は高いほど，奥行き誤差は低いほどよい．青い領域は学習範囲の8回から16回，赤い線の32回は16回基準を初めて下回った評価点である．64回では姿勢が0.021，奥行き誤差が0.313となった．入力は[公式評価の全集計](../data/raw/dvlt_r1_r2_r3_summary.json)，SHA-256は`55dbfeecf4c61aae37a4787f1dfc83b42a272023e4460eac3d3d8d4677ff039f`，および[図用の縮約値](../data/dvlt_k_sweep.csv)，SHA-256は`c589ed886f012cde4b8f342ba20c5b57b87e6e80b53bde24ea5f92caeae35940`である．各回数で同じ13系列を使い，missingは記録されていない．`make figures`で生成する．*

16回から24回ではaggregate metricが同程度であり，学習上限を少し超えただけでは破綻を検出しにくい．32回以降は16回基準を下回り，64回ではDepth AbsRelが16回の約17.2倍となった．この観測は，このcheckpoint，ETH3D 13系列，8回から64回という有限範囲に限られる．反復モデル一般の発散，または無限時間の発散を示すものではない．

補助診断では，学習範囲内の隣接更新の84.1%でhidden-state normが非減少であったが，全更新が単調増加するsceneは0%であった．また，768 channels中567 channelsが「学習範囲内の最大値を超え，範囲外後半で増加傾向を持つ」という有限長の診断基準を満たした．この基準は収束証明でも発散証明でもなく，探索的なproxyである．

## 5．探索的なnegative result：学習型refiner

### 5.1 背景と仮説

正解measurementは実運用で使えないため，VGGTの初期推定とtrackから姿勢補正を予測する小さなnetworkを試した．仮説は，「refinerがtrackを因果的に利用し，正しいtrackと壊れたtrackを区別できれば，measurement経路の失敗を姿勢改善へ変換できる」というものであった．

### 5.2 三つの試行

最初のrefinerは，trackを消す，または入れ替えるcontrolでも出力がほとんど変わらず，実質的にVGGTのgeometry priorだけを使っていた．ETH3Dでは，すでに良い初期姿勢を悪化させた．

次に，改善が期待できない場合は何も変更しないgateを加えた．悪化は抑えられたが，training dataに同じsceneの正しいtrackと壊したtrackのpairがなく，track差を学ぶlossが機能しなかった．

最後に，正しいtrackと意図的に壊したtrackのpairをtrainingへ加えた．Trackを変えると出力も変わる性質は得られたが，教師とした姿勢更新は投影Jacobianから導いたGauss-Newton stepではなく，平均残差から作ったheuristicであった．姿勢精度は改善しなかった．

**Evidence: local-experiment. Scope: exploratory，artifact不完全．** この結果は，trackへの感度が幾何改善を保証しないという反例である．一方，定量値，解析単位，checkpointを再集計するartifactが本repositoryにないため，特定の幾何solverが必要だと結論する根拠にはならない．投影Jacobianから更新を計算するhybrid設計は，次に検証する仮説である．

## 6．何が非自明か

### 6.1 集合レベルでは，初期姿勢とmeasurement経路を別々に測る必要がある

自然な予想は，feed-forward modelの初期姿勢が高い集合ほどbundle adjustmentも適用しやすい，というものである．今回，stress集合では系列単位の初期姿勢中央値0.933と，試行単位の高い拒否率が別々に観測された．解析単位が異なり系列ごとの対応もないため，初期姿勢から拒否を予測できるかは未検証である．現段階では，二つの指標を別々に報告すべきことを示唆する結果と解釈する．

### 6.2 同じ初期値とsolverでも，measurement経路が変わると上限が変わる

三処理のcomplete-case上限では，24系列すべてに正の改善があり，21系列で正解measurementを使う処理が最良となった．これは「solverを増やせばよい」という結論ではなく，現在のsolverを固定してもmeasurement構築経路に診断上の余地が残ることを示す．ただし，正解measurementは点数と被覆も変えるため，次に切り分けるべき対象は対応精度，観測数，空間被覆，画像間接続である．

### 6.3 学習範囲の近傍が安定でも，長い外挿の安全性は分からない

Déjà Viewでは16回から24回のaggregate metricが同程度であったため，短い外挿だけなら問題がないように見える．同じcheckpointは64回で大きく崩れた．非自明なのは，境界を一度超える試験だけではfailureを発見できなかった点である．反復回数を運用パラメータにするなら，想定最大値までのstress testまたは停止条件が必要である．この含意は今回のcheckpointに対するものであり，別checkpointや別modelへは未検証である．

### 6.4 入力への感度は，幾何目的の改善ではない

Counterfactualなtrack pairにより，trackを変えるとrefiner出力も変わる性質は得られた．それでも姿勢は改善しなかった．「入力を使っているか」と「再投影誤差を下げる更新か」は別々のcontrolを要する．

## 7．次の手法仮説

**Evidence: inference.** 次に検証する候補は，すべてのsceneへ同じrefinementを適用するnetworkではなく，measurementの健全性と予測改善量を使って処理を選ぶ系である．候補処理は，現在のfeed-forward推定を返す，既存measurementで幾何最適化する，measurementを再推定してから最適化する，の三つである．今回の事後上限は選択問題の可能性を示すだけで，このselectorの有効性を実証していない．

学習器には，measurementの信頼度，外れ値重み，damping，対応候補，処理ごとの改善見込みを予測させ，カメラ姿勢の更新は投影Jacobianに基づくGauss-NewtonまたはLevenberg-Marquardtで計算する構成を候補とする．これはnegative resultから導いた次の仮説であり，必要条件として確立したものではない．

決定的な次実験は二つである．第一に，同じquery位置，点数，track長，空間被覆を保ったまま対応だけを正解または破壊し，measurementのどの性質が差を生むか調べる．第二に，拒否時に元のVGGT出力へ戻す規則を含め，全29系列で処理選択後のutilityを評価する．

## 8．限界

- 初期値について測ったのはカメラ姿勢であり，depthと3D点を含む「初期3D推定全体」が良いとは言えない．
- 初期姿勢0.933は系列単位の中央値，57.5%と87.5%は設定違いを含む試行単位の拒否率である．系列と試行を結ぶraw tableがなく，同一系列での共起や拒否の集中を検証できない．
- 拒否には誤対応だけでなく，観測不足とhealth gateによる中止が含まれる．
- 正解measurementは対応の正しさだけでなく，query位置，点数，track長，空間被覆も変え得る．今回識別したのはmeasurement構築経路全体の差である．
- solverの種類，反復上限，dampingを振っていないため，より強いsolverで差が閉じるかは未検証である．
- 三処理の上限を比較できたのは29系列中24系列である．全29系列のfallback後utilityは未計算であり，24系列の結果はcomplete-caseの事後上限である．
- 事後最良処理の件数はselector性能ではなく，処理ごとの総利得比率でもない．
- 標準条件の小さなmeasurement gapは主にCO3Dが支える．datasetを跨ぐ普遍則とは言えない．
- π³とMapAnythingによるmulti-architecture診断は未完了である．現時点ではVGGT固有の観測か，feed-forward 3D model一般の性質かを区別できない．
- Déjà Viewの17回以上は学習範囲外であり，一つのcheckpointとETH3D 13系列に対する外挿耐性の結果である．学習型反復一般の収束性を示さない．
- 学習型refinerの定量artifactがなく，該当節は再現可能な主要結果ではなく探索記録である．

## 9．監査で撤回した主張

### 9.1 設定違いの実行を独立sampleとして数えた集計

**Evidence: retracted.** 初期集計は，robust kernel，初期値摂動，frame数の違いを別sampleとして数え，510実行を独立観測のように扱った．同じsceneの反復測定であり，独立性を満たさない．現在の系列単位の値は，sequence内で先に集約した後，sequence間で計算した値である．試行単位の拒否率は独立scene確率として扱わない．

### 9.2 学習型refinerの収束保証

**Evidence: retracted.** 初期のrefinerでは，monotone operatorに対する条件を確認し，収束保証があると報告した．しかし実装した更新は，その保証が適用されるsolverではなくplain fixed-point iterationであった．保証対象と実装が一致しないため，収束保証の主張を撤回した．

### 9.3 Trackerを区別しない拒否率

**Evidence: retracted.** 87.5%はVGGT自身のtrackに対する拒否率である．強い外部トラッカーでは57.5%であり，両者をlearned tracker一般の単一値として報告できない．

### 9.4 Refusalを除いたcomplete-case評価

**Evidence: retracted.** 最適化が成功したsceneだけで平均を取ると，処理しやすいsceneへ選択が偏る．24系列の結果は診断上限としてのみ残し，運用性能とは呼ばない．運用評価には，拒否時のfallbackを含む全29系列の集計が必要である．

## 10．再現性

```bash
pip install -r requirements.txt
make check
```

`make check`が検証するのは，保存済みJSON，縮約CSV，headline値，SHA-256，生成figureの相互整合性である．model inferenceやbundle adjustmentを再実行するcommandではない．

| 対象 | Grade | 現在検証できること | 欠けているもの |
|---|---|---|---|
| Déjà View反復実験 | B | 全集計JSONから表と図を再生成できる | exact upstream commit，checkpoint revision，config dump，実行command |
| VGGT対応点診断 | C寄りのB | 監査後の系列単位summaryから表と図を再生成できる | 一部raw JSON，系列と試行の対応表，exact revision，run manifest，実行command |

欠けた値を推測では補わない．次回はcheckpoint SHA，upstream commit，sequence一覧，frame sampling，solver backend，damping，health-gate閾値，GPU，seed，walltime，実行command，完全raw outputをrun manifestへ保存する必要がある．

## 11．一次資料

- [VGGT paper](https://arxiv.org/abs/2503.11651)
- [VGGT official code](https://github.com/facebookresearch/vggt)
- [Déjà View paper](https://arxiv.org/abs/2605.30215)
- [Déjà View official code](https://github.com/nv-tlabs/dvlt)
- [Déjà View checkpoint](https://huggingface.co/nvidia/dvlt)
- [π³ official code](https://github.com/yyfz/Pi3)
- [MapAnything official code](https://github.com/facebookresearch/map-anything)
