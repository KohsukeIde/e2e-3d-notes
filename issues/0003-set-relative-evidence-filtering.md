# [Experiment] RobustVGGTの画像除外判定は，残り4枚を変えるだけで同じ正しい画像に対して反転する

> 状態：結果あり．TartanAirの4画像系列で再現した．実画像と別architectureでは未検証である．

## このIssueで調べたこと

[VGGT](https://arxiv.org/abs/2503.11651)は，複数の入力画像を同時に処理し，各画像のcamera，depth，point mapを一回のforwardで推定する．入力に同じsceneへ属さない画像が混ざると，すべてを一つの3Dとして説明しようとして出力が崩れる可能性がある．

[RobustVGGT](https://arxiv.org/abs/2512.04012)は，最初のVGGT推論から各画像のscoreを計算し，scoreが0.4未満の画像を除外してから，残った画像だけでもう一度VGGTを実行する．scoreが高いほど，その画像は現在の入力集合と整合していると判定される．これは確率ではない．attentionとfeature similarityを入力集合内の最小値と最大値で0から1へ正規化して作る相対値である．

本Issueでは，このscoreが次の二つを区別できるかを調べた．

- **別scene画像**：異なる物理環境を写しており，同じ3Dへ統合できない画像である．除外すべき画像として使う．
- **遠方画像**：基準画像群と同じsceneを写す正しい画像だが，基準画像群との直接の表面overlapが3%以下である．基準側と遠方側の両方に重なる1枚を介して，scene全体へ接続する．保持すべき画像である．

中心的な問いは次である．

> 同じ正しい画像であれば，入力集合の残りを別scene画像から正しい画像へ置き換えても，同じように保持されるか．また，誤って除外された画像は3D再構成に本当に必要か．

## どのような入力を比較したか

TartanAirから森林2系列，病院2系列を選んだ．各入力は12枚であり，先頭の8枚は二条件で完全に同じである．

- 基準画像と大きく重なる正しい画像：5枚
- 基準側と遠方側の両方に重なる正しい画像：1枚
- 基準側とは直接ほとんど重ならない正しい遠方画像：2枚

残り4枚だけを次のように変えた．

| 入力条件 | 最後の4枚 | 本来の正しい判定 |
|---|---|---|
| A | 別environmentを写した別scene画像4枚 | 4枚を除外する |
| B | 同じsceneで基準側を追加観測する近傍画像4枚 | 4枚をすべて保持する |

総画像数，先頭の基準画像，共通する8枚，画像順序，前処理，model，score計算，除外thresholdは固定した．条件Bの追加画像は基準側とは30%以上重なるが，遠方側とのoverlapは最大5%以下である．したがって，遠方画像を直接支える新しい画像ではない．

![実際の入力画像と除外判定](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/filter_qualitative_example.png?raw=1)

*図1．森林系列の実例である．緑枠は保持，赤枠と×は除外を表す．上段では別sceneの病院画像4枚だけを正しく除外した．下段では12枚すべてが同じ森林sceneであるにもかかわらず，共通する遠方画像2枚を誤って除外した．*

## 結果

### Q1．別scene画像は正しく除外できたか

**A．できた．4画像系列すべてで，別scene画像を4枚中4枚除外し，共通する正しい8枚をすべて保持した．**

これはRobustVGGTが想定する通常の使い方に対するpositive controlである．公開されたTrevi／Notre-Dame例でも，手元のscore計算は公式scriptの除外結果と一致した．以下の現象は，除外処理そのものが動いていないためではない．

### Q2．同じ正しい8枚は，残り4枚を変えても同じように判定されたか

**A．判定されなかった．最後の4枚を同じsceneの正しい画像へ置き換えると，4画像系列すべてで同じ遠方画像2枚が保持から除外へ反転した．**

![同じ遠方画像に対する除外判定の反転](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/filter_score_comparison.png?raw=1)

*図2．4行は独立な画像系列である．白丸は共通する遠方2画像それぞれのscore，菱形はその平均，横線は2画像のscore範囲を示す．青と橙の違いは最後の4枚だけである．破線は除外thresholdの0.4であり，全系列で青の2画像は保持側，橙の同じ2画像は除外側にある．*

条件Aでは，遠方2画像の平均scoreは0.41から0.60であり，すべてthreshold 0.4以上だった．条件Bでは0.02から0.08まで低下し，すべてthreshold未満になった．正しい画像だけの入力にすれば誤除外が減るという自然な予想とは逆である．

### Q3．なぜ，同じ遠方画像のscoreが反転したのか

**A．入力集合ごとの正規化だけで反転を再現できた．**

別scene画像を含む最初のforwardで得たattentionとfeatureの値を固定し，別scene画像を最小値・最大値の計算からだけ外した．モデルを再実行していないため，内部表現は変わっていない．それでも4画像系列すべてで遠方2画像がthreshold未満になった．

別scene画像は非常に低い値を持つため，入力集合の下限を提供する．その結果，正しい遠方画像は0から1の中間へ押し上げられる．別scene画像を尺度決めから外すと，遠方画像自身が新しい最小値に近づく．今回の判定反転には，この相対的な尺度が必要だった．

基準画像を固定して他の画像順序だけを変えたcontrolでは，判定反転は起きなかった．一方，先頭の基準画像を変えると判定が変わった．したがって，一般的な順序noiseよりも，基準画像と入力集合の構成への依存が大きい．

### Q4．誤って除外された遠方画像は，3D再構成に必要だったか

**A．必要だった．条件Bでは，遠方側にしか見えない3D表面のcompletenessが4画像系列すべてで低下した．**

評価対象は，基準側の5画像からは見えず，基準側と遠方側の両方に重なる1枚から初めて見える表面である．予測とground truthの座標合わせには基準側の予測点だけを使い，評価する遠方側の点は使っていない．

条件Bのcompleteness低下は−25.5，−5.0，−8.3，−2.6ポイントであり，平均は−10.3ポイントだった．つまり，誤除外された2枚は単なる重複画像ではなく，それまで見えていなかった3D表面を運んでいた．

![画像除外による遠方側3D表面の変化](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/filter_geometry_change.png?raw=1)

*図3．横棒は，同じ12枚から画像を除外する前後で，遠方側にしか見えない正解の3D表面を再構成できた割合が何ポイント変わったかを示す．0より右は改善，左は悪化である．右の条件では4系列すべてが0より左にあり，正しい遠方画像の誤除外によって3D表面が失われた．*

条件Aで別scene画像を除いた効果は，2系列で改善，1系列で悪化，1系列でほぼ不変だった．この4系列だけから「別scene画像を除けば3Dが必ず改善する」とは言えない．

### Q5．一度除外した後の画像集合へ，同じ判定をもう一度使えるか

**A．使えなかった．8条件すべてで，二回目以降に新しい正しい画像が除外された．**

![全8条件における反復除外](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/iterative_filter_small_multiples.png?raw=1)

*図4．4行は独立な画像系列，2列は最後の4枚が異なる入力条件である．横軸は除外処理の適用回数，縦軸は残った画像枚数であり，各小図は一つの条件だけを示す．左列の青い区間では別scene画像だけを正しく除外したが，その後の赤い区間では正しい画像を除外した．右列は最初から12枚すべてが正しいため，赤い減少はすべて誤除外である．灰色は，もう一度処理しても画像集合が変わらなかったことを表す．*

5回から7回で判定が変わらなくなり，最終的に残ったのは12枚中2枚または3枚だった．これは画像を除くたびにscoreの最小値と最大値が変わり，次に低い正しい画像が新しい除外対象になるためである．

RobustVGGTの公式pipelineは，除外処理を一回だけ行う．したがって，図4は公式pipelineを通常どおり使うと12枚が2枚になるという結果ではない．公開scoreを画像固有のvalidityとして繰り返し利用できるかを調べた追加実験である．

### Q6．判定反転は，特定の極端な別scene画像1枚だけで起きたのか

**A．違った．別scene画像の枚数が主な要因だが，同じ枚数でも選んだ画像によって判定が変わった．**

最後の4枠を，別scene画像または同じsceneの近傍画像へ置き換えた全16組合せを，各画像系列で調べた．合計64 forwardであるが，独立単位は4画像系列である．

![別scene画像の枚数と遠方画像の保持率](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/distractor_count_curves.png?raw=1)

*図5．各小図は独立な画像系列である．横軸は最後の4枠に含めた別scene画像の枚数，縦軸はその枚数で可能な組合せのうち，正しい遠方2画像をともに保持した割合である．0%と100%の間にある点は，同じ枚数でも画像の選び方によって判定が変わったことを表す．*

別scene画像の枚数だけで，遠方2画像のscore変動を平均93.0%説明した．ただし，同じ枚数でも保持と除外が分かれたため，枚数だけの法則ではない．すべての組合せで遠方2画像の保持を保証するのに必要な枚数は，画像系列ごとに1，2，2，4枚だった．

64条件中，実際に遠方2画像をともに保持したのは44条件だった．各forwardの内部表現を固定したまま，別scene画像をscoreの尺度決めからだけ除くと，保持条件は44から0へ減った．したがって，今回観測した保持には，別scene画像が作るscoreの尺度が必要だった．

### Q7．別scene画像を正しく除外できれば，最初のVGGT推論が出した正しい画像の3Dは信頼できるか

**A．そのままでは信頼できなかった．別scene画像のlabelは正しかったが，同じjoint forwardに含まれる正しい画像のpoint mapも変化していた．**

次の比較では，共通する正しい8画像だけを入力した結果を基準にした．そこへ別scene画像4枚を追加する条件と，同じsceneの近傍画像4枚を追加する条件を比較した．同じ8画像を同じ順序でもう一度実行した差は数値精度以下だった．

入力ごとに3Dのglobal scaleと座標系が異なるため，基準側の5画像だけで共通出力をSim(3) alignmentした．その後，同じpixelが表す3D点の変位を測った．遠方画像は座標合わせに使っていない．

![同じ遠方画像におけるpoint map変位](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/projectivity_qualitative_example.png?raw=1)

*図6．変化が最大だった森林2の遠方画像である．中央と右は，8画像だけの出力に対する同一pixelの3D点変位を示す．同じ色尺度を用い，camera撮影範囲の直径に対する割合で表示した．別scene画像を加えた方が，画像全体で大きな変位が生じている．*

![共通する正しい画像のpoint map変化](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/shared_output_change_plots.png?raw=1)

*図7．4行は独立な画像系列である．左は，8枚だけを入力した場合を基準として，4枚を追加したときに共通8画像のpoint map誤差が何%変わったかを示す．0より右は悪化，左は改善である．右は別scene画像4枚を追加した場合について，同一pixelが表す3D点の変位を，camera撮影範囲の直径に対する割合で示す．*

別scene画像4枚は4画像系列すべてで正しく除外され，共通8画像もすべて保持された．それでも，共通8画像のpoint map誤差は4系列すべてで20.1%から38.0%増えた．同じsceneの近傍画像4枚を加えたcontrolでは，3系列で改善し，1系列の悪化も0.4%だった．

別scene画像による共通point mapの変位は，同じsceneの近傍画像を加えた場合より4系列すべてで大きかった．また，別scene画像を加えたときの変位は，遠方側の方が基準側より4系列すべてで大きかった．

ただし，絶対的な変位が事前に固定した1% thresholdを超えたのは1/4系列である．camera rotationの変化は0.11から0.27 degree，depthの変化は0.61%から1.94%であり，それぞれの0.5 degreeと5% thresholdを超えなかった．全出力が大きく崩壊したという結果ではなく，point map誤差の悪化方向が4/4系列で揃ったという結果である．

RobustVGGTの公式pipelineは，別scene画像を除いた後にVGGTを再実行する．図6と図7は，公式pipelineの最終出力が同じだけ悪化することを示していない．最初の推論で得た正しい画像の出力から，別scene画像だけをmaskしても元の3Dには戻らないこと，したがって二回目の推論に意味があることを示す．

## 何がnon-trivialだったか

1. **悪い入力を加えると，正しい入力の判定が改善した．** 別scene画像を追加する方が，正しい画像だけの入力より遠方画像を保持できた．
2. **画像の見た目やmodel表現を変えなくても反転した．** 同じforwardの値を再正規化するだけで，同じ判定反転が起きた．
3. **正しいlabelと汚染されていない3D出力は別だった．** 別scene画像を正しく見つけても，同じforwardの正しい画像のpoint mapはすでに変わっていた．

低overlap画像のscoreが低いこと自体は自明である．非自明なのは，より整合しない画像を追加すると，それまで除外されていた正しい画像が保持され，その3D completenessまで相対的に改善するという非単調性である．

## ここから生じるresearch question

固定thresholdを調整するだけでは，入力集合ごとにscoreの尺度が変わる問題を解けない．次の問いは，画像を二値で除外する方法そのものを問い直す．

> 複数sceneの画像が混在したとき，画像を一つずつ除外するのではなく，複数の整合した3D worldへ同時に分けられるか．また，新しいworldの画像を追加しても，既存worldの共通するcamera，depth，point mapを変えないようにできるか．

この問題を **set-projective multi-world 3D** と呼ぶ．異なるsceneの画像を追加したときは新しい3D worldを生成し，既存worldの3D出力は維持する．一方，基準画像と直接重ならない正しい遠方画像は，両側に重なる画像を介したmulti-hop geometryによって同じworldへ残す．

最小評価は次の三条件からなる．

1. 別scene画像を追加しても，既存worldの共通出力が変わらない．
2. 直接overlapの小さい正しい画像を，同じworldへ保持できる．
3. 入力部分集合を変えても，world分割と共通3D出力が整合する．

## 次に行う実験

- 見た目が似ている別scene画像を用い，物理的な不整合とappearance差を分ける．
- 同じ共通出力評価を別のE2E 3D architectureへ適用し，VGGT固有かを調べる．
- 画像除外後の再推論，leave-one-out整合性，pairwise view graph，multi-world出力を，同じ遠方画像保持率と共通3D出力の安定性で比較する．

## この結果からは言えないこと

- TartanAirの4画像系列だけであり，実画像で同じ頻度の反転が起きるとは言えない．
- VGGT-1Bの一checkpointとRobustVGGTの公開scoreだけを調べた．E2E 3D全般の性質とは言えない．
- 別scene画像は見た目をmatchingしていない．物理的不整合とappearance差を完全には分離していない．
- 64 forwardは同じ4画像系列内の条件比較であり，64独立sceneではない．
- 共通3D出力の16 forwardも，同じ4画像系列に対する対応づけた比較である．
- 大きな絶対point map変位が4系列すべてに出たわけではない．事前thresholdを超えたのは1/4系列である．
- 反復除外はscoreの性質を調べる追加実験であり，一回だけ除外する公式pipelineの通常出力ではない．

<details>
<summary>実行設定と公開データ</summary>

### Modelと画像score

- Model：`facebook/VGGT-1B`
- Score：RobustVGGT公式実装と同じ最終global blockのattentionとfeature similarity
- Attentionとfeatureの重み：各0.5
- 除外条件：scoreが0.4未満
- 学習・finetuning：なし

### 入力

- Dataset：TartanAir `Easy`
- Environment：森林2 trajectory，病院2 trajectory
- 画像枚数：12枚
- Model入力：crop mode，392 × 518 px
- 共通8画像：基準側5枚，両側に重なる1枚，遠方側2枚
- 比較する4枠：別scene画像，または同じsceneの近傍画像

### 遠方画像を持つ入力系列の選択

- 画像間のedge：mutual surface overlap 10%以上
- 基準側と遠方側：mutual overlap 3%以下
- 両側に重なる画像と基準側：10%以上45%以下
- 両側に重なる画像と遠方側：10%以上
- 遠方側の代表画像において，基準側から見えない表面が20%以上
- その表面のうち，両側に重なる画像から見える部分が5%以上

### 3D評価

- 座標合わせ：基準側画像の対応点だけを使う80% trimmed Sim(3)，3反復
- Completenessの評価領域：基準側の全画像から不可視で，両側に重なる画像から可視な遠方側表面
- Completeness threshold：scene直径の2%，下限10 cm，上限50 cm
- 共通出力の事前threshold：point mapとcamera centerはcamera撮影範囲直径の1%，camera rotationは0.5 degree，depth差は5%，または同一入力再実行差の5倍の大きい方
- 集計単位：画像系列．画像，pixel，条件，反復回数を独立標本として数えない

### 公開データ

- [入力集合，score，3D completenessの集計](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/data/set_relative_filter_geometry.json)
- [反復除外の集計](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/data/iterative_filter_cascade.json)
- [最後の4枠の全組合せ](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/data/distractor_subset_law.json)
- [共通3D出力の集計](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/data/shared_output_projectivity.json)
- [qualitative例のmetadata](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/data/qualitative_forest2.json)
- [qualitative例の縮小画像とpoint map変位](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/data/qualitative_forest2.npz)
- [図生成script](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/scripts/make_figures.py)

Qualitative図にはTartanAirの縮小画像を用いた．元解像度の画像，depth，model checkpointは再配布していない．

</details>

## 事実と解釈の区分

- **論文に書かれていること**：VGGTの入出力と，RobustVGGTがscoreで画像を除外してからVGGTを再実行する構成である．
- **手元で再現したこと**：公開Trevi／Notre-Dame例の除外結果である．
- **今回新しく測ったこと**：TartanAir 4画像系列の入力比較，3D completeness，反復除外，全64組合せ，共通3D出力の比較である．
- **結果からの解釈**：入力集合に依存しない画像選択と，set-projective multi-world 3Dが必要だという部分である．

## 一次資料

- [VGGT paper](https://arxiv.org/abs/2503.11651) / [official code](https://github.com/facebookresearch/vggt)
- [RobustVGGT paper](https://arxiv.org/abs/2512.04012) / [official code](https://github.com/cvlab-kaist/RobustVGGT)
- [TartanAir dataset](https://theairlab.org/tartanair-dataset/)
