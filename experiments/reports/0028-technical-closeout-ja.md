> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan28 技術closeout：全回帰はホスト再起動で未成立

## 判定

Plan28を`COMPLETED / GAME_NO_FLAG / TECHNICAL_ACCEPTANCE_FAILED /
FULL_REGRESSION_INTERRUPTED_BY_HOST_REBOOT`として閉じる。
ゲーム判定はpilotで既に`NO_FLAG`であり、人間試遊候補ではない。登録済みの
単一全回帰はホスト再起動までに完了せず、最終`Ran`/`OK`/exitを保存できなかった。
事前規則どおり全回帰を再実行せず、技術受理を成功扱いにしない。

## 保存済みpilot証拠

- 登録commit：`b0d9b4b7840833ecbe564cbf81eba7ed4ad79a9e`
- Git tree：`ed9cd2c98ea7c93b82221d1b399cdf628b71a72f`
- production pilot：session42229 / PID94917 / exit0
- exact：`UNKNOWN_CENSORED`@100,000、外部PV replay0
- base：32/32 COMPLETE、A7/B25、draw/censor/failure0、12..29ply
- H3/H3：A4/B12、T3/T3：A3/B13
- 終局：GOALはA0/B1、NO_LEGAL_ACTIONは31局
- final48：`NOT_STARTED_GATE_CLOSED`
- disposition：`NO_FLAG`

二つのsaved-only監査は、70 canonical envelopes、68 publication hashes、
190 source pins、799遷移を追加game/solver/replayなしで照合した。mainのraw copyも
隔離runとbyte-identicalだった。pilot結果の詳細は
[Plan28所見](0028-two-current-cross-weave-findings-ja.md)に保存済みである。

## 完了しなかった全回帰

唯一の全回帰session24610 / PID94928は、登録済みclean worktree
`/tmp/parity-forge-plan0028.0JISrP/checkout`から2026-09-06 21:43:55 JSTに
開始した。22:50:38 JST、開始後1:06:32の時点でもPython processは存在し、
ログは1,103行、
`test_selected_five_stabilizer_shards_match_independent_oracles`の実行途中で、
最終summaryへ達していなかった。

ホストの現在のboot recordは2026-09-06 22:55:35 JSTであり、開始から約
1時間11分40秒後に再起動したことを示す。再起動後はPID94928と親processが
存在せず、一時worktreeと`full-suite.log`も消失した。task session記録にも
Plan28 suiteの最終`Ran`/`OK`はなく、実際の完了・exit0を立証できない。
途中までfailure表示を観測しなかったことを、全回帰PASSへ読み替えない。

これはゲームの`UNKNOWN`やdrawではなく、技術受理を成立させない運用上の
中断である。pilotのimmutable raw結果を変更せず、追加suite、追加pilot、
追加exact、追加game、追加replay、seed補充、閾値変更をしない。

## 次の境界

Plan28のゲームは数値gateとGOAL gateの両方を既に外しているため、全回帰を
やり直しても人間候補にはならない。ここで閉じ、次番号Plan29ではacceptedな
既存parser/engine/agentだけを使う固定4候補の安いpreselectionを先に行う。
Plan28固有screenを後続の根拠として再利用しない。
