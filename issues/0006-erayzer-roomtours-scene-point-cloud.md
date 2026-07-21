> 状態：結果あり．RoomToursの4 sceneを用い，E-RayZerのlocal Gaussianをscene-level point cloudへ統合できるかを，学習なしで比較した．今回試した方法からは，破綻していないscene point cloudは得られなかった．

## 結論

E-RayZerを5-view単位のlocal reconstructorとして使い，overlap，同一pixel対応，robust Sim(3)，global graph optimization，ray re-anchoringまで試した．しかし，**4 sceneすべてでwindow間の位置・scale・局所形状が十分には整合せず，LAM3Cへ渡す前段のscene-level point cloudとしては破綻した**．

- Gaussian中心のnearest-neighbor対応は，4 sceneすべてで有効な点群を出せなかった．
- shared frame上のsame-pixel対応ならregistration edgeは作れたが，held-out residualとinlier率が悪かった．
- global Sim(3) graphは，逐次合成より明確には改善しなかった．
- global camera rayへのre-anchoringは一部のF-scoreを改善したが，surface thicknessやscene coverageを同時には改善しなかった．
- source-window色で見ると，windowごとのずれ，壁・床の反復，sceneの多重化が全sceneに残った．
- 外部cameraを使うoracleはscale calibrationを通過せず，cameraとlocal geometryのどちらが主因かはまだ分離できていない．

これは「汚い点群から学習できるか」の評価ではない．LAM3Cはその後段を扱うため，本Issueではまず**学習入力として扱う以前に，一つのscene point cloudとして成立しているか**を調べた．

## 元レビューの項目を全部試したか

**全部は試していない．** 今回は，学習なしでscene point cloudを成立させる中心経路を優先した．以下の「一部実施」「未実施」を，実施済みと読み替えてはいけない．

| レビュー項目 | 状態 | 今回行ったこと／残っていること |
|---|---|---|
| 3-frame overlapの5-view window | **実施済み** | 40 keyframesからstride 2で18 windowを作り，隣接windowは3 reference framesを共有した |
| optical flow・blur・dynamic ratio等によるadaptive keyframe選択 | **未実施** | 40 framesは時間方向に固定抽出した |
| raw Gaussian NN + 逐次Umeyama | **実施済み** | A2nでhistorical non-overlap baseline，A2oでoverlap＋robust NNを評価した |
| shared-frame / same-pixel対応 | **実施済み** | A3で全33 edge/sceneを推定した |
| 対応候補filter | **一部実施** | opacity，Gaussian scale，画像端，depth discontinuity，depth ratioをfilterした．dynamic/specular maskとforward–backward reprojection判定は未実施 |
| robust Sim(3)初期化・refinement | **実施済み** | RANSAC 512 trials＋Cauchy IRLS 25 iterationsを使用した．TEASER++そのものは未使用 |
| photometric reprojection refinement | **未実施** | 今回のheld-outは3D correspondence residualであり，RGB photometric lossではない |
| camera center・rotationとsame-pixel pointの併用 | **実施済み** | A4 graphでcamera center/rotationにも重みを与えた |
| global Sim(3) graph | **実施済み** | 全18 submapをjoint optimizationし，adjacent edge，second-neighbor cycle，robust switch，未使用audit edgeを入れた |
| appearance retrievalによる長距離loop closure | **未実施** | 今回の冗長edgeは共有frameを持つsecond-neighborまでで，scene再訪検出は行っていない |
| raw XYZ変換とray re-anchoringの比較 | **実施済み** | A4FとA5でfilter・fusion・point budgetを固定して比較した |
| opacity/support filterとvoxel fusion | **実施済み** | opacity，scale，2-window support，voxel fusionを使用した．normal consistencyとdynamic maskは未実施 |
| point provenance保存 | **実施済み** | source window/frame，pixel，opacity，support，alignment uncertaintyを保持した |
| 外部global camera oracle | **実行したが判定不能** | A6でVGGT cameraのみを使用したが，4/4でlocal/global scale calibrationが成立せず，点群を生成できなかった．MASt3R-SLAM/VGGT-SLAMの完成trajectoryを用いたoracleは未実施 |
| E-RayZer-only backend | **一部実施** | same-pixel 3D＋E-RayZer cameraのgraphまでは実施．RGB photometric refinementとappearance loop closureは未実施 |
| scene-level E-RayZer再学習 | **未実施** | recurrent memoryや長系列fine-tuningは行っていない |
| Gaussian Gauge Atlas | **一部実施** | local chartsとtransitionをlossless artifactとして保存・可視化した．feature transportを含むAtlas学習は未実施 |

