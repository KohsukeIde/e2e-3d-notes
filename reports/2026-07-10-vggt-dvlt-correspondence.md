# VGGT / Déjà View実験から得た訂正版知見

Snapshot: 2026-07-10
Status: local reproduction + local experiment、外部review後の訂正版
Scope: VGGT-1B後段のcorrespondence / BA診断、DVLT K-sweep、失敗したrefiner V1–V3

## Executive summary

最も重要な結論は、feed-forward 3Dの後処理を「最適化を回すか、回さないか」で捉えるのが粗すぎることです。難しいsceneではVGGTのfeed-forward poseがすでに良くても、対応点が壊れているためBAが拒否されます。完全対応点を使えるoracle action ceilingでは24/24 sequenceが改善し、最良actionは21/24でREPAIR、3/24でREFINE、KEEPは0でした。価値は追加反復よりcorrespondence repairに集中しています。

一方、looped modelのDéjà Viewは、学習範囲内K=8–16から少し外れたK=20–24までは改善・plateauしますが、K=32から悪化し、K=64でDepth AbsRelがK=16の約17.2倍、Pose AUC@30が0.954から0.021へ崩れました。したがって、`K` は少なくともreleased checkpoint上では安全なanytime knobではありません。

![DVLT K sweep](../figures/dvlt_k_sweep.png)

## 1. 何を比較したか

### VGGT diagnostic

固定したVGGT-1Bのfeed-forward geometryを初期値として、track sourceだけを入れ替え、同じBA backendで比較しました。

| arm | correspondence | 役割 |
|---|---|---|
| FF | なし | feed-forward baseline |
| a1 | VGGSfM external tracker、ALIKED + SuperPoint | 公開 `+BA` pipelineに近い強いlearned baseline |
| a2 | VGGT自身のtrack head | integrated modelの診断 |
| b | GT pose / depthから投影したoracle tracks | perfect-correspondence recoverability ceiling |
| b-GTinit | oracle tracks + GT init | solver / initialization ceiling |

重要な設定差として、VGGTの論文・公式 `demo_colmap.py` の `+BA` はVGGT自身のtrack headではなく外部trackerを使います。a1とa2を分けないと、「published +BA」と「model-native tracks」の性質を混同します。

### DVLT reproduction

公開 `nvidia/dvlt` checkpointと公式evaluation stackを使い、ETH3D 13 sequencesで `K={8,12,16,20,24,32,48,64}` を評価しました。K=16でhook有無のoutput一致を確認してから、recurrent blockのstate normをread-only hookで記録しました。

`k_sampling=linspace` なので、K>16は「16以降の整数depthを実行」することではありません。同じtied blockを、`[0,1]` 上のより細かいtime gridで学習範囲より多く適用するartifact testです。

## 2. 具体的な設定

### Model / environment

| item | VGGT diagnostic | DVLT reproduction |
|---|---|---|
| model | `facebook/VGGT-1B` | `nvidia/dvlt`, 117M |
| Python | 3.12 | 3.12 |
| PyTorch | VGGT用ABCI環境 | 2.5.1 |
| CUDA | cluster環境 | 12.4 |
| execution | ABCI, single-GPU PBS job | ABCI `rt_HG`, 1 GPU, walltime 3h |
| seed | 20260703 | 20260703 |

DVLTのexact upstream commit / checkpoint revisionは実行時 `config_dump.json` に保存する設計でしたが、縮約review bundleにはsummary JSONしか残っていません。ここは再現artifactの欠落であり、推測値は書きません。

### VGGT / tracker / BA

- image load resolution: 1024、model resolution: 518
- track budget: 4096、query frames: 8、visibility threshold: 0.2
- a1 keypoint extractor: `aliked+sp`、fine tracking on
- intrinsics: primaryでは固定
- camera model: PINHOLE、OpenCV world-to-camera convention
- robust loss: soft-L1、scale 4 px
- max reprojection error: 12 px
- minimum track length: 2、minimum inliers per frame: 16
- BA maximum iterations: 80、function / gradient / parameter tolerance: 1e-10
- pose metric: pairwise-relative RRA/RTA AUC@30、gauge-free

### Data / analysis unit

