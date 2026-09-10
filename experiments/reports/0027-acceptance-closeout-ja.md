> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan27 技術受理と終了

## 判定

Plan27を計算・保存証拠として`COMPLETED / ACCEPTED`とする。ゲーム判定は
`NO_FLAG`のままで、人間試遊候補ではない。raw summaryの
`PROVISIONAL_UNTIL_FULL_REGRESSION`は実行時点の不変記録なので変更せず、
このcloseoutが後続の技術受理を記録する。

## 登録と実行

- 登録commit：`ca3451bb478aed518e34ff5e69ad362f64771d69`
- 単一production pilot：session67283、PID71418、exit0
- 単一全回帰：session78528、PID70567、exit0
- worktree：`/tmp/parity-forge-plan0027.mTxbu8/checkout`
- full-suite：1,348 tests / 5,351.812s / `OK (skipped=2)`
- log SHA256：`107af4476fa1e6b6d2beaa1509cf47aa43ee2e56a53862838085b600fcbb7253`

2件のskipはいずれも明示的opt-inの実証拠再構築test。登録HEADとGit tree
`a4fcc24f4db41e3ec2dd05a88d482f2db908dee5`は一致し、tracked source/indexに
差異はない。Plan27 screenの13件と再利用Plan24 adapterの7件も、全回帰
log内で個別にpassした。PID70567とPID71418は終了済み。

18:27:31 JSTの最初のshell起動は`scripts`のimportに失敗したが、
`run_pilot`、output予約、候補読込、exact、game、replayより前に終了した。
従ってproduction attemptには数えない。保存launcher log SHA256は
`63b0dfefcf188ac891442e6cd9e84a1ecd5673ae64920b7487ddc837066358e6`。

## 保存証拠

独立保存監査とcloseout crosscheckは次を確認してPASSした。

- 70 canonical envelopes、68 publication hashes、186 source pins
  （184 Python＋登録時active plan＋proposal）が一致。
- 固定81予定のうちexact1件とbase32局だけを実施。後段48局は
  全て事前規則どおり`NOT_STARTED_GATE_CLOSED`。
- exactは`UNKNOWN_CENSORED`@100,000、外部PV replay0。
- 32局は全て`GOAL`で決着し、A24/B8、draw/censor/failure0、
  各prefix replay1、7..22ply。
- isolated runとmain保存コピーは各70ファイル、585,665 bytesでbyte一致。
  symlinkはない。正規化run-tree SHA256は
  `11af60946eeb862387ffd820bd80b029ffbcafcc933ef6de57aeb6b109b7e7ab`。
- raw-SHA map digestは
  `8523cc4579f4261b918d2701687b7986b07abe0d26c2a357d24bffaf922d59d1`、
  summary raw SHA256は
  `9c40cd83898e197f36e250189762e99938dc9bba725a9b78d3a2931486aebdf3`。
- source/result drift、予期しない出力、追加candidate callはない。

## ゲーム判定の保存

T4/T4はA12/B4で固定A5..11条件を1勝超過してfail。T3/T3はA12/B4で
固定A4..12の上端をpassした。よって`base_pass=false`、`NO_FLAG`で、
後段48局は実施しない。charged nodesはA37,321/B33,260、保存された
495遷移は全てPhiを1..3減少させた。

記述的作用証拠はA-SWAP9局/9回、B-PUSH5局/6回、T4水平選択は
A15局/B16局、tactical witnessはA8局/B3局。これらはbase不通過を救済しない。
exact UNKNOWN、混在勝敗、作用証拠を、難しさ、公平性、面白さに読み替えない。
rawの`fairness_established`、`hardness_established`、`fun_established`は
全てfalseのままである。詳細は
[Plan27結果](0027-three-currents-findings-ja.md)。

Plan27のpilot、exact、32局、replay、全回帰を今後再起動・再開・補充しない。
Plan28はPlan27の再試行ではなく、両者の作用とgoalを変えた別の固定研究問いである。