レビュー中のL0--L6との対応は次の通りである．

| Arm | 状態 | 対応する今回の実験 |
|---|---|---|
| L0: local 5-view cloud SSL | **未実施** | 本Issueは学習前のpoint-cloud integrityに限定 |
| L1: raw concat | **実施済み** | A1 |
| L2: sequential Umeyama | **実施済み** | A2n |
| L3: overlap + same-pixel robust Sim(3) | **実施済み** | A3 |
| L4: global Sim(3) graph | **実施済み** | A4 |
| L5: external poses + ray re-anchoring | **実行したが点群なし** | A6．scale calibration unavailable |
| L6: E-RayZer graph + ray re-anchoring | **実施済み** | A5 |

評価項目についても，shared-frame 3D residual，graph audit residual，Pi3 pseudo-referenceに対するcompleteness/precision/F-score，surface thickness，coverage，blind visual reviewは実施した．camera ATE/RPE，held-out RGB reprojection，residualのdepth/image-radius/normal/view-angle別plot，最終3D linear-probe mIoUは未実施である．

## 背景：なぜ5-view出力をそのまま連結できないのか

E-RayZerは，checkpointの通常設定では5枚のreference RGB画像からpixel-aligned Gaussiansを生成し，別の5枚をcontextとして使う．長いroom video全体を一つの座標系で再構成するmodelではない．

したがってscene videoを複数windowへ分けると，各windowは独立に次を予測する．

- camera poseとintrinsics
- camera ray上のdepth
- Gaussian center，rotation，scale，opacity，color
- window内だけで定義された座標系とscale

同じ壁を見ていても，windowごとに座標・scale・depth distortionが少しずれる．この状態でGaussian中心をnearest neighborとして対応づけ，Umeyamaを逐次適用すると，誤対応と小さなscale/rotation誤差がscene全体へ蓄積する．

中心仮説は次だった．

> E-RayZerをscene predictorへ再学習しなくても，overlapするlocal submapとして扱い，共有frameのsame-pixel対応とglobal Sim(3) backendを使えば，scene全体を一つの点群へ整合できるのではないか．

## 実験の入力から出力まで

```text
RoomTours scene video
        ↓ 40 RGB keyframesを抽出
overlapping local windows
        ↓ 各window: 5 reference + 5 context
frozen E-RayZer inference
        ↓ local Gaussians + local cameras + ray depth
window間の対応・Sim(3)推定
        ↓ sequential alignment または global graph
point construction
        ↓ transformed XYZ または global-ray re-anchoring
filtering / voxel fusion
        ↓
dense colored scene cloud + normalized 20k point cloud
        ↓
registration・coverage・surface quality・blind visual評価
```

入力は同一tour内のbathroom，bedroom 2件，living roomの4 sceneである．各sceneから40 keyframesを取り，5 reference viewsをstride 2で動かしたため，1 sceneにつき18 local windowsとなる．隣接windowは3 reference framesを共有する．A1からA5までは同じframe，reference/context role，同じE-RayZer raw outputを使い，対応・global alignment・point constructionだけを変えた．

要求する出力は，局所windowごとの点群ではなく，一つのscene座標系に置かれたcolored point cloudである．定量評価用には点数を20,000へそろえたpoint cloudも作った．

## 比較した手法

