# [Research question] 座標ではなく「幾何を満たす関係式」を予測するfeed-forward 3Dは有利か

> 状態: 仮説と実験計画．学習・評価は未実施．

## 先に結論

VGGTのようなfeed-forward 3Dは，複数画像からcamera pose，depth，pointmap，trackを直接予測する．今回残った仮説は，これらの座標を出力せず，「同じ3D世界なら満たすべき局所的な関係式」だけを予測し，cameraと観測された3D点を一つの共通解から復元するというものである．

この仮説に情報量の優位性はない．局所座標を予測すれば，同じ関係式を決定的に作れるからである．したがって，効くとすれば，関係式だけを出力させる制約が学習時の無駄な自由度を減らすという，出力形式が学習へ与える構造的な偏りによる．

最も重要な実験は，関係式を直接予測する方法と，同じ情報量の座標を予測してから同じ関係式へ変換する方法を，同じbackbone，同じ対応関係，同じsolver，同じrefinementで比較することである．座標側が同等以上なら，手法としての仮説は棄却される．

このIssueでは，仮説を判定するための最小比較，揃える条件，支持・棄却・保留を分ける基準を記録する．

## 何を変えようとしているのか

![現在の出力形式と今回の仮説](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/constraint_output_hypothesis.png?raw=1)

*図1．上段はcamera，depth，pointmap，trackのような座標を直接出す現在の構成である．下段は局所的な幾何関係だけを出し，全体を一つのnullspaceから復元する仮説である．*

局所的な関係式は，近くにある少数のカメラ中心や観測点へ符号付きの重みを付け，整合した3D配置では重み付き和がゼロになるように作る．多数の関係式を集め，すべてを同時に満たす解空間を求めると，理想的な条件では三つの3D座標成分と一つの定数成分を同時に復元できる．

これは「VGGTの結果へ別の最適化を追加する」話ではない．GLUEMAPやGlob3Rは，feed-forward modelが出したdepth，pose，pointmap，warp，trackをglobal SfMやbundle adjustmentへ渡す構成を既に示している．今回変えるのは後処理ではなく，ニューラルネットワークの唯一の幾何出力である．

## どこが自明でないのか

一見すると，「座標より関係式の方がシーン全体の整合性を表しやすい」と考えられる．しかし，固定した局所的な対応関係では，座標から関係式を作ることができ，関係式から局所座標を復元できる条件も多い．両者はほぼ同じ情報のreparameterizationである．

そのため，次の広い主張はできない．

- 関係式は座標より多くの情報を持つ．
- 固定solverを使うこと自体が新しい．
- 関係式がglobalに整合すれば，画像対応も正しい．
- Feed-forward 3Dとglobal optimizationを組み合わせることが新しい．

残る問いは一つだけである．同じ情報，同じsolver，同じ計算量でも，関係式を直接予測するという出力制約自体が，通常のcameraと3D reconstructionを改善するかである．この比較には，先行研究も今回の手元実験もまだ答えていない．

## 先行研究との境界

