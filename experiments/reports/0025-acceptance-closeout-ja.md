> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan25 技術受理と終了

## 判定

Plan25を計算・保存証拠として`COMPLETED / ACCEPTED`とする。ゲーム判定は
`NO_FLAG`のままで、人間試遊候補ではない。raw summaryの
`PROVISIONAL_UNTIL_FULL_REGRESSION`は実行時点の不変記録なので変更せず、
このcloseoutが後続の技術受理を記録する。

## 登録と実行

- 登録commit：`8b15e1ea44831e5af45d73f27f3c7c4af4be3e3b`
- 単一pilot：session16352、exit0
- 単一全回帰：session68935、exit0
- worktree：`/tmp/parity-forge-plan0025.gvR2Wy/checkout`
- full-suite：1,325 tests / 5,160.407s / `OK (skipped=2)`
- log SHA256：`93bd4ca03d2f9296ed1c96ebe191537df420ce4ba6430e06a3d33593eb5fbefb`

2件のskipはいずれも明示的opt-inの再構築テスト。登録HEADは一致し、tracked
source/indexに差異はない。全10件のPlan25 screen testと、再利用した全7件の
Plan24 adapter testも全回帰log内で個別にpassした。PID35740は終了済み。

## 保存証拠

独立監査は次を確認してPASSした。

- 70 canonical envelopes、68 publication hashes、182 source pins
  （180 Python＋active plan＋proposal）が一致。
- 固定81予定のうちexact1件とbase32局だけを実施。後段48局のresultはなく、
  全て事前規則どおりgate-closed。
- exactはUNKNOWN_CENSORED@100,000、外部PV replay0。
- 32局は全てGOALで決着し、draw/censor/failure0、各prefix replay1、7..19ply。
- isolated runとmain保存コピーは各70ファイルでbyte一致。正規化tree SHA256は
  `75f9a89fb32fc71d672319267581057745c23a7a2ef3b8e800e1a4327223f446`。
- source/result drift、予期しない出力、symlink、追加candidate callはない。

## ゲーム判定の保存

T4/T4はA7/B9で固定5..11条件を通過した。T3/T3はA15/B1で固定4..12条件を
外れ、base_pass=false、`NO_FLAG`となった。後段48局は実施しない。初手T4の
最善値は全て0でSHORT_FORCED_RESULTではなく、戦術証拠はA3/B9、charged
nodesはA92,143/B86,598だった。これらはbase不通過を救わない。

exactの予算切れやT4の混在勝敗を、難しさ、公平性、面白さに読み替えない。
閾値緩和、seed追加、再実行、予算増加、mirror実行はしない。詳細は
[Plan25結果](0025-staggered-hunters-findings-ja.md)。Plan25のpilot、exact、
32局、replay、全回帰を今後再起動・再開しない。

次の横並び配置は、Plan25の結果・traceと登録前bounded AND/OR露出を開示した
別hash・別plan・fresh seedの開発候補としてのみ扱う。
