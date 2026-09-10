> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# 次候補レビュー：三潮流（SWAP対PUSH）

2026-09-06。Plan26の固定pilot終了後、全回帰の待機中に作成したsource-led
development記録。これはPlan27の候補案であり、active plan、登録済み実験、
人間試遊推薦ではない。production game、exact solve、agent対局、replayは0。
Plan13/14の候補・結果メンバーには触れていない。

## なぜrunner/hunterの座標調整を終えるか

Plan24〜26は、5×5、A先手、3 runner対2 hunter、行動、目標を固定したまま、
Bの開始行だけを変えた。公開traceでは、T4/T4のA勝29局中26局で3枚全てが
動き、21局では1枚以上、11局では2枚を捕らせて残りが到達した。単純な最終手
の取り逃しより、逐次投入と別runnerへのrelayが主要な形だった。

同じseedのT3/T4比較では17/48局で勝者が反転し、そのうち14局はT4のB勝から
T3のA勝への反転だった。新seedと座標を同時に変えたPlan間の勝数差は因果効果
ではない。これ以上の座標調整は、ゲーム構造よりterminal-only agentの深さ偶奇
境界へ合わせる危険が高い。runner/hunter全体の不可能性は主張しないが、
この座標だけの系譜はPlan26で止める。

## 固定した機械案

提案fileは`experiments/proposals/three-currents-swap-push-v0.json`、definition
hashは`aa3079277a9089aa8758fa04f0d81be09544af39ba9338524cf97e6f98490209`。
候補definition objectはcommit`1da2eadca`で、対局・solver前に固定した。
その後、definitionを変えずにexposure metadataだけをbounded確認後の完全な文言へ
更新した。現在のproposal file SHA256は
`24429c2c3f703367b0a1361f98eddf3c762c91f57e847518323968f2f5cc7269`。

- 5×5、A先手、両役3枚。Aは上辺、Bは下辺の列0,2,4から始める。
- Aは右または下へ1マス動く`SWAP`。行先がBなら位置を交換する。
- Bは上または左へ1マス動く`PUSH`。行先がAなら同方向へ1マス押す。
- Aは1枚でも下辺、Bは1枚でも上辺へ達すれば勝つ。
- 空所への移動、交換、押し以外の捕獲、連鎖、pass、運はない。
- `max_plies=55`。機械的正本はproposalのDSL4定義である。

同数駒・同じ到達型目標だが、交換は接触時に相手も上・左へ進め、押しは相手を
上・左へ押し戻す。役割交換や盤面回転だけでは同一にならない。これは
MOVE/REACH対MOVE_CAPTURE/ELIMの初期座標修正ではない。

## 全合法手の有限決着証明

A駒`(r,c)`に`qA=(4-r)+(4-c)`、B駒に`qB=r+c`を与え、

`Phi = sum(qA) + 2*sum(qB)`

とする。全項は非負整数で、初期値は`18+2*18=54`。

- Aの空所移動は右/下なので`Phi`を1減らす。
- AのSWAPはAを右/下、Bを左/上へ1進め、`Phi`を3減らす。
- Bの空所移動は上/左なので`Phi`を2減らす。
- BのPUSHはB項を2減らし、押されたA項を1増やすので、正味1減らす。

従って全合法手で`Phi`が最低1減り、54ply以内にgoalまたは合法手なしで終了する。
54<55なので`PLY_LIMIT`は到達不能。DSL4ではgoalを先に判定し、次手番に合法手が
なければ直前のactorが勝つ。同時に両goalが成立してもactor優先で勝者は一人。
初期盤面で各役の合法手はA5/B5、両goalはfalse。