- [Neural Jacobian Fields](https://arxiv.org/abs/2205.02904)は，局所Jacobianを予測し，標準Poisson solveでglobal mapを復元する一般構図を既に示している．
- [GLUEMAP](https://arxiv.org/abs/2605.26103)の公式実装は，feed-forward outputとしてdepth，depth confidence，camera extrinsics，intrinsicsを要求する．
- [Glob3R](https://arxiv.org/abs/2607.09225)は，local geometryとdense warpからtrackを作り，motion averagingとbundle adjustmentを行う．
- DROID-SLAM，BA-Net，DeepV2Dなどは，学習したflow，depth，pose，residualをfactor graphやbundle adjustmentで解く．
- Fundamental matrixを学習する研究は二画像間のconstraint matrixを扱うが，scene全体のcameraと3D点を一つのnullspaceから同時に復元しない．
- LLE，LTSA，affine rigidityは，局所的なaffine relationからglobal embeddingを復元する数学を既に持つ．

以上の一般構図は新規性に数えられない．調査範囲で見つからなかったのは，「未加工の複数視点RGB画像から座標を別に出力せず，関係式だけを学習し，cameraと観測3Dが同じnullspaceからのみ現れる」という出力設計である．見つからなかったことは新規性の証明ではない．

## Q&A

### Q1．なぜ関係式を直接予測すると良くなる可能性があるのか

**A．座標系の選び方に使う自由度を減らし，すべてのcameraと3D点を全体で共通する一つの解へ結び付けられる可能性があるからである．**

同じ3D形状でも，座標値は平行移動，回転，scaleなどで変わる．関係式はこの違いを除いたまま学習できる．ただし，これは仮説であり，精度改善は未確認である．

### Q2．関係式が整合していれば，正しい3Dを得られるのか

**A．得られるとは限らない．誤った画像対応でも，一貫していれば代数的にきれいな解を作れる．**

Nullspace solverは関係式同士の矛盾を検出できるが，その関係式が現実の同じ点を結んでいるかは判定できない．繰り返し模様や似た建物では，誤対応がglobalに整合する可能性がある．

### Q3．難しい画像を混ぜる実験から始めてはいけないのか

**A．その実験だけでは，関係式の表現が有利だと判断できない．**

どの画像やpixelを結ぶかを選ぶ部分や，どのcomponentを残すかという規則だけで結果を作れるからである．まず通常のmulti-view sceneでcameraと3D形状そのものが良くなるかを測る必要がある．

### Q4．どの結果なら仮説を支持するのか

**A．関係式を直接予測する方法だけがcameraと観測3Dを改善し，固定したnullspace復元を置き換えると差が消える結果である．**

差は全手法へ同じbundle adjustmentを適用した後にも残り，対応関係の選択，component処理，計算量では説明できない必要がある．

### Q5．どの結果なら棄却するのか

**A．座標を予測して同じ関係式へ変換する方法が同等以上なら，新しい手法としての仮説を棄却する．**

最終3Dは同じで，初期整合性や数値条件だけが変わる場合は，最終精度への効果は支持されない．その場合は数値条件と最適化挙動を切り分ける．人工的な診断条件だけが良い場合は前進させない．

## 最初に必要な実験

![最初に必要な比較](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/constraint_matched_test.png?raw=1)

*図2．関係式を直接予測する手法，座標から同じ関係式を作る手法，同じ対応関係から通常のSfMを行う手法，固定nullspaceを学習可能なreadoutへ置き換える手法を比較する．*

### 比較する手法

1. 関係式だけを直接予測し，固定nullspace solverでcameraと3D点を得る．
2. 同じ数の連続値で局所座標を予測し，同じ関係式へ変換して，同じnullspace solverへ渡す．
3. 同じ対応関係と局所座標を通常のSfMへ渡す．
4. 関係式を予測するが，固定したnullspace復元だけを同程度の表現力を持つ学習器へ置き換える．

### 揃える条件

- 入力画像，学習済みbackbone，初期値
- 実際に選ばれたcameraとpixelの対応関係
- 一つの局所関係が出力する連続値の数
- Training data，supervision，optimizer，学習step，seed
- Camera convention，intrinsics，scale alignment，cheirality
- Componentを残す規則，失敗時のfallback
- Bundle adjustmentとrobust loss
- Parameter数，routingを含む推論時間，peak memory

### 暫定pilot設定

- VGGT-1Bのbackboneを固定し，出力headだけを学習する．
- 一つのsceneから10画像を入力し，model入力は518 pxとする．
- CO3DとReplicaで開発し，学習に使わないCO3D・Replica sceneとETH3Dで通常条件を評価する．
- TartanAir，弱いoverlap，長いscene，繰り返し模様は追加評価とし，最初の主要評価から分ける．
- OpenCVのworld-to-cameraと既知intrinsicsを使い，同じgauge alignmentを全手法へ適用する．
- 同じbundle adjustmentを最大80回適用し，適用前後を両方保存する．
- Cameraはrelative rotation，relative translation direction，Pose AUC@5/10/30で評価する．
- 3DはDepth AbsRel，point cloud accuracy/completeness，観測領域の3D誤差で評価する．
- 三つ以上のseed，失敗率，数値条件，推論時間，peak memoryを保存する．

採用・棄却の数値thresholdは未設定である．実装前に固定する必要がある．

## 実験結果の判定

| 観測 | 判定 |
|---|---|
| 関係式を直接予測する方法だけがcameraと観測3Dを改善し，固定nullspace復元を置き換えると差が消える | 仮説を支持する |
| 座標を予測して同じ関係式へ変換する方法が同等以上になる | 仮説を棄却する |
| 最終3Dは同じで，bundle adjustment前の整合性や数値条件だけが変わる | 最終精度への効果は支持されない．現象を切り分けて再評価する |
| 人工的なscene混合やnullspaceの診断値だけが改善する | 保留とし，通常sceneのcamera・3D指標が改善するまで拡張しない |

## 詳細

- [詳細レポート](../blob/main/reports/2026-07-15-constraint-native-feed-forward-3d.md)

## 一次資料

- [VGGT](https://arxiv.org/abs/2503.11651) / [official code](https://github.com/facebookresearch/vggt)
- [π³](https://openreview.net/forum?id=DTQIjngDta) / [official code](https://github.com/yyfz/Pi3)
- [MapAnything](https://map-anything.github.io/) / [official code](https://github.com/facebookresearch/map-anything)
- [Neural Jacobian Fields](https://arxiv.org/abs/2205.02904)
- [GLUEMAP](https://arxiv.org/abs/2605.26103) / [official code](https://github.com/colmap/gluemap)
- [Glob3R](https://arxiv.org/abs/2607.09225) / [project page](https://junyuandeng.github.io/Glob3r/)