29 base sequencesです。

- easy: CO3D 12 + Replica 3
- hard: ETH3D 13 + TartanAir 1
- kernel、jitter、10/30 framesはwithin-sequence repeated measures
- action ceilingは必要なarmが揃った24 sequences
- TartanAirはpaired complete-caseがほぼ0であり、easy oracle-gapの一般化には使っていません

## 3. Non-trivial findings

### F1. Déjà ViewのKにはsweet spotがあり、追加反復は安全ではない

| K | Pose AUC@30 ↑ | Depth AbsRel ↓ | Delta1 ↑ |
|---:|---:|---:|---:|
| 8 | 0.865 | 0.0325 | 0.986 |
| 16 | 0.954 | 0.0182 | 0.997 |
| 20 | **0.957** | **0.0180** | 0.997 |
| 24 | 0.956 | 0.0184 | 0.997 |
| 32 | 0.938 | 0.0231 | 0.996 |
| 48 | 0.786 | 0.0529 | 0.980 |
| 64 | **0.021** | **0.3126** | **0.484** |

悪化開始は明示したK=16基準でK=32です。K=64のAbsRel比は17.16倍です。これは「Kを増やせば徐々に悪化」という単純なcurveではなく、短いgrace zoneの後に急崩壊する形です。

state normについては、K≤16の隣接stepの84.1%がnondecreasingでしたが、全stepで単調増加したsequenceは0%でした。また、768 channels中 `norm=554`、`max_abs=389`、union `567` が事前定義した有限horizon proxyを満たしました。これはunbounded divergenceの証明ではなく、released artifactの有限K診断です。「論文のfew channelsは過小評価」と強く主張するのも避けます。

### F2. Easyではoracle gapは小さいがゼロではない

sequence-levelで、oracleとの差は次の通りでした。

- a1 external tracker: 13/14 positive、median +0.0244 AUC
- a2 VGGT track head: 15/15 positive、median +0.0325 AUC

external trackerはmodel-native trackより良いものの、`a1≈oracle parity` ではありません。以前のentry-level集計から得た「a1≈parity」は撤回されています。

### F3. Hardではposeよりcorrespondence graphが先に壊れる

hard-tierのFF-init median Pose AUC@30は0.933と高い一方、BAのrefusalはattempt-levelで次でした。

- a1 external tracker: 57.5%
- a2 VGGT own tracks: 87.5%

つまり「初期geometryが悪いからoptimizerが失敗する」だけでは説明できません。good-init / bad-tracks というcornerがあり、track固定のrefinerをさらに強くしても、そもそも観測graphが使えないsceneは直りません。

![Correspondence diagnostics](../figures/correspondence_diagnostics.png)

### F4. Oracle action ceilingはREPAIRに集中する

各sequenceで `KEEP=FF`、`REFINE=max(a1,a2)`、`REPAIR=oracle BA` の最良を選ぶと次になりました。

| subset | n | median gain | positive | best action |
|---|---:|---:|---:|---|
| all | 24 | +0.051 | 24/24 | REPAIR 21 / REFINE 3 / KEEP 0 |
| easy | 15 | +0.051 | 15/15 | REPAIR 14 / REFINE 1 / KEEP 0 |
| hard | 9 | +0.049 | 9/9 | REPAIR 7 / REFINE 2 / KEEP 0 |

これはperfect correspondenceを使ったoracle上限であり、real repairの達成値ではありません。ただし、selectorやpost-processingに約0.05 AUCのpotentialがあり、その大半が「同じtrackで解き直す」REFINEではなく「trackを変える」REPAIRにあることを示します。

![Oracle action ceiling](../figures/oracle_action_ceiling.png)

### F5. Track-causalであることとgeometrically usefulであることは別

V1–V3のrefiner失敗は、method設計上の有用なnegative resultでした。

| variant | 観測 | 学び |
|---|---|---|
| V1 | track-blind、ETH3D OODでFFを大きく悪化 | geometry priorへのshortcutを疑う |
| V2 | identity gateで悪化は抑えたがtrack-blind | counterfactual pairがtrainingに無く、contrastive lossが実質0 |
| V3 | track sensitivityは改善したがpose価値は負 | targetがtrue GN stepでなくmean residualから作ったheuristic delta |

