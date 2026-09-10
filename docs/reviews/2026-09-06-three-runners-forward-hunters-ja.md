> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# 次の固定案：前進する3枚と横並びの直交hunter2枚

Plan25の`NO_FLAG`後に固定したデータ定義案。未登録で、productionの
対局・exact・replayは0。人間への推薦ではない。正本：
[three-runners-two-forward-orthogonal-hunters-v0.json](../../experiments/proposals/three-runners-two-forward-orthogonal-hunters-v0.json)。
canonical hashは
`aed723e270cacd8bdfe3c87db22299d8ccf1045e63c0cebbd638d900d0491b94`。

## 変更と根拠

Plan25のルール、A先手、5×5、Aの初期配置、25ply capを全て維持し、
残る左hunterだけを`(3,1)`から`(2,1)`へ1マス前進させる。Bは
`(2,1),(2,3)`となり、初期配置の水平鏡映対称性が戻る。これはPlan25の
救済、再試行、backfill、独立確認ではなく、結果とtraceを見た第三段階の
開発案である。別hash・別plan・fresh seedでしか評価しない。

Plan25はT4/T4がA7/B9だった一方、T3/T3がA15/B1だった。保存traceでは、
A手番のT3は`A-B-A`まで読んで2手後のbottom到達を見られるのに、B手番の
T3は`B-A-B`で止まり、その直後のA到達を読めない。A勝15局ではBが価値0の
即時捕獲を選ばない例が多く、seed514ではT3の全応手が0なのに対しT4は
捕獲0／他+1を区別した。したがって15対1を完全ゲームの値とは扱わず、
浅いBへ空間的な1 tempoを与える最小変更を次の反証実験とする。

前進がBを単調に強くする証明はない。実際、Plan24からPlan25への片側前進で
T3のA勝は12から15へ増えた。Plan25のT4/T4は既にB9勝なので、両hunterの
前進がB支配へ過補正する危険も明示する。Bの後退vectorを削る案は、Plan25の
T4が後退を終局勝ちを含めて実際に使ったため、配置1座標より大きな変更として
採らない。

## ルールと無引き分け証明

Aは上辺の列1,2,3に3枚。1手に1枚を1行下へ進め、列は左・同じ・右。
どれか1枚が下辺へ着けばA勝ち。Bはrow2の列1,3に2枚。1手に1枚を上下左右へ
動かし、行先のAを捕獲できる。Aを全て取ればB勝ち。パスなし。合法手が
なければschema4既定どおり手番側の負け。

非終局状態で、生存A全枚の下辺までの残り行数を
`D = sum(4 - row(A))`とする。初期Dは12。各A手はDをちょうど1減らし、
Bの捕獲はbottom未到達Aの正の項を除く。Bの通常移動だけがDを保存する。
A先手の交互手番なのでAは最大12回、Bは最大11回しか行動できない。
遅くとも23plyでAのREACH、BのELIMINATE、または手詰まりによる一方の勝ちに
なる。23<25のため、全合法playでPLY_LIMITもdrawも到達不能である。

## 静的境界とgoal機能性

初期goalは双方false。Aの合法手は9、初期盤をB手番として測るとBは8。
最大分岐もA`3枚×3=9`、B`2枚×4=8`。cache効果を仮定しないdepth4の
1選択上限はA`9+72+648+5184=5913`、B`8+72+576+5184=5840`。
最大12/11選択なので累積A70,956、B64,240で、各role/gameの100,000未満。
これは計算可能性の境界であり、ゲームの難しさの証明ではない。

両goalには合法な協力線がある。

- A到達：`A01-10, B23-24, A10-20, B21-22, A20-30, B22-23, A30-40`。
- B全捕獲：`A01-11, B21x11, A02-12, B11x12, A03-13, B12x13`。

したがってgoal自体はdeadではない。MOVE/REACH対MOVE_CAPTURE/ELIMの
signatureは公開old-sixと役割交換の外にある。

## 限定的な短手筋確認

中央直進`A02-12`には`B23-13`があり、次の`A12-22`は左hunter、
`A12-23`は右hunterが捕獲できる。単純なBの端追跡・捕獲も万能ではない。

`A01-10/B21-20, A03-14/B23-24, A02-12/B20x10,
A12-21/B24x14, A21-32`

の後、Bは`(1,0),(1,4)`、Aは`(3,2)`にいる。Bは次の1手でAのbottom候補を
全て防げず、Aは次手に到達する。これはその単純方策だけの反例であり、
Aの強制勝ちではない。

独立した助言的なbounded AND/OR確認では、論理短絡を使って
`(state, target, horizon)`を累積153,753 cache miss評価した。
問い合わせ`A13/B13/A14/B14`は全てfalseで、主要命題のA13/B14により
A/Bとも最初の7自手以内に全応手へ勝てない。terminalをhorizon0より先に
判定し、target手番は存在量化、相手手番は全称量化した。別担当のfreshな
独立実装も同じ4結果、各miss`61977/8780/70771/12225`と累積値を再現した。
この確認はagent、
登録production exact、ゲーム試行、replay、保存runではない限定的な
solver-like analysisだが、候補固有の計算を行った登録前露出として記録する。
production game/exact/replay countは0。14ply以降の強制勝ち不在、公平性、
深さ、面白さは証明しない。

proposalのmachine-readable exposureにも、Plan25の結果・trace利用とこの
登録前bounded AND/OR計算を記録した。

## 次の固定screen案

Plan25の全回帰と技術closeoutが通った後だけPlan26として登録を検討する。
候補実行前に最終wireのcanonical/hash/public-region/no-draw/境界を再監査し、
直接の短い万能勝ち、dead goal、証明欠陥が見つかれば登録前棄却する。

通す場合もPlan24/25のgateを緩めない。fresh seeds700/800を使い、exact
100,000を1回、baseはT4/T4とT3/T3を各16局、通過時だけ後段48局とする。
最大80局+exact1回。retry、resume、backfill、seed差替え、cap増加、depth追加、
追加PVは禁止。登録時に詳細scheduleと停止規則をprospectiveに凍結する。
機械gateを全て通して独立保存物監査と全回帰も通るまで、人間には提示しない。
