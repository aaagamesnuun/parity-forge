> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0028 二潮流の交差織り：本番pilot所見

## 結論

ゲーム判定は `NO_FLAG`。人間の試遊候補ではない。登録済みの固定base
32局はすべて有限・決着・監査可能だったが、T3/T3の勝数条件を1勝だけ
下回り、さらに明示的な接続GOALは32局中1局しか起きなかった。後段48局は
予定どおり `NOT_STARTED_GATE_CLOSED` とし、再試行、seed追加、閾値緩和、
配置やgoalの救済は行わない。

これは「不公平が証明された」という結果ではない。固定された浅い既存agent
screenで、人間の注意を使うための最低条件を満たさなかったという限定結果である。

## 登録と実行境界

- 登録commit：`b0d9b4b7840833ecbe564cbf81eba7ed4ad79a9e`
- Git tree：`ed9cd2c98ea7c93b82221d1b399cdf628b71a72f`
- protocol：`plan0028-two-current-cross-weave-v1`
- clean detached worktree：`/tmp/parity-forge-plan0028.0JISrP/checkout`
- source pins：190（Python 188、active plan 1、proposal 1）
- pin-map SHA256：
  `a21478ba8a66288790f7abcaa7cc42e9530ba6578e230c56a067f8ffb33f7e33`
- pilot session 42229 / Python PID 94917：exit 0、終了済み
- 開始記録：2026-09-06 21:43:49.168 JST
- 最終attempt記録：2026-09-06 21:44:50.699 JST
- 観測資源：64.92秒 real、54.27秒 user、11.05秒 sys、最大RSS
  234,127,360 bytes。これらは科学的gateではない。

manifestは計算前にexact 1件と条件付き80局、計81attemptを全て公開した。
実際に開始したのはexact 1件とbase 32局だけである。pilot内でLLMは使って
いない。登録ソースからの追加pilot、追加exact、追加game、追加replayはない。

## exactと無引分条件

既存exact solverは100,000 stateで `UNKNOWN_CENSORED`、外部PV replayは0。
これは難しさや公平性の証拠ではない。事前の整数potential証明はそのまま成立し、
全合法手でPhiが1または2減るため、全ての合法playは50ply以内にA/Bいずれかの
勝ちで終わる。保存32局にもdraw、PLY_LIMIT、game censor、failureはなかった。

## 固定base 32局

| 条件 | A勝 | B勝 | 判定 |
|---|---:|---:|---|
| H3/H3、seed 1100..1115 | 4 | 12 | 固定範囲4..12の下端でPASS |
| T3/T3、seed 1100..1115 | 3 | 13 | A勝4..12に1勝不足 |

全体はA 7勝、B 25勝、12..29ply、計799遷移だった。T3の初期16判断は
全てbest terminal-only value 0で、depth3以内の既知の強制終局は検出されて
いない。これも、それより先の短い万能戦略が存在しないことを意味しない。

終了理由は `GOAL` がBの1局だけで、残る31局は
`NO_LEGAL_ACTION` だった。固定baseは各役2件以上のGOAL勝ちを要求するため、
A 0件/B 1件で明確に不合格である。接続goalは協力線では機能するが、この
agent条件ではゲームの中心的な終わり方になっていない。

## 相互作用とnode証拠

保存された事前stateとselected/applied actionから数えた実作用は、A-HOPが
31局・116手、B-PUSHが22局・44手だった。従ってbaseの相互作用gate各4局は
PASSした。相互作用が頻発したことは、明示goalの不活性や勝数gate失敗を
上書きせず、戦略的深さや面白さの証明でもない。

charged nodesはA 70,960、B 61,902、合計132,862。保存された最大合法手数は9。
全decisionのagent identity、node連鎖、完全legal-action列、selected action、
隣接state、schema-v4終端順序を照合した。Phi差分は1が306遷移、2が493遷移で、
非減少は0だった。

## Gateと解釈

- `base_numeric_pass=false`
- `base_interaction_pass=true`
- `base_goal_pass=false`
- `base_pass=false`
- `pilot_gates_pass=false`
- `human_review_eligible=false`
- `fairness_established=false`
- `hardness_established=false`
- `fun_established=false`
- disposition：`NO_FLAG`

Plan28で追加したGOAL勝利gateは有効だった。勝数だけならH3/H3は境界内で、
T3/T3も1勝差のmissに見える。しかし31/32局が行動不能終了であるため、
「交差する二つの接続競争」という説明と実際の対局の中心が一致していない。
このwireを1勝分だけ調整するより、次は明示goalが自然に終局を生む構造的に
別のaction/goal関係を選ぶ。

## 保存監査

rootと二つの独立したsaved-only監査は、game、solver、engine replayを再実行せず
PASSした。

- canonical envelopes：70
- publication hashes：68、一致
- regular files：70、1,086,998 bytes、symlink 0
- normalized-tree SHA256：
  `2ad8bc4220d6389bc19a24d6274c22483d4e4c5300812bc5f6e68df6dc2e80e8`
- raw-SHA-map SHA256：
  `dff88e07f4f741f44817f461a944a94146b8594e98b2c147697d9b08eec01dd0`
- payload-SHA-map SHA256：
  `7f6736da7abf5beb661786b96c1db74607a1286f3c6e11354991fee9b8b4762c`
- publication-map SHA256：
  `ba56a196de9e81bca6828a87c5e998d24293b960f040900fb452ab2abcb8e52b`
- summary raw SHA256：
  `2a73e1470f7b181392bdc2e6f6287b55bf100e441432c2e0b022a9505c1ac071`
- pilot log SHA256：
  `da05ae7c4670e53972beae507afb2e1d910f35f7daa91cb50bdf077210810791`

main worktreeのraw copyは隔離runの70ファイルとbyte-identicalである。Plan28の
技術acceptanceは、登録commitから同時に開始した唯一のfull regressionが完了し、
ログとsourceを確認するまでは未確定である。

## 次の判断

この候補を調整・再実行しない。Plan28のfull regressionと技術closeoutを完了後、
次番号のPlanで、既存DSL・既存agent・無LLM計算cascadeを再利用しつつ、
`GOAL`が例外ではなく主要な終局になる構造的に別のゲーム族を試す。人間への
質問や試遊依頼はまだ不要である。