V3は「trackが変わるとoutput deltaも変わる」ことは学びましたが、「reprojectionを減らす正しいdelta」を学んだわけではありません。次のmethodではnetworkにraw 6D pose deltaを回帰させず、observation weights、covariance、damping、assignment、action utilityを予測させ、更新自体はtrue projection JacobianからGN/LMで計算するのが自然です。

## 4. 撤回された主張

### R1. 510 entries / 136 pairsを独立sampleとした統計

kernel、jitter、frame countの反復を独立sceneのように数えていました。primary unitはbase sequenceです。すべてsequence内で先に集約する必要があります。

### R2. V1の「certified non-divergence」

certificateは `sym(I-W)` のstrong monotonicityを確認していましたが、実装solverはplain Picard iterationでした。monotone operatorをproper splittingで解く保証をPicardへ移せません。reviewerのskew-symmetric counterexampleではcertificateを通る一方、Picard Jacobianのspectral radiusが1を超えます。したがってV1のconvergence certificateは無効です。

### R3. 88% breakdownを一般のlearned tracker結果とした表現

87.5%はa2固有です。a1は57.5%でした。tracker sourceを必ず分けます。

### R4. Refusalを除いたcomplete-case utility

失敗sceneを落とすと、optimizationが成功しやすいsubsetだけを評価します。deployment endpointではrefusal時にKEEP=FFを返すutilityへ変える必要があります。

## 5. 実装・評価で得た再利用可能な罠

1. CO3DのPyTorch3D row-vector conventionで `A@R` と `A@R.T` を取り違えると、内部reprojectionは約2 pxでもGT poseから約23°ずれる。self-consistency testだけでは検出不能。
2. TartanAirのfar-field / sky depthは非常に大きく、load時にinvalid化しないとoracle samplingまで汚染する。
3. wide baselineでin-bounds率が低いのはconvention errorとは限らず、FOV exit / occlusionの可能性がある。signed depth residualで切り分ける。
4. solver iteration capをlogしていても、backend fallbackで実際には同じdefault capを使う場合がある。capがbindしたことをassertする。
5. health gateが止めたrunを「diverged」と呼ばない。pre-BA refusal、post-BA residual rejection、objective increaseを分ける。
6. exact configを生成しただけでは不十分で、review bundleに含まれたかをextract後に検査する。

## 6. 現在のmethod仮説

次の形を **Keep / Refine / Repair: Dual-Certified Selective Proximal Geometry** と呼んでいます。

1. `KEEP`: FFを返すfirst-class action
2. `REFINE`: learned weights / damping + true GN/LM + trust-region acceptance
3. `REPAIR`: soft assignment、dustbin、cycle consistency、high-influence observationだけ再match
4. inner certificate: 実装したgeometric energyのdescent
5. outer certificate: calibrated lower confidence boundが正のactionだけ選び、それ以外はKEEP

次のmake-or-breakは、realistic REPAIRがoracle +0.051の何割を回収できるかです。π³ / MapAnythingのmulti-architecture結果はまだなく、VGGT固有かclass-levelかも未確定です。

## 7. 一次資料

- [VGGT paper](https://arxiv.org/abs/2503.11651)
- [VGGT official code](https://github.com/facebookresearch/vggt)
- [Déjà View paper](https://arxiv.org/abs/2605.30215)
- [DVLT official code](https://github.com/nv-tlabs/dvlt)
- [DVLT checkpoint](https://huggingface.co/nvidia/dvlt)
- [π³ official code](https://github.com/yyfz/Pi3)
- [MapAnything official code](https://github.com/facebookresearch/map-anything)

## 8. Reproducibility status

- DVLT plot: `data/raw/dvlt_r1_r2_r3_summary.json` から再生成可能
- VGGT action / refusal plot: external review後のauthoritative sequence summaryから再生成可能
- exact DVLT checkout / checkpoint SHA: reduced bundleに欠落
- VGGT sequence-level raw re-aggregation: D2 surface JSONがlocal bundleに欠落
- overall grade: B（headline dataとscriptはあるが、完全なraw replayには不足）
