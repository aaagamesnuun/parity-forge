> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan30 静的候補設計記録

## 境界

Plan30は、最大4候補を安い静的条件で揃えてから一度だけpreselectionする。
この段階ではgame、exact solver、選択用AND/OR、到達state列挙を実行しない。
各新規slotは最大2 draft、各draftは手書きprefix最大4本をprimary/auditで
各1 replayまでとする。candidateの楽しさ、公平性、奥深さ、人間適格は未判定。

CELL-1 `five-thread-hop-swap-connect-v0`（hash
`a6de32c2b481614901caeabd2f2414815088a2b60992a3c4a55b7041aa2b7908`）は、
Plan29からdefinitionを一切変えずrank1へ持ち越した。登録前のshort screenや
state-prefix結果を見たoutcome-exposed developmentであり、Plan30の確認証拠、
候補間の公平比較、手法改善の証拠ではない。

## CELL-2 draft1 individual static lane

`five-thread-push-capture-triad-v0`、hash
`641c04d91572f4b748e927fe45490233a1ff71eb61cd5ab030a0e54c57bef4be`。
5×5/A先手。Aは上辺5枚を南3方向へPUSHし、自色でTOP–BOTTOMを接続する。
Bは下辺columns0,2,4の3枚を北3方向へMOVE_CAPTUREし、A全滅を目指す。
`max_plies=53`。公開old-six predicateは直接・role-swapともfalseだった。

`Phi=2*sum_A(4-row)+sum_B(row)`は初期52。A空移動で2、実PUSHではA項-2と
B項+1で正味1、B空移動で1、実captureではB項1に加えて正のA項が減る。
従って全合法手で非負整数Phiがstrictに減り、52<53なのでPLY_LIMIT前に
必ずA/Bいずれか1名が勝つ。初期は非terminalで、Aの合法手は13。

最大分岐は`b=15`、各roleの判断回数は`t<=26`。
`26*(15+15^2+15^3)=93,990<100,000`なので既存T3は構造上完走できる。

固定初期状態から二つの完全合法prefixをengineでprimary/audit各1回確認した。
A接続GOALは19ply、B全滅GOALは14ply。後者は実PUSH1回と実capture5回を含む。
全中間状態は非terminal、全actionはその時点のauthoritative legal tuple内、
最終reasonは各々GOALだった。完全action列はmachine-readable draft recordに
保存した。draft1が候補単体の静的laneを満たしたためCELL-2 draft2は未生成・
未確認で永久に閉じる。4候補間の構造比較と合計resource ceilingはまだ計算
できないため、最終cohort admissionは4定義確定後までpendingである。

## CELL-1 / CELL-3 / CELL-4 と最終cohort

CELL-1はPlan29のdefinitionを変更せず、Plan30固有のprimary/auditを新たに
実行した。`Phi=sum_A(4-row)+sum_B(row)=40<cap41`、`b=15`、`t<=20`、
T3=72,300。A/B両GOAL、実HOP、実SWAPの4 prefixを各laneで1回だけ再生し、
合計96 transitionsで一致した。Plan29の既知結果を検査の代用にはしていない。

CELL-3 draft1 `five-thread-capture-swap-bridge-v0`（hash
`247adb1bd139def5650fdfe0f8e0f9a78bc36147b08a505ab27e64d9fa8b03be`）は、
AがMOVE_CAPTURE/CONNECT、BがSWAP/REACH。CELL-4 draft1
`full-rank-hop-capture-thread-v0`（hash
`5b5b5c4c88fcabe0017c8ecc2749a74c639ab6dd35a03cca8455106f416fca11`）は、
AがHOP/CONNECT、BがMOVE_CAPTURE/REACHである。どちらも
`Phi=sum_A(4-row)+sum_B(row)=40<cap41`、`b=15`、`t<=20`、T3=72,300。
CELL-3はA GOAL+captureとB GOAL+swapをprimary/audit各1回、計54
transitions、CELL-4はA GOAL、実HOP、B GOAL+captureを同様に計64
transitionsで再現した。途中終局、不正手、不一致はなかった。draft1が通った
ため両slotのdraft2は生成も検査もしていない。

独立read-only cohort監査では、4定義のcanonical hash、公開old-sixのdirect/
role-swap全false、相互structure、Plans20–28およびPlan29の他3 draftとの
非重複が一致した。CELL-1自身の同一Plan29 copyだけを規定どおり免除した。
4候補の`sum(b)=60`、`sum(L)=172`、`sum(max_plies)=176`。
本番上限はBFS6,000,060 transitions、内部replay1,584 transitions、対局
1,408 plies、short miss1,600,000、exact state400,000、設定上agent node
6,400,000である。実scheduleのT2/T3構造boundは165,120+2,487,120=
2,652,240、全game-role callをT3で包む保守boundは4,974,240と区別する。

設計stageは最大7 definitions / 56 prefix replaysだった。schema上
`L<=999`なので一般上限55,944、固定CELL-1を反映した事前上限48,272
transitions。実際は4 definitions、22 replays、280 transitionsだけを使い、
game/exact/selection AND/OR/BFSは0のままcohortを凍結した。

最終freeze監査で、Plan本文の旧表現「every intermediate stateとlegal tupleを
recording」がdurable artifact保存を意味するようにも読める点を検出した。
実際の各laneはそれらを逐次構築・検査したが、正本に永続化したのは完全な
入力action列、lane回数、終局・効果summaryであり、導出可能な全state/tuple
の複製ではない。Plan本文をこの実際のevidence formatに明確化した。追加
replayは行っておらず、既定の各lane1回上限を緩和していない。

設計正本：`experiments/proposals/plan0030-design-drafts-v0.json`。
凍結prospective proposal：
`experiments/proposals/plan0030-four-structure-preselection-v0.json`。
48個のseedは全て一意、policy順はT2/T2→T3/T3、最大56 attemptsである。
最終read-only freeze監査は全定義/hash、design SHA参照、seed mapping、gate、
UNKNOWN wire、BFS memory、files/bytesを再計算してPASS。proposal SHA256は
`d547bc5dee706f2a5480f4f2e8c7ac021e8ba2eec9abbda6fbac2a0ab48fcd15`。
このPASSは無引き分け性と本番実行可能性の静的入場判定だけで、公平性、
難しさ、面白さ、人間playtest適格を意味しない。次はPlan固有script/testを
実装・監査してから、production count zeroで一度だけ登録する。
