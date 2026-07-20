# [Experiment] 同じsensor noiseを繰り返すと，VGGTは高confidenceのままcamera・depth・3D点・track間で矛盾するか

> 状態：結果あり．TartanAirの4画像系列，公式VGGT-1B，48回のforwardで検証した．仮説は支持されなかった．

## このIssueで調べたこと

[VGGT](https://arxiv.org/abs/2503.11651)は，複数画像からcamera，depth，3D point map，画像間のtrack，visibility，confidenceを一回のforwardで出力する．通常はcamera誤差，depth誤差，track誤差を別々に評価するが，それぞれが良い値でも，すべてが同じ3D sceneを表しているとは限らない．

例えば，基準画像上の一点が別画像のどこへ移るかは，次の三経路から求められる．

1. 基準画像のdepthで3D点へ戻し，予測cameraで別画像へ投影する．
2. VGGTが直接出した3D点を，予測cameraで別画像へ投影する．
3. VGGTのtrack headが，別画像上の位置を直接予測する．

三つが同じ3Dを表すなら，移動先も近くなるはずである．本Issueでは，二つの3D経路が示す位置を結ぶ線分から，track headの予測が何pixel外れたかを「追跡headだけに残る追加ずれ」とする．二つの3D経路自身がずれている場合，その間のどちらをtrackが選んでもtrackだけの誤りとは数えないためである．confidenceはこの距離の計算にも，評価点の選択にも使わない．

![実験設計と三経路の比較](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/vggt_noise_experiment_design.png?raw=1)

*図1．上段は入力条件，下段は同じ点について比較する三つの予測位置である．同じ撮影位置と画像順序を保ったまま，各反復画像のnoise模様だけを変えた．*

中心的な問いは次である．

> 同じ撮影位置の反復画像が同じnoise模様を共有すると，VGGTはそれらを複数の独立な3D証拠として数え，track confidenceを高く保ったまま，camera・depth・3D点・trackの相互矛盾を増やすか．

## 仮説

自然な仮説は，同じ撮影装置に由来する相関したartifactが，独立な観測のように数えられるというものである．この場合，同じnoise模様を反復する条件では，毎回異なるnoise模様を使う条件よりもconfidenceが維持または増加する一方，追跡headだけに残る追加ずれが増えるはずである．

別の説明もある．VGGTが小さなnoise模様を証拠として使わなければ条件差は生じない．また，条件差が出ても，通常のtrack誤差やdepth誤差と同時に変わるだけなら，新しい出力間矛盾ではなく，単純な精度変化である．

## 何を固定し，何を変えたか

TartanAir Easyから，Gascola 2系列とHospital 2系列の計4画像系列を用いた．各入力は12枚である．撮影位置の構成を二種類用意した．

| 撮影位置の構成 | 12枚の内訳 |
|---|---|
| 2位置 | 2つの撮影位置を各6回使う |
| 4位置 | 4つの撮影位置を各3回使う |

各構成について，次の二条件を対応づけて比較した．

| noise条件 | 同じ撮影位置の反復画像 |
|---|---|
| 同じnoise | 一つのnoise模様をbyte-identicalに反復する |
| 異なるnoise | 反復ごとに異なる，同じ強度のnoise模様を使う |

noiseはsensor noiseを模したゼロ平均Gaussian RGB noiseであり，画素値0から255に対するRMSは3である．比較対の間では，元画像，camera poseの多重集合，12枚の順序，先頭の基準画像，noise強度，画像品質，前処理，48個の基準点，modelを固定した．対応する二条件の平均PSNR差は最大0.003 dB未満だった．

各条件を3種類のnoise seedで実行した．4画像系列×2撮影位置構成×2 noise条件×3 seedで，合計48回のVGGT forwardである．方向の判定では，各画像系列内で3 seedの中央値を取った．独立単位は4画像系列であり，48回を48独立sceneとは数えない．

## 事前に決めた判定

仮説を支持するには，次の三条件をすべて要求した．

1. 2撮影位置と4撮影位置の両方で，同じnoise条件の追加ずれが4系列中3系列以上で増える．
2. 両方の撮影位置構成で，track confidenceが4系列中3系列以上で維持または増加する．
3. 通常のtrack誤差，camera誤差，depth誤差，3D点誤差，二つの3D出力間のずれ，欠損率が同程度の比較でも，追加ずれだけが系列内のばらつきを明確に超える．

この条件を満たさない場合，同じnoise模様が作る「高confidenceだが一つの3Dとして矛盾した状態」という仮説は支持しない．

## 結果

### Q1．追加ずれの測り方は，本当に特定の出力だけの破損を検出できたか

**A．検出できた．既知答えを持つ51条件はすべて想定どおりに判定された．**

一つの3Dから解析的に作った出力，camera・depth・3D点だけを壊した出力，trackだけを壊した出力，visibilityだけを壊した出力，異なるsceneの出力を混ぜた条件，confidenceだけを交換した条件，必須出力が欠けた条件を含む．confidenceだけを交換したとき，主指標配列の最大変化は数値上0.0だった．

実際の48出力でも，trackを二つの解析的位置のどちらかへ置き換えると追加ずれは最大0.0 pxとなった．trackへ既知のoffsetを加えたcontrolでは，最小でも32.7 pxとして検出された．以下の否定結果は，評価器がtrackのずれを測れないためではない．

### Q2．同じnoise模様を反復すると，高confidenceのまま追加ずれが増えたか

**A．一貫して増えなかった．追加ずれが増えたのは，どちらの撮影位置構成でも4系列中2系列だった．**

| 撮影位置の構成 | 追加ずれが増えた系列 | confidenceが維持または増加した系列 | 事前条件 |
|---|---:|---:|---|
| 2位置を各6回 | 2 / 4 | 4 / 4 | 不合格 |
| 4位置を各3回 | 2 / 4 | 3 / 4 | 不合格 |

![同じnoise模様を反復した条件差](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/vggt_noise_acquisition_effects.png?raw=1)

*図2．0より上は，同じnoise模様を反復した方が値が大きいことを表す．各点は一つの画像系列における3 seedの中央値，ひげは3 seedの範囲である．追加ずれの符号は系列間で揃わなかった．*

2位置条件における追加ずれの差は，Gascola 1から順に+0.068，−0.225，−0.051，+0.045 pxだった．4位置条件では+0.542，+0.449，−0.038，−0.148 pxだった．特定の環境だけで符号が決まったわけでもなく，事前に要求した3 / 4系列へ届かなかった．

confidenceは維持または増加することが多かったが，追加ずれが同時に増えるとは限らなかった．したがって，confidenceが変わらないことだけを，同じ取得artifactを独立証拠として数えた根拠にはできない．

### Q3．追跡先の画像で見えない点が，この否定結果を作った可能性はないか

**A．その可能性だけでは説明できなかった．正解上で見えている点だけに限定しても，追加ずれが増えたのは両構成で4系列中2系列だった．**

主解析は，modelのvisibility予測で都合のよい点を選ばないように，正のdepthへ投影できる点をすべて数えた．しかし，投影先が追跡先画像の外にある点や，別の表面に遮られた点は，通常のtrackとして観測できない．そこで事後監査として，TartanAirの正解cameraとdepthから追跡先画像で可視と判定された点だけを再集計した．

2位置条件における可視点だけの差は+0.034，−0.050，−0.046，+0.028 px，4位置条件では−0.057，+0.047，+0.006，−0.073 pxだった．対象を可視点へ変えると個々の符号は一部変わったが，仮説の方向が揃わないという結論は変わらなかった．

この監査では別の注意点も分かった．4撮影位置と2撮影位置の追加ずれを，正のdepthを持つ全点で比べると，系列中央値で2.4から23.3 pxの差があった．正解上の可視点だけでは0.15から0.30 pxだった．複数出力の整合性を評価するとき，追跡先画像で実際に観測可能な点を定義しないと，視野外点が結果の尺度を大きく変える．

### Q4．追加ずれは，通常のtrack誤差とは別の現象だったか

**A．別の現象とは言えなかった．通常指標から分離できた比較は24組中0組だった．**

![通常の追跡誤差への還元監査](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/vggt_noise_ordinary_error_audit.png?raw=1)

*図3．横軸は通常のground-truth track誤差の条件差，縦軸は追加ずれの条件差である．両軸とも同じnoise条件から異なるnoise条件を引いた値であり，各点は一つの画像系列を表す．追加ずれの変化は，通常誤差が変わらない状態で一貫して現れなかった．*

各比較で，camera center，camera rotation，scaleを合わせたdepth，直接予測された3D点，ground-truth track，二つの3D出力間のずれ，invalid率も測った．これらがすべて系列内のnoise seedによるばらつき以内にありながら，追加ずれだけが自身のばらつきの5倍を超えることを分離条件としたが，該当する比較はなかった．

撮影位置を2つから4つへ増やす比較では，可視点の追加ずれが4系列の全6比較で増えた．ただし通常のtrack誤差も全6比較で増え，confidenceは全6比較で低下した．撮影位置と各位置の反復回数を同時に変えた比較でもあるため，これは通常の入力難化と分離できない事後観察である．

### Q5．実際の出力間のずれは，画像上でどのように見えるか

**A．正解位置と三つの予測位置がすべて画像内にある場合でも，二つの3D経路だけが正解とtrack headから離れる局所例は存在した．**

> **訂正（2026-07-21）**：初版の図4では，正解位置だけが画像内にあり，二つの3D経路の投影位置は画像上端の外側にあった．また，8.6 pxを元画像座標の距離と記したが，正しくはモデル入力座標の距離だった．以下では四位置がすべて画像内にある例へ差し替え，モデル入力座標と元画像座標を区別した．この訂正は集計結果と仮説の判定には影響しない．

![VGGTの三経路が示す位置の定性的な実例](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/vggt_noise_qualitative.png?raw=1)

*図4．正解上で可視であり，正解位置と三つの予測位置が左右端から画像幅の5%以上，上下端から画像高の5%以上離れている12,186組から，追加ずれが最大の例を選んだ．左の白枠を右で拡大する．黒線はdepth＋cameraと直接3D点が示す範囲，赤破線はそこからtrack headまでの追加ずれである．この例では二つの3D経路は元画像上で3.0 px離れ，track headはその範囲から9.0 px離れた一方，正解位置との距離は1.0 pxだった．評価時の518 × 392座標では，追加ずれは7.3 pxである．四位置はすべて画像内である．この一例は出力間の局所的なずれを示すが，noise条件の因果効果を示すものではない．*

## 何がnon-trivialだったか

1. **confidenceが維持されても，出力間矛盾が同じ方向に増えるとは限らなかった．** 取得artifactを共有する反復画像という操作は，confidenceと3D整合性の逆転を作る十分条件ではなかった．
2. **視野外点を含めるかで，見かけの効果量が一桁以上変わった．** 出力値だけで閉じた整合性評価は一見model非依存であるが，その点が追跡先画像で観測可能かという外部の条件を持たないと，追跡として意味のない点と画像の組が支配し得る．
3. **可視点に残った撮影位置構成の差は，通常誤差と一緒に動いた．** 局所的な出力間のずれは実在するが，今回の操作では通常のtracking degradationと独立なfailure modeにはならなかった．

## ここから生じるresearch question

単純なnoise相関では複数headのworld解釈を分岐させられなかった．次の問いは，より直接的に入力画像が作る幾何的な支持関係を操作するものである．

> 画像集合を変えたとき，VGGTのcamera，depth，3D点，trackは同じworldへ一緒に更新されるのか，それとも出力ごとに異なるworldへ遷移する条件があるか．

最小実験では，4つの撮影位置を常に含めたまま，12枠の反復配分を`3-3-3-3`，`6-2-2-2`，`9-1-1-1`へ変える．評価する基準点と追跡先画像の組，および正解可視領域は，全条件に共通する部分へ固定する．これにより，撮影範囲を変えずに重複証拠の集中度だけを操作できる．同時に，同じ通常track誤差を持つ条件を対応づけ，どの出力だけが別の更新をしたかを測る必要がある．

## この結果からは言えないこと

- TartanAirの4画像系列と一つのVGGT-1B checkpointだけであり，実画像や別architectureへ一般化できない．
- 加法Gaussian RGB noiseは，実cameraのshot noise，read noise，demosaicing，ISPを再現しない．
- 基準画像上の48点を使った評価であり，denseな全表面の整合性ではない．
- 一つの局所例で，track headが二つの3D経路の範囲から元画像上で9.0 pxずれたことから，VGGT全体が一つの3Dを持たないとは言えない．
- 4撮影位置と2撮影位置の事後比較は，撮影位置identityと各位置の反復回数を同時に変える．単一の原因を断定できない．
- どの入力画像が矛盾を支えたかを調べる局在化実験は，主仮説が事前条件を満たさなかったため実行していない．

<details>
<summary>実行設定と公開データ</summary>

### Model

- Model：公式`facebook/VGGT-1B`
- 実行：各条件につき一回のforward
- 学習・finetuning：なし
- filtering・optimization・後処理：なし
- 計算：CUDA，bfloat16 autocast

### 入力

- Dataset：TartanAir Easy
- 画像系列：`gascola/P003`，`gascola/P005`，`hospital/P000`，`hospital/P003`
- 元画像：640 × 480 px
- Model入力：crop mode，518 × 392 px
- 画像枚数：12枚
- 基準点：先頭画像上の8列×6行，計48点
- Noise：ゼロ平均Gaussian RGB，clipping前RMS 3 / 255
- Experiment seed：17，29，43
- Forward数：48，成功48，失敗0

### 評価

- Camera convention：OpenCV world-to-camera
- 主指標：モデルへ入力した518 × 392座標における，track headの予測から，depth＋cameraと直接3D点が示す二位置を結ぶ閉線分までのpixel距離
- 主解析の対象：基準画像以外の11 frameで，二つの3D経路とtrackを有限に計算でき，両3D経路のdepthが正である点と画像の組
- 可視点監査：TartanAirの正解cameraとdepthから，追跡先画像内かつ遮蔽されていないと判定した点と画像の組
- 集計単位：4画像系列．3 seedは各系列内で中央値を取る

### 公開データ

- [対応づけた全24比較，control，visibility監査，事後比較](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/data/one_world_vggt.json)
- [qualitative例の縮小画像と四つの位置](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/data/one_world_vggt_qualitative.npz)
- [図生成script](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/scripts/make_figures.py)

Qualitative図にはTartanAir画像を512 × 384 pxへ縮小して用いた．元画像，depth，model checkpointは再配布していない．

</details>

## 事実と解釈の区分

- **論文に書かれていること**：VGGTが複数画像からcamera，depth，point map，track，visibility，confidenceをfeed-forwardで出力する構成である．
- **今回新しく測ったこと**：TartanAir 4画像系列における48条件，三経路の追加ずれ，通常指標との比較，正解可視点だけの事後監査である．
- **結果からの解釈**：同じGaussian noise模様の反復は，confidenceと出力間整合性を逆転させる十分条件ではないこと，今後の整合性評価では観測可能な点と画像の組を明示すべきだという部分である．

## 一次資料

- [VGGT paper](https://arxiv.org/abs/2503.11651) / [official code](https://github.com/facebookresearch/vggt)
- [TartanAir dataset](https://theairlab.org/tartanair-dataset/)