| 手法 | 入力と処理 | 何を比較するための手法か |
|---|---|---|
| **Pi3** | 同じsceneに対する既存のPi3点群 | 厳密なground truthではなく，geometry評価のpseudo-reference |
| **A0-all** | 40 viewsをE-RayZerへ一括入力し，高opacity Gaussian centerを点群化 | window統合を避けたone-shot上限．ただし学習時より大幅に多い画像を入れるためOOD |
| **A0-all-ellipsoids** | A0-allと同じ一括推論から，centerだけでなくGaussian ellipsoid上をsample | Gaussian centerだけを点にすることが原因かを見るOOD control |
| **A1: raw concat** | 18 local point cloudsをalignmentせず単純連結 | windowごとの座標ずれがどの程度かを見る最小baseline |
| **A2n: historical Umeyama** | non-overlap window，Gaussian centerのnearest neighbor，逐次Umeyama | 共著者が最初に試していた方法に対応するbaseline |
| **A2o: overlap + robust NN Sim(3)** | overlap windowへ変え，Gaussian centerのNN候補から外れ値に頑健なSim(3)を逐次推定 | overlapとrobust solverだけでraw Gaussian対応を救えるか |
| **A3: same-pixel Sim(3)** | shared frameの同一pixelから得た3D点同士を対応させ，同じrobust Sim(3) stackで逐次合成 | solverを固定し，NN対応をpixel-identity対応へ変えた効果 |
| **A4: global Sim(3) graph** | A3で得たedgeを全windowのgraphとして同時最適化．一部edgeはfitに使わずheld-out auditへ回す | sequential driftをglobal optimizationとcycleで除けるか |
| **A4F: direct XYZ + matched fusion** | A4のglobal transformでlocal XYZを移し，A5と同じfiltering・fusionを適用 | A5との差をray re-anchoringだけに限定するcontrol |
| **A5: ray re-anchoring** | A4のglobal cameraと各pixelのE-RayZer ray depthから，global camera ray上へpointを再構築してfusion | local camera誤差をXYZへ焼き込まず，ray depthだけを移送する効果 |
| **A6: external-camera oracle** | VGGTのglobal camera trajectoryを使い，E-RayZerのintrinsics・ray depth・fusionはA5と同じ | camera/gaugeが正しければ点群が成立するかを調べるcontrol |
| **ATLAS** | local A3 submapをmergeせず，chartとwindow間transitionを保持 | global point cloudへ無理に焼き込まず，local geometryが残るかを見るdiagnostic |

A2oとA3はcorrespondenceだけ，A3とA4はsequentialかglobal graphかだけ，A4FとA5はpoint constructionだけが異なる．したがって，改善があればどの操作によるものかを切り分けられる設計にした．

## どう評価したか

### 1．local Sim(3)は未知の対応にも成立するか

fitに使わなかったshared-frame対応に対し，正規化3D residualの中央値と90 percentileを測った．また，fit候補のうちrobust estimatorでinlierとなった割合も測った．成功条件はmedian 3%以下，p90 5%以下，inlier率50%以上である．

### 2．global graphは逐次合成よりdriftを減らすか

graph fitに使わなかったaudit edgesで，A4がA3よりresidualを25%以上減らすか，または絶対residualを3%以下にすることを要求した．隣接edgeを悪化させないこと，switchが十分残ること，graphがconnectedであることも同時に要求した．

### 3．ray re-anchoring自体に効果があるか

同じtransform・filter・point budgetを持つA4FとA5を比較した．Pi3に対する2%/5% F-scoreのどちらかが3 percentage points以上改善するだけでなく，surface thicknessが20%以上改善し，completenessとcoverageを維持することを要求した．F-scoreだけが上がっても，大量削除やsurfaceの肥厚なら成功とはしない．

### 4．最終点群がsceneとして成立しているか

finite point率，largest connected component，複数windowから支持されたscene occupancy，unsupported point，duplicate surfaceを測った．加えて，手法名を隠したsix-view renderingとsource-window coloringから，window split，repeated wall/floor，floaterを判定した．必須のsupported occupancyは80%以上である．

