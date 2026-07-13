# [Experiment] VGGT後段は「追加反復」より「対応点修復」が支配する

> Snapshot: 2026-07-10 / external review後の訂正版
> Evidence: `local-reproduction` + `local-experiment`
> Status: findingsは有効、V1 convergence certificateは撤回、REPAIR methodは未実装

## TL;DR

VGGT系のfeed-forward 3Dを後段で改善する問題は、単にoptimizationを追加する問題ではありませんでした。

- hard sequencesではFF poseがすでに良い（median AUC@30 = 0.933）のに、learned-track BAは外部trackerでも57.5%、VGGT own tracksでは87.5%拒否される。
- perfect correspondenceを使うoracle action ceilingは24/24 sequencesで改善し、best actionは `REPAIR=21 / REFINE=3 / KEEP=0`、median gainは+0.051 AUC。
- Déjà ViewはK=20付近にsweet spotがあるが、K=64でDepth AbsRelがK=16の約17.2倍、Pose AUC@30が0.954→0.021へ崩れる。
- よって安全な後段は、blind iterationではなく `KEEP / REFINE / REPAIR` を選び、REFINEはtrue GN/LM、価値の中心はcorrespondence REPAIRに置くべき。

![DVLT K sweep](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/dvlt_k_sweep.png?raw=1)

## 3Dを専門にしていないCV研究者向けの前提

multi-view 3Dでは、異なる画像のどのpixelが同じ3D点かというcorrespondence / trackが、camera poseと3D点を拘束します。BAはその対応点を固定してreprojection errorを下げるoptimizerです。したがって、初期poseが良くてもtrack graphが壊れていれば、BAを長く回しても直りません。

今回のactionは次です。

- `KEEP`: feed-forward結果を返す
- `REFINE`: trackを固定してGN / LMでpose・pointを改善
- `REPAIR`: track自体を再割当・追加・棄却してから解く

詳しい用語とcamera conventionは [`docs/e2e_3d_primer.md`](../blob/main/docs/e2e_3d_primer.md) にあります。

## 実験設定

### VGGT differential

同じVGGT-1B feed-forward initializationとBA backendに対して、track sourceだけを交換しました。

| arm | track source | 意味 |
|---|---|---|
| FF | なし | feed-forward baseline |
| a1 | VGGSfM external tracker: ALIKED + SuperPoint | 公開 `+BA` pipelineに近いstrong baseline |
| a2 | VGGT own track head | model-native pipeline |
| b | GT pose / depthから投影したoracle track | perfect-correspondence ceiling |
| b-GTinit | oracle track + GT init | solver / init ceiling |

設定の主要部:

- model: `facebook/VGGT-1B`、load 1024 px、model 518 px
- tracks: max 4096 queries、8 query frames、visibility 0.2
- BA: fixed intrinsics、PINHOLE、OpenCV w2c、soft-L1 4 px
- gates: max reprojection 12 px、track length≥2、inliers/frame≥16
- metric: gauge-free pairwise relative Pose AUC@30
- base sequences: 29（easy: CO3D 12 + Replica 3、hard: ETH3D 13 + TartanAir 1）
- repeated measures: robust kernel、jitter 5、10/30 frames。独立Nには数えない

注意: VGGT論文・公式コードの `+BA` はVGGT own track headではなく外部trackerを使います。a1とa2は別物です。

### Déjà View / DVLT reproduction

- model: released `nvidia/dvlt`, 117M
- official repo / evaluator、repo本体は未改変
- Python 3.12、PyTorch 2.5.1、CUDA 12.4
- ETH3D 13 sequences、同一sequenceを全Kで評価
- K: `{8,12,16,20,24,32,48,64}`
- read-only hook、K=16 hook/no-hook output deviation = 0
- `K>16` は学習範囲より多いtied-block applications。より細かい `[0,1]` time gridであり、「整数step 17以降」ではない

## Result 1: DVLTのKはsafe anytime knobではない

| K | Pose AUC@30 ↑ | Depth AbsRel ↓ | Delta1 ↑ |
|---:|---:|---:|---:|
| 8 | 0.865 | 0.0325 | 0.986 |
| 16 | 0.954 | 0.0182 | 0.997 |
| 20 | **0.957** | **0.0180** | 0.997 |
| 24 | 0.956 | 0.0184 | 0.997 |
| 32 | 0.938 | 0.0231 | 0.996 |
| 48 | 0.786 | 0.0529 | 0.980 |
| 64 | **0.021** | **0.3126** | **0.484** |

K=20–24まではgrace zoneですが、K=32からK=16基準で悪化し、K=64で急崩壊します。

state normはK≤16の隣接stepの84.1%でnondecreasingですが、全stepが単調増加するsequenceは0%です。有限horizon proxyは768 channels中 `norm=554 / max_abs=389 / union=567`。これはunbounded divergenceの証明ではありません。

## Result 2: Easyでもoracle gapは小さいがnonzero

- a1 external: 13/14 positive、median +0.0244
- a2 own track: 15/15 positive、median +0.0325

external trackerはown trackより良いもののoracle parityではありません。

