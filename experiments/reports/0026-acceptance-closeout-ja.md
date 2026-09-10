> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan26 技術受理と終了

## 判定

Plan26を計算・保存証拠として`COMPLETED / ACCEPTED`とする。ゲーム判定は
`NO_FLAG`のままで、人間試遊候補ではない。raw summaryの
`PROVISIONAL_UNTIL_FULL_REGRESSION`は実行時点の不変記録なので変更せず、
このcloseoutが後続の技術受理を記録する。

## 登録と実行

- 登録commit：`0bf342f04f833505706a8564755d29217cb3f6ff`
- 単一pilot：session99923、exit0
- 単一全回帰：session80914、exit0
- worktree：`/tmp/parity-forge-plan0026.JdpTKU/checkout`
- full-suite：1,335 tests / 5,416.084s / `OK (skipped=2)`
- log SHA256：`701b5dcbbca4b36dfe5c3fe47f74363271a8134ed8863230728b3c7c8f151597`

2件のskipはいずれも明示的opt-inの実証拠再構築テスト。登録HEADは一致し、
tracked source/indexに差異はない。全10件のPlan26 screen testと、再利用した
全7件のPlan24 adapter testも全回帰log内で個別にpassした。PID50884は終了済み。

## 保存証拠

独立した保存監査とcloseout crosscheckは次を確認してPASSした。

- 70 canonical envelopes、68 publication hashes、184 source pins
  （182 Python＋active plan＋proposal）が一致。
- 固定81予定のうちexact1件とbase32局だけを実施。後段48局のresultはなく、
  全て事前規則どおりgate-closed。
- exactは`UNKNOWN_CENSORED`@100,000、外部PV replay0。
- 32局は全てGOALで決着し、draw/censor/failure0、各prefix replay1、7..19ply。
- isolated runとmain保存コピーは各70ファイルでbyte一致。正規化tree SHA256は
  `9fa3ef1340b86d500435f8711aac4f000137b50a7487fd32d32f17de09e1128c`。
- source/result drift、予期しない出力、symlink、追加candidate callはない。

## ゲーム判定の保存

T4/T4はA12/B4で固定A5..11条件を外し、T3/T3もA13/B3で固定A4..12条件を
外れた。いずれもA勝利上限を1局だけ超え、`base_pass=false`、`NO_FLAG`と
なった。後段48局は実施しない。初手T4の最善値は全て0で
SHORT_FORCED_RESULTではなく、戦術証拠はA3/B4、charged nodesは
A91,626/B84,212だった。これらはbase不通過を救わない。

exactの予算切れやT4/T3の混在勝敗を、難しさ、公平性、面白さに読み替えない。
閾値緩和、seed追加、再実行、予算増加、mirror実行はしない。詳細は
[Plan26結果](0026-two-forward-hunters-findings-ja.md)。Plan26のpilot、exact、
32局、replay、全回帰を今後再起動・再開しない。

Plan24–26の座標だけを変えるrunner/hunter調整はここで終了する。次の候補は
既存DSL内のSWAP/PUSHという別構造であり、Plan26の再試行や救済ではない。