## 定量結果

| Scene | A2o | A3 held-out median / p90 / inlier | A4 audit改善 / active switches | A5−A4F F@2 / F@5 | A5 occupancy / LCC | Blind visual |
|---|---|---:|---:|---:|---:|---|
| bathroom | 対応候補不足で点群なし | 7.5% / 66.8% / 31.0% | +3.9% / 0.80 | −3.7 / −2.2 pp | 10.2% / 96.5% | fail |
| bedroom-1 | Sim(3) consensusなし | 9.8% / 82.1% / 22.1% | −27.6% / 0.80 | +0.5 / −0.2 pp | 6.2% / 65.3% | fail |
| living room | Sim(3) consensusなし | 11.1% / 86.2% / 20.8% | −0.7% / 0.88 | +0.2 / +1.5 pp | 7.5% / 95.9% | fail |
| bedroom-2 | Sim(3) consensusなし | 12.9% / 65.3% / 21.9% | +4.2% / 0.84 | +1.0 / +3.2 pp | 6.2% / 98.6% | fail |

主な読み方は次である．

1. **A2oは4/4で点群なし．** raw Gaussian centerのNN対応は，overlapとrobust Sim(3)を入れても安定しなかった．
2. **A3もlocal Sim(3)として不十分．** medianは要求3%に対して7.5–12.9%，p90は要求5%に対して65.3–86.2%，inlier率は要求50%に対して20.8–31.0%だった．cleanなsame-pixel対応でも，一つのSim(3)では説明できないlocal distortionが残る可能性が高い．
3. **A4はdriftを解消しなかった．** held-out auditの改善は−27.6%から+4.2%で，要求した+25%に届かなかった．
4. **A5のcoverageが崩壊した．** supported occupancyは6.2–10.2%で，要求80%を大きく下回った．unsupported/duplicate pointがfilter後に0でも，sceneの大部分を削除した結果なら成功とは扱えない．
5. **bedroom-2のF@5だけは+3.2 pp改善したが，surface thicknessは7.1%悪化した．** ray re-anchoring固有の構造改善とは判定できない．
6. **A6は4/4で点群を出せなかった．** local cameraとglobal cameraのscale calibrationが不安定だったためで，cameraを差し替えれば解決するというoracle結果はまだ得られていない．

## Qualitative結果

旧contact sheetは9手法×6視点を1枚へ詰めており，点群が小さすぎたため使用を止めた．以下は**1行最大4パネル**とし，入力4 frames，Pi3点群，手法ごとのfront viewを分離して掲載する．各画像を開くと元解像度で確認できる．Pi3は同じsceneの既存点群を単独renderしたpseudo-referenceであり，ground truthではない．各手法画像内の`Arm-XX`はblind評価時の匿名ラベルで，表の見出しがreveal後の手法名である．

RGBはpoint color，sourceは生成元windowによる色分けである．source画像で異なる色の壁・床が平行に反復する場合，同じsurfaceがwindowごとに別位置へ置かれている．A2oとA6は点群を生成できなかったため，空欄を画像で埋めず「点群なし」と表示する．

### Bathroom

代表入力4 frames（実際の40 keyframesの先頭・約1/3・約2/3・末尾）：

<img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/input_frames.jpg?raw=1" width="100%">

