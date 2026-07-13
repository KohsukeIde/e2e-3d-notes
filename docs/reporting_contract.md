# E2E 3D 実験レポート保存契約

この契約は、半年後に別の研究者が「何を信じてよいか」「どの条件なら再現できるか」を判断できることを目的にします。

## 1. Claimごとにstatusを付ける

`paper`、`local-reproduction`、`local-experiment`、`inference`、`retracted` のいずれかを付けます。論文の主張と手元の観測を同じ文で混ぜません。

## 2. Analysis unitを最初に固定する

- primary unit: base scene / base sequence
- within-unit repeats: kernel、jitter、frame count、seed
- attempt-level failure: refusal、crash、missing data

反復測定はsample sizeを増やしません。集計ではsequence内を先にまとめ、その後sequence間を比較します。

## 3. 最低限保存する設定

| group | fields |
|---|---|
| model | name、parameter count、checkpoint ID / SHA、upstream commit、license |
| input | image resolution、frame sampling、frame count、crop / resize |
| geometry | c2w / w2c、OpenCV / OpenGL、intrinsics、scale、alignment |
| tracks | extractor、query数、visibility、track length、outlier rule |
| solver | backend、optimized variables、loss、damping、iteration cap、health gates |
| data | dataset、split、sequence IDs、easy / hard定義、除外理由 |
| statistics | primary unit、repeat axes、missing / refusalの扱い、test |
| runtime | Python、PyTorch / CUDA、GPU、walltime、seed |

exact revisionが回収できない場合は推測で埋めず、`unverified` としてartifact gapを残します。

## 4. Refusalを結果から消さない

最適化armが拒否されたsceneをcomplete-case集計から落とすと、成功しやすいsceneだけの評価になります。deployment utilityでは、原則としてrefusal時に `KEEP=feed-forward` を返したものとして評価します。refusal rate自体もfirst-class metricです。

## 5. Conventionを実dataで検証する

synthetic self-testやself-reprojectionだけでは不十分です。GT camera / depthのある実sequenceで、投影、positive depth、front-facing率、depth consistencyを確認します。

## 6. Figureの入力をcommitする

figureごとにCSV / JSON、生成script、captionの主張を対応づけます。論文PDFから数値を手入力した場合と、local artifactから抽出した場合を区別します。

## 7. 撤回を履歴として残す

誤ったcertificate、誤った独立sample数、未確認のiteration capなどは削除せず、次を記録します。

- 以前の主張
- 破綻させたcounterexample / audit
- 影響するfigure / conclusion
- 生き残る最小主張
- 次回の防止策

## 8. Reproducibility grade

| grade | 条件 |
|---|---|
| A | raw artifact、exact config、revision、集計scriptから全headlineを再生成可能 |
| B | headlineの縮約データとscriptはあるが、一部raw artifact / revisionが欠ける |
| C | prose / tableのみ。第三者が再集計できない |

今回のDVLT K-sweepはB、VGGT sequence-level action ceilingはC寄りのBです。DVLTのfull summary JSONはある一方、exact config dumpが縮約bundleに残っていません。action ceilingはauthoritative result文書はありますが、sequence-level再集計に必要なD2 surface JSONがローカルbundleにありません。