手書きの協力的な固定lineをengineで1回ずつ確認した。Aは
`(0,4)-(1,4)-(2,4)-(3,4)`と進み、最後に`(4,4)`のBとSWAPして7plyで勝てる。
Bは列0を`(4,0)-(3,0)-(2,0)-(1,0)-(0,0)`と進み、Aが初手で`(0,0)`を
右へ空けるlineで8ply勝ちできる。これは両goalの機能確認であり、競争的な
勝ちや公平性の証拠ではない。別の4ply prefix
`A(0,0)->(1,0), B(4,0)->(3,0), A(1,0)->(2,0), B(3,0)->(2,0)`では、
最後のBがAを`(1,0)`へ実際にPUSHすることも1回確認した。Aのgoal lineの
最終手は実際のSWAPであり、両conditional effectは到達可能である。

公開semantic signatureの`SWAP/REACH_EDGE`対`PUSH/REACH_EDGE`は、直接順・
役割交換順ともold-six predicateがfalseだった。member accessはしていない。

## 計算境界と事前の短手数確認

各役は3枚×2方向なので、任意局面の合法手は高々6。cache再利用なしのdepth4
選択は高々`6+36+216+1296=1554` node。54plyの交互手番では各役は高々27回
選択するため、役別全局上限は`1554*27=41958<100000`。

固定定義に対し、production solverとは別の助言的bounded AND/ORをrootと独立
reviewerが各target1回ずつ実行した。論理短絡と
`(state,target,remaining)` cacheを使い、各query100,000 missで停止する。

- Aが13ply以内、すなわちAの最初の7手以内に全応手へ勝てるか：
  `false`、28,639 misses、13,184 cache hits。
- Bが14ply以内、すなわちBの最初の7手以内に全応手へ勝てるか：
  `false`、12,681 misses、3,429 cache hits。

独立実装はcanonical順ではなくsalted SHA256順でactionを辿り、A13を
`false`（25,883 misses/12,344 hits）、B14を`false`
（15,895 misses/5,736 hits）と再現した。短絡順序で件数は変わるが真偽は一致。

これは各horizon内に限った完全な否定であり、15ply以降の必勝、完全play値、
公平性、難しさ、面白さを示さない。実装上の属性名誤りで再帰開始前に止まった
試行が2回あり、最初は初期合法手数まで、次は上記2本のgoal lineまでを確認した。
成功したbounded queryはroot/独立を合わせ各target2回。いずれも
game/exact/replayには数えない。

この追加露出をproposal metadataへ明記した。最終exposure文字列は
`SOURCE_DESIGNED_AFTER_PLAN0024_0026_PUBLIC_TRACE_DIAGNOSIS_AND_`
`PREREGISTRATION_GOAL_EFFECT_AND_SHADOW_COUNTERLINES_AND_TWO_BOUNDED_`
`AND_OR_TRAVERSALS_EXPOSED_NOT_CONFIRMATION`。

## 代表的shadow方策の限定challenge

manual reviewerは、Bの自然なpure方策を二つに固定した。`H`は初期同列を担当し、
Aが列を空けたらそのhome fileを上がり続け、確認branchでは水平再配置を使わない。
`Q`はAが右へ移るたび東側の最寄りBを即LEFTして追跡する。両極とも万能ではない。

`H`はAの最初のDOWN列のhome Bをactiveにし、合法な間はそのBのUP/PUSHを
続ける。不能なら合法UPを持つ未使用home列を小さい列順でactiveにする。
`Q`は、直前A手がRIGHTなら新列より東の最寄りBをLEFT（距離、row、columnの
昇順tie）、直前A手がDOWNなら同列下方の最寄りBをUP/PUSH、該当なしなら
合法UPを持つ最左B（row昇順tie）を選ぶ。各節は指定手が合法な場合だけ適用し、
最後は`(from,to)`昇順の最初の合法手へfallbackする。この規則で確認対象となる
正確なaction列は以下。