<table>
<tr>
<td width="25%"><b>Pi3 pseudo-reference</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/pi3_front.png?raw=1" width="100%"></td>
<td width="25%"><b>A0-all</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A0-all-rgb-front.png?raw=1" width="100%"></td>
<td width="25%"><b>A0-all-ellipsoids</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A0-all-ellipsoids-rgb-front.png?raw=1" width="100%"></td>
<td width="25%"><b>A1 raw concat</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A1-rgb-front.png?raw=1" width="100%"></td>
</tr>
<tr>
<td><b>A2n Umeyama</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A2n-rgb-front.png?raw=1" width="100%"></td>
<td><b>A3 same-pixel</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A3-rgb-front.png?raw=1" width="100%"></td>
<td><b>A4 global graph</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A4-rgb-front.png?raw=1" width="100%"></td>
<td><b>A4F direct XYZ</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A4F-rgb-front.png?raw=1" width="100%"></td>
</tr>
<tr>
<td><b>A5 ray re-anchor</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A5-rgb-front.png?raw=1" width="100%"></td>
<td><b>ATLAS export</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/ATLAS-rgb-front.png?raw=1" width="100%"></td>
<td><b>A2o robust NN</b><br>点群なし：fit候補10点 &lt; 必要12点</td>
<td><b>A6 VGGT camera</b><br>点群なし：scale calibration unavailable</td>
</tr>
</table>

<details><summary>Bathroom：top viewとsource-window色</summary>

<table><tr>
<td width="25%"><b>Pi3 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/pi3_top.png?raw=1" width="100%"></td>
<td width="25%"><b>A3 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A3-rgb-top.png?raw=1" width="100%"></td>
<td width="25%"><b>A4 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A4-rgb-top.png?raw=1" width="100%"></td>
<td width="25%"><b>A5 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A5-rgb-top.png?raw=1" width="100%"></td>
</tr><tr>
<td><b>A3 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A3-source-front.png?raw=1" width="100%"></td>
<td><b>A4 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A4-source-front.png?raw=1" width="100%"></td>
<td><b>A4F / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A4F-source-front.png?raw=1" width="100%"></td>
<td><b>A5 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-001_bathroom/A5-source-front.png?raw=1" width="100%"></td>
</tr></table>
</details>

### Bedroom-1

<img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/input_frames.jpg?raw=1" width="100%">

<table>
<tr>
<td width="25%"><b>Pi3 pseudo-reference</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/pi3_front.png?raw=1" width="100%"></td>
<td width="25%"><b>A0-all</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A0-all-rgb-front.png?raw=1" width="100%"></td>
<td width="25%"><b>A0-all-ellipsoids</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A0-all-ellipsoids-rgb-front.png?raw=1" width="100%"></td>
<td width="25%"><b>A1 raw concat</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A1-rgb-front.png?raw=1" width="100%"></td>
</tr>
<tr>
<td><b>A2n Umeyama</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A2n-rgb-front.png?raw=1" width="100%"></td>
<td><b>A3 same-pixel</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A3-rgb-front.png?raw=1" width="100%"></td>
<td><b>A4 global graph</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A4-rgb-front.png?raw=1" width="100%"></td>
<td><b>A4F direct XYZ</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A4F-rgb-front.png?raw=1" width="100%"></td>
</tr>
<tr>
<td><b>A5 ray re-anchor</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A5-rgb-front.png?raw=1" width="100%"></td>
<td><b>ATLAS export</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/ATLAS-rgb-front.png?raw=1" width="100%"></td>
<td><b>A2o robust NN</b><br>点群なし：Sim(3) consensusなし</td>
<td><b>A6 VGGT camera</b><br>点群なし：scale calibration unavailable</td>
</tr>
</table>

<details><summary>Bedroom-1：top viewとsource-window色</summary>
<table><tr>
<td width="25%"><b>Pi3 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/pi3_top.png?raw=1" width="100%"></td>
<td width="25%"><b>A3 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A3-rgb-top.png?raw=1" width="100%"></td>
<td width="25%"><b>A4 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A4-rgb-top.png?raw=1" width="100%"></td>
<td width="25%"><b>A5 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A5-rgb-top.png?raw=1" width="100%"></td>
</tr><tr>
<td><b>A3 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A3-source-front.png?raw=1" width="100%"></td>
<td><b>A4 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A4-source-front.png?raw=1" width="100%"></td>
<td><b>A4F / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A4F-source-front.png?raw=1" width="100%"></td>
<td><b>A5 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-002_bedroom/A5-source-front.png?raw=1" width="100%"></td>
</tr></table>
</details>