## Result 3: Hardではgood initでもtrack pipelineが壊れる

hard-tier FF-init medianは0.933ですが、attempt-level refusalはa1で57.5%、a2で87.5%でした。

![Correspondence diagnostics](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/correspondence_diagnostics.png?raw=1)

この組合せは「pose initializationを改善すればBAが直る」という説明に反します。measurement graphが壊れているsceneでは、track固定refinementは問題のある情報を強く信じるだけです。

## Result 4: Method価値はREPAIRに集中する

![Oracle action ceiling](https://github.com/KohsukeIde/e2e-3d-notes/blob/main/figures/oracle_action_ceiling.png?raw=1)

| subset | n | median gain | positive | oracle-best action |
|---|---:|---:|---:|---|
| all | 24 | +0.051 | 24/24 | REPAIR 21 / REFINE 3 / KEEP 0 |
| easy | 15 | +0.051 | 15/15 | REPAIR 14 / REFINE 1 / KEEP 0 |
| hard | 9 | +0.049 | 9/9 | REPAIR 7 / REFINE 2 / KEEP 0 |

これはperfect tracksを使った上限です。realistic repairが+0.051を達成する、という主張ではありません。ただしselectorを作る価値があるかというStage-1 go/no-goには十分で、次のmake-or-breakは「real repairがこのceilingの何割を回収できるか」です。

## Result 5: track-causal ≠ geometrically useful

失敗したV1–V3 refinerから次が分かりました。

- V1: track-blindで、OOD ETH3Dでは良いFF initを悪化させた。
- V2: identity gateは悪化を抑えたが、trainingにcounterfactual pairsが無くcontrastive lossが0だった。
- V3: counterfactual augmentationでtrack sensitivityは出たが、pose delta targetがtrue GN stepではなくmean residualから作ったheuristicだったため、geometry valueは出なかった。

次の設計では、networkにraw SE(3) deltaを回帰させず、weights / damping / assignment / action utilityを予測させ、updateはtrue projection Jacobianで解くべきです。

## 撤回・訂正

1. `510 entries / 136 pairs` を独立Nとして扱った統計は撤回。primary unitはbase sequence。
2. V1の `certified non-divergence` は撤回。monotonicity certificateをplain Picard solverへ誤適用していた。
3. `88% breakdown` はa2固有。a1は57.5%。
4. `a1≈oracle parity` は撤回。sequence-level gapは小さいがnonzero。
5. refusalを落としたcomplete-case utilityは不適切。refusal時はKEEP=FFとして評価する。
6. V3はgeometric stepを学習したのではなく、track変更への反応を学習しただけ。

## 実装で再利用できる注意

- camera conventionはsynthetic / self-reprojectionだけでなくGT camera/depthで検証する。
- internally coherentでもCO3D `A@R` vs `A@R.T` の誤りで約23°ずれ得る。
- health-gate refusalとnumerical divergenceを分ける。
- iteration capは設定値をlogするだけでなく、実際にbindしたことをassertする。
- review bundleをextractし、config dumpとraw集計入力が本当に含まれるか確認する。

## 現在の仮説と次の実験

`Keep / Refine / Repair: Dual-Certified Selective Proximal Geometry`

1. KEEPをfirst-class actionにする。
2. REFINEはlearned weights / damping + true GN/LM + trust-region acceptance。
3. REPAIRはsoft assignment、dustbin、cycle consistency、influence-guided rematching。
4. inner certificateは実装と一致するgeometric energy descent。
5. outer certificateはcalibrated non-harm。全actionのlower bound≤0ならKEEP。

未確認:

- real REPAIRがoracle ceilingの何割を回収するか
- VGGT以外のπ³ / MapAnythingでも同じfailure structureか
- leave-one-dataset-outでaction selectorのnon-harmが校正できるか

## Reproducibility

```bash
pip install -r requirements.txt
make check
```

- full report: [`reports/2026-07-10-vggt-dvlt-correspondence.md`](../blob/main/reports/2026-07-10-vggt-dvlt-correspondence.md)
- raw DVLT summary: [`data/raw/dvlt_r1_r2_r3_summary.json`](../blob/main/data/raw/dvlt_r1_r2_r3_summary.json)
- sequence summary: [`data/t36_sequence_summary.json`](../blob/main/data/t36_sequence_summary.json)
- reporting contract: [`docs/reporting_contract.md`](../blob/main/docs/reporting_contract.md)

Artifact gap: DVLT exact `config_dump.json` とVGGT sequence re-aggregation用 `outputs/d2/surface/*.json` は縮約bundleに残っていません。現snapshotのreproducibility gradeはBです。

## Primary sources

- [VGGT paper](https://arxiv.org/abs/2503.11651) / [official code](https://github.com/facebookresearch/vggt)
- [Déjà View paper](https://arxiv.org/abs/2605.30215) / [official code](https://github.com/nv-tlabs/dvlt) / [checkpoint](https://huggingface.co/nvidia/dvlt)
- [π³ official code](https://github.com/yyfz/Pi3)
- [MapAnything official code](https://github.com/facebookresearch/map-anything)