```json
{
  "H": [
    ["A","SWAP",[0,2],[1,2]], ["B","PUSH",[4,2],[3,2]],
    ["A","SWAP",[1,2],[1,3]], ["B","PUSH",[3,2],[2,2]],
    ["A","SWAP",[0,0],[0,1]], ["B","PUSH",[2,2],[1,2]],
    ["A","SWAP",[0,1],[0,2]], ["B","PUSH",[4,0],[3,0]],
    ["A","SWAP",[1,3],[2,3]], ["B","PUSH",[3,0],[2,0]],
    ["A","SWAP",[2,3],[3,3]], ["B","PUSH",[2,0],[1,0]],
    ["A","SWAP",[3,3],[4,3]]
  ],
  "Q": [
    ["A","SWAP",[0,4],[1,4]], ["B","PUSH",[4,4],[3,4]],
    ["A","SWAP",[0,2],[1,2]], ["B","PUSH",[4,2],[3,2]],
    ["A","SWAP",[0,0],[1,0]], ["B","PUSH",[4,0],[3,0]],
    ["A","SWAP",[1,2],[1,3]], ["B","PUSH",[3,4],[3,3]],
    ["A","SWAP",[1,0],[1,1]], ["B","PUSH",[3,2],[3,1]],
    ["A","SWAP",[1,4],[2,4]], ["B","PUSH",[3,0],[2,0]],
    ["A","SWAP",[2,4],[3,4]], ["B","PUSH",[2,0],[1,0]],
    ["A","SWAP",[3,4],[4,4]]
  ],
  "horizontal_effect_prefix": [
    ["A","SWAP",[0,2],[1,2]], ["B","PUSH",[4,4],[3,4]],
    ["A","SWAP",[1,2],[2,2]], ["B","PUSH",[3,4],[2,4]],
    ["A","SWAP",[2,2],[2,3]], ["B","PUSH",[2,4],[2,3]],
    ["A","SWAP",[2,2],[2,3]]
  ]
}
```

- HへのA counterlineは13plyでA勝。中央Aを右へ逃がし、左上Aを右へ2回動かして
  top中央を再封鎖する間に、別列のBを1tempo遅らせ、逃がしたAが下辺へ達する。
- QへのA counterlineは15plyでA勝。左右のAを囮としてB2枚を左へ誘導し、
  温存されなかった右端をAが突破する。

rootはreviewerが固定した両action列をengineで各1回検証し、それぞれ13/15plyの
A `GOAL`を確認した。また中央Aと右Bをrow2へ寄せる7ply prefixで、水平B-PUSHの
直後に水平A-SWAPが合法で、途中goalなしであることも1回確認した。

これは「再配置しない」「常に即再配置」という二つの具体的方策だけの反例である。
進行度に応じて右端Bをreserveするhybridや、任意の完全戦略を否定しない。

## 既知のリスクと次の境界

- 代表的なpure shadow/queue二案は反証したが、進行度でreserveを切り替える
  15ply以降のhybrid万能方策があり得る。
- 右/左の選択が実質的に劣後し、説明上だけの分岐になる可能性がある。production
  gateでは両役のT4が水平手を選んだ局と、実SWAP/PUSHが生じた局を別々に数える。
- SWAPはBも目標方向へ進め、PUSHはAを戻すため、有限skillでB有利かもしれない。
- Aはbottom上のBとSWAPしてactor goalで勝てるが、Bはtop上のAを盤外へPUSH
  できない。またAが上端付近のBとSWAPすると相手goalを成立させ得る。この
  terminal非対称は派生ルールとテストに明記する。
- 低い分岐でも状態空間が100,000以内に解ければD-057で棄却する。
- T3/T4は同じterminal-only familyであり、勝率混在は人間の深さを示さない。

独立した定義・証明・bounded結果の再確認と、二つの代表的shadow方策への限定
source challengeはPASSした。今後、短い/単純な万能勝ちを発見した場合は登録前に
閉じる。Plan26の固定screenを候補固有に機械的retargetしたPlan27を、
Plan26技術closeout後に別commitで登録する。screenには既存decision recordから
実作用と水平選択を導く候補固有telemetryだけを追加し、adapterは変更しない。