### Living room

<img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/input_frames.jpg?raw=1" width="100%">

<table>
<tr>
<td width="25%"><b>Pi3 pseudo-reference</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/pi3_front.png?raw=1" width="100%"></td>
<td width="25%"><b>A0-all</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A0-all-rgb-front.png?raw=1" width="100%"></td>
<td width="25%"><b>A0-all-ellipsoids</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A0-all-ellipsoids-rgb-front.png?raw=1" width="100%"></td>
<td width="25%"><b>A1 raw concat</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A1-rgb-front.png?raw=1" width="100%"></td>
</tr>
<tr>
<td><b>A2n Umeyama</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A2n-rgb-front.png?raw=1" width="100%"></td>
<td><b>A3 same-pixel</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A3-rgb-front.png?raw=1" width="100%"></td>
<td><b>A4 global graph</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A4-rgb-front.png?raw=1" width="100%"></td>
<td><b>A4F direct XYZ</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A4F-rgb-front.png?raw=1" width="100%"></td>
</tr>
<tr>
<td><b>A5 ray re-anchor</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A5-rgb-front.png?raw=1" width="100%"></td>
<td><b>ATLAS export</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/ATLAS-rgb-front.png?raw=1" width="100%"></td>
<td><b>A2o robust NN</b><br>点群なし：Sim(3) consensusなし</td>
<td><b>A6 VGGT camera</b><br>点群なし：scale calibration unavailable</td>
</tr>
</table>

<details><summary>Living room：top viewとsource-window色</summary>
<table><tr>
<td width="25%"><b>Pi3 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/pi3_top.png?raw=1" width="100%"></td>
<td width="25%"><b>A3 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A3-rgb-top.png?raw=1" width="100%"></td>
<td width="25%"><b>A4 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A4-rgb-top.png?raw=1" width="100%"></td>
<td width="25%"><b>A5 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A5-rgb-top.png?raw=1" width="100%"></td>
</tr><tr>
<td><b>A3 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A3-source-front.png?raw=1" width="100%"></td>
<td><b>A4 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A4-source-front.png?raw=1" width="100%"></td>
<td><b>A4F / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A4F-source-front.png?raw=1" width="100%"></td>
<td><b>A5 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-003_living_room/A5-source-front.png?raw=1" width="100%"></td>
</tr></table>
</details>

### Bedroom-2

<img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/input_frames.jpg?raw=1" width="100%">

<table>
<tr>
<td width="25%"><b>Pi3 pseudo-reference</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/pi3_front.png?raw=1" width="100%"></td>
<td width="25%"><b>A0-all</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A0-all-rgb-front.png?raw=1" width="100%"></td>
<td width="25%"><b>A0-all-ellipsoids</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A0-all-ellipsoids-rgb-front.png?raw=1" width="100%"></td>
<td width="25%"><b>A1 raw concat</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A1-rgb-front.png?raw=1" width="100%"></td>
</tr>
<tr>
<td><b>A2n Umeyama</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A2n-rgb-front.png?raw=1" width="100%"></td>
<td><b>A3 same-pixel</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A3-rgb-front.png?raw=1" width="100%"></td>
<td><b>A4 global graph</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A4-rgb-front.png?raw=1" width="100%"></td>
<td><b>A4F direct XYZ</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A4F-rgb-front.png?raw=1" width="100%"></td>
</tr>
<tr>
<td><b>A5 ray re-anchor</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A5-rgb-front.png?raw=1" width="100%"></td>
<td><b>ATLAS export</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/ATLAS-rgb-front.png?raw=1" width="100%"></td>
<td><b>A2o robust NN</b><br>点群なし：Sim(3) consensusなし</td>
<td><b>A6 VGGT camera</b><br>点群なし：scale calibration unavailable</td>
</tr>
</table>

