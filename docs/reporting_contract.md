# E2E 3D実験レポート保存契約

この契約の目的は，半年後に別の研究者が，コードや会話履歴を知らなくても「なぜ実験したか」「何を信じてよいか」「どの条件なら再現できるか」を判断できる状態を作ることである．

## 1．結論より前に研究の問いを作る

各レポートは次の順序で書く．

1. 既存論文または実運用のどの観測が出発点か
2. その観測に対する複数の説明は何か
3. 説明ごとに，どの結果が予測されるか
4. 何を固定し，何だけを変えて説明を区別したか
5. 実験結果はどの説明を支持または棄却したか
6. その結果が従来の想定をどう変えるか

「modelの出力を改善する」「pipelineが壊れる」のような表現を，問題設定なしで使わない．何を入力し，何を出力し，どの処理を追加し，何のmetricを改善する話かを先に定義する．

## 2．ゼロコンテキストで読める本文にする

- 内部のarm名，variant名，stage名，script名，job名を本文へ出さない．
- 内部識別子の代わりに，「強い外部トラッカー」「VGGT自身のtrack」「完全対応点」のように役割を書く．
- 専門語は最初に必要になった場所で，実験上の役割とともに定義する．読者層を名指しした別primerへ説明を追い出さない．
- 略語は初出で展開し，その後も概念が曖昧なら日本語の役割名を使う．
- 本文は「だ・である」調とし，日本語の句読点は「，．」へ統一する．
- Figure captionだけでも，何を比較し，どの方向が良く，何が観測されたか分かるようにする．

## 3．Claimごとにevidence statusを付ける

`paper`，`local-reproduction`，`local-experiment`，`inference`，`retracted`のいずれかを付ける．原論文の主張と手元の観測を同じ事実として混ぜない．

## 4．Analysis unitを最初に固定する

- primary unit: base scene / base sequence
- within-unit repeats: kernel，jitter，frame count，seed
- attempt-level failure: refusal，crash，missing data

反復測定はsample sizeを増やさない．sequence内で先に集約し，その後sequence間を比較する．attempt-levelの率とsequence-levelの率を同じ数字として扱わない．

## 5．何を変え，何を固定したかを書く

因果的な解釈を行う場合，controlled swapを明示する．少なくともinput data，initialization，correspondence，solver，metricのうち，どれを固定し，どれを変更したかを書く．複数要因を同時に変えた比較から，単一要因の原因を主張しない．

正解correspondenceがquery位置，観測数，track長，空間被覆，画像間接続も変える場合，これはcorrespondence correctnessだけの交換ではなく，measurement構築経路全体の交換である．単一要因を主張するには，supportを一致させたcontrolが必要である．Solverを固定した比較から「より強いsolverでも直らない」と主張せず，solver強度のsweepを別に行う．

## 6．最低限保存する設定

| Group | Fields |
|---|---|
| Model | name，parameter count，checkpoint ID / SHA，upstream commit，license |
| Input | image resolution，frame sampling，frame count，crop / resize |
| Geometry | camera-to-world / world-to-camera，OpenCV / OpenGL，intrinsics，scale，alignment |
| Tracks | extractor，query数，visibility，track length，outlier rule |
| Solver | backend，optimized variables，loss，damping，iteration cap，health gate |
| Data | dataset，split，base sequence IDs/count，group定義，除外理由 |
| Statistics | primary unit，repeat axes，missing / refusalの扱い，test |
| Runtime | Python，PyTorch / CUDA，GPU，walltime，seed |

Exact revisionを回収できない場合は推測で埋めず，`unverified`としてartifact gapを残す．

## 7．Refusalを結果から消さない

最適化が拒否されたsceneをcomplete-case集計から落とすと，成功しやすいsceneだけが残る．deployment utilityでは，原則としてrefusal時にfeed-forward出力を返したものとして評価する．refusal rate自体もfirst-class metricである．

Sequence-levelのmetricとattempt-levelのrefusal rateを並べる場合，解析単位の違いをcaptionと本文に明記する．系列と試行を結ぶ表がなければ，同一系列で二つの現象が共起したとは主張しない．Complete-caseの事後最良値は診断上限と呼び，selector性能またはdeployment utilityと呼ばない．

## 8．Conventionを実dataで検証する

Synthetic self-testやself-reprojectionだけでは不十分である．正解cameraとdepthのある実sequenceで，projection，positive depth，front-facing率，depth consistencyを確認する．内部再投影が小さいだけでは，ground-truth conventionとの一致を証明できない．

## 9．Figureの入力をcommitする

各figureにCSVまたはJSON，生成script，captionのclaimを対応づける．論文PDFから手入力した数値と，local artifactから抽出した数値を区別する．Figureは結果だけでなく，実験で固定したものと変更したものを説明するためにも使う．

各定量figureのcaptionには，入力fileとSHA-256，対象subset，analysis unit，missingとrefusalの扱い，集約方法，metricの良い方向，生成commandを書く．異なるanalysis unitを一つのfigureへ置く場合は，panel間のpaired relationを意味しないことを明示する．数値入力のない概念図は，生成scriptとcommandを示す．

## 10．何が非自明かを明示する

結果の列挙で終わらず，次を一段落で書く．

- 実験前に自然だった予想
- その予想と両立しない観測
- controlled comparisonによって除外できた説明
- まだ除外できない説明
- 次のmethod choiceがどう変わるか

「精度が上がった」「失敗率が高かった」だけではnon-trivialな知見にならない．どのdefault assumptionを変える結果かを示す．

一つのcheckpoint，一つのdataset，学習範囲外のstress testから，architecture一般またはmethod class一般の性質へ広げない．観測したcheckpoint，dataset，反復範囲をclaimとfigure captionへ残す．

## 11．撤回を履歴として残す

誤ったcertificate，誤った独立sample数，未確認のiteration capは削除せず，次を記録する．

- 以前の主張
- 破綻させたcounterexampleまたはaudit
- 影響するfigureとconclusion
- 生き残る最小主張
- 次回の防止策

## 12．Reproducibility grade

| Grade | 条件 |
|---|---|
| A | raw artifact，exact config，revision，集計scriptから全headlineを再生成可能 |
| B | headlineの縮約dataとscriptはあるが，一部raw artifactまたはrevisionが欠ける |
| C | proseまたはtableのみで，第三者が再集計できない |

今回のDéjà View反復実験はB，VGGTの系列単位診断はC寄りのBである．Déjà Viewのfull summary JSONはあるがexact config dumpが欠ける．VGGT診断には訂正版summaryがあるが，系列単位の再集計に必要な一部raw JSONが欠ける．
