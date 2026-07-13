# Contributing

新しい知見は原則としてGitHub Issueへ保存し，再利用する数値，図，生成scriptをrepositoryへ追加する．

## 新しい実験Issueの最低要件

1. 既存研究または実運用から生じた背景
2. 一つのresearch questionと，競合する複数のhypothesis
3. 仮説ごとの予測
4. 実験で固定したものと変更したもの
5. Model，checkpoint，upstream commit，license
6. Dataset，split，base sequence数，反復測定の軸
7. Camera convention，scale，gauge，alignment
8. Metricの定義と良い方向
9. Refusal，crash，missing outputの扱い
10. 強いcontrol，failure case，撤回事項
11. Raw artifact，集計script，figure生成script
12. 何が非自明で，次のmethod choiceをどう変えるか

`.github/ISSUE_TEMPLATE/experiment-report.yml`は，この順序を実験Issueへ展開する．

## 文章

- 本文は「だ・である」調で書く．
- コードや内部文書を知らない読者を前提とする．
- 内部のarm名，variant名，script名は本文へ出さず，役割を自然言語で書く．
- 専門用語の説明を別primerへ追い出さず，最初に必要となる場所へ組み込む．
- 結果だけを先に置かず，背景，対立仮説，識別実験，結果，含意の順で構成する．
- Sequence-level metricとattempt-level failureを同一系列の共起として扱わない．
- 正解measurementが点数や被覆も変える場合は，対応精度だけの効果と呼ばない．
- Complete-caseの事後上限，selector性能，deployment utilityを別のclaimとして扱う．

## Figureとdata

- 論文figureのscreenshotより，raw valueから再生成したfigureを優先する．
- CSVまたはJSONへprovenanceとanalysis unitを残す．
- Checkpoint，dataset本体，上流licenseに抵触するassetをcommitしない．
- Repeated measuresを独立sample数として数えない．
- 無効になった結論は削除せず，`retracted`と理由を追記する．
- Captionへ入力data，SHA-256，subset，analysis unit，集約方法，metricの方向を書く．