<details><summary>Bedroom-2：top viewとsource-window色</summary>
<table><tr>
<td width="25%"><b>Pi3 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/pi3_top.png?raw=1" width="100%"></td>
<td width="25%"><b>A3 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A3-rgb-top.png?raw=1" width="100%"></td>
<td width="25%"><b>A4 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A4-rgb-top.png?raw=1" width="100%"></td>
<td width="25%"><b>A5 / top</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A5-rgb-top.png?raw=1" width="100%"></td>
</tr><tr>
<td><b>A3 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A3-source-front.png?raw=1" width="100%"></td>
<td><b>A4 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A4-source-front.png?raw=1" width="100%"></td>
<td><b>A4F / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A4F-source-front.png?raw=1" width="100%"></td>
<td><b>A5 / source</b><br><img src="https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/t24_erayzer_scene_pc_v2/scene-004_bedroom/A5-source-front.png?raw=1" width="100%"></td>
</tr></table>
</details>

全sceneで，A3/A4/A4F/A5/ATLASにwindow splitまたはrepeated/ghosted room surfaceが残る．A0 variantsはcompactだが40-view one-shot OODであり，multi-window fusionの成功例ではない．Bedroom-2ではA5のF@5が少し上がったものの，source-window wall layerが残りsurface thicknessも悪化している．

## 手法ごとに分かったこと

- **A0-all / ellipsoids**：compactには見えるが，E-RayZerの学習範囲外である40-view one-shot入力であり，multi-window間の支持率も0である．scene assemblyの成功とは扱えない．
- **A1**：同じsurfaceがwindowごとに別位置へ並び，raw concatが不可能であることを確認した．
- **A2n**：逐次Umeyamaでは平行なwall layerとscale driftが残る．
- **A2o**：raw Gaussian centerのNNはrobust化しても対応自体が成立せず，点群を出せない．
- **A3**：same-pixel対応はNNより定義が明確で全sceneのedgeを作れたが，single Sim(3) modelの残差が大きい．
- **A4**：global graphはconnectedになっても，bad local geometryを修正できず，held-out edgeを改善しない．
- **A4F**：filter/fusionをそろえてもghostingが残り，単なるfusion tuningでは解決しない．
- **A5**：ray re-anchoringは局所的なscoreを動かすが，coverageとsurface qualityを両立しない．
- **A6**：外部camera oracleを成立させる前のscale/convention calibrationが主な未解決点である．
- **ATLAS**：local chartを壊さず保存できるが，現時点では一つのscene point cloudではない．学習方法を導入する前に，local chart自体のgeometryが有効かを調べる必要がある．

## 現在言えること／言えないこと

言えることは，今回の4 sceneでは，raw NN，same-pixel Sim(3)，global graph，matched fusion，ray re-anchoringのいずれも破綻しないscene point cloudを作れなかったことである．

一方，次はまだ言えない．

- E-RayZerの再学習が必要かどうか
- camera/gauge，intrinsics，ray-depth convention，local non-Sim(3) distortion，fusionのどれが支配的か
- この点群でもLAM3C型学習なら有効か
- RoomTours全体へ一般化するか．4 sceneは同一tourから取っている

## 次に行う診断

次は複雑なfusionを追加するのではなく，**conventionを確認した外部cameraで，各local E-RayZer surfaceをglobal rayへ置き直し，fusion前の状態で評価する**．

1. externally posed unfused local surfacesを作る
2. shared frameのreprojectionとdepth consistencyを測る
3. residualをdepth，image radius，surface normal，view angleごとに分解する
4. unfused local surfaceが正しければfusion/atlas transportを主因とする
5. unfused段階でも崩れれば，intrinsics・ray-depth convention・local non-Sim(3) distortionを調べる

この診断で初めて，scene-level predictorの再学習へ進むべきか，local chartを保ったATLAS型学習へ進むべきかを判断できる．

## 一次資料

- [E-RayZer paper](https://arxiv.org/abs/2512.10950)
- [E-RayZer official code](https://github.com/QitaoZhao/E-RayZer)
- [VGGT paper](https://arxiv.org/abs/2503.11651)
