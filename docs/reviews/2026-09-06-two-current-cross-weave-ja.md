> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan28候補レビュー：二潮流の交差織り

未登録・未対局・未solver・未replayの開発候補。正本は
[`two-current-cross-weave-v0.json`](../../experiments/proposals/two-current-cross-weave-v0.json)。
definition hashは
`c84f8cf6c01adb1e13f0668dd97cfc75112f63c4e5b0dbae89a22ea8e6e3100a`、
proposal SHA256は
`eb4adfdab51b5441fae5c72af9d548884537665e74f978249d07a0866bc9582a`。
Plan27の技術closeoutまではdraftであり、本番実行の権限を持たない。

## ルール

5×5、A先手、各5枚。Aは1枚を右または右下へ1マス動かす。隣接先に
駒があれば、その同じ方向へ飛び越えて2マス先の空所へ着地する。Aは
自分の駒で上辺と下辺を直交接続すれば勝ち。Bは1枚を上または左上へ
1マス動かす。移動先のA駒は同方向へ1マス押し、Bはその跡へ入る。
Bは自分の駒で左辺と右辺を直交接続すれば勝ち。パスはない。

初期配置はAが`(0,0),(1,1),(2,0),(3,1),(4,0)`、Bが
`(2,2),(3,0),(3,4),(4,1),(4,3)`。両goalは初期false、初期合法手は
A8/B7。公開semantic signatureの`HOP/CONNECT_EDGES`対
`PUSH/CONNECT_EDGES`は、直接順・役割交換順ともold-six predicateが
falseだった。これは公開領域との非一致であって、世界全体の新規性ではない。

## 全合法手順の無引分証明

A駒ごとに`qA=4-column`、B駒ごとに`qB=2*row`を置き、
`Phi=sum(qA)+sum(qB)`とする。初期値は50。

- Aの通常移動はPhiを1、実HOPは2減らす。
- Bの上移動は2減らす。
- Bの左上移動は2減らす。実PUSHでAが左へ1列戻されてもA項が1増す
  だけなので、正味1減る。上向き実PUSHなら正味2減る。

従って全合法手で非負整数Phiが厳密に減り、goalまたは行動不能により
50ply以内に一意のA/B勝者が決まる。`max_plies=51`へは到達せず、
PLY_LIMIT/drawは不可能。保存対局でdraw0を見ることを証明の代用にしない。

## goal・作用・計算境界

authoritative parser/engineで次の協力線を各1回だけ確認した。

- A GOAL、5ply：`A00-01, B30-20(push), A10-21, B41-30, A40-41`。
- B GOAL、12ply：`A00-01, B30-20, A01-02, B41-31, A11-12,
  B31-21, A02-03, B43-33, A03-04, B33-23, A10-32(hop), B34-24`。
- 初期`A11-33`はB22を越える実HOP。`A00-01`後の`B22-11`は
  A11を00へ移す実PUSH。

各役は5枚×2方向なので合法手は高々10。cache再利用なしのdepth3は
1判断あたり`10+100+1000=1110` node。Phi50から各役は高々25回しか
選択せず、役別1局累積は`27750<100000`。depth2は2750以下。
これは既存T3/H3を完遂できる資源証明であり、深さや面白さの証明ではない。

authoritative engineのcanonical action順によるbounded AND/ORを、targetごと
に1回、100,000 cache misses上限で実行した。Aは13ply以内に強制勝ちを
持たず（false、44,704 misses/38,678 hits）、Bも14ply以内に持たない
（false、30,661/23,235）。独立実装はrole turnとwinner codeを分離した後、
同じ真偽と件数を再現した。これは各役の最初7手だけの完全な否定であり、
15ply以降、完全値、公平性、難しさ、面白さを示さない。

authoritative GameStateの幅優先列挙は、ply8の途中で100,001個の異なる
到達stateへ達した時点で停止した。ply別新規数は
`1,8,58,299,1437,5816,21352,65767,5263`、確認214,528遷移でPhi非減少0。
現行exact solverは全childを列挙し同じGameStateをcache keyにするため、
100,000 stateでは完了できない下限証拠になる。ただし、他solverや大きい資源
への困難性、意味のある分岐、ゲーム品質の証明にはしない。

## 棄却済みの事前案と露出

このwireは未接触confirmationではなく、次の公開開発結果の後に固定した。

- 5×5斜めSWAP対斜めMOVE_CAPTUREは、端列の空け方25通り全てでBが
  ply8以内に強制勝ち。3枚Bでも短勝ちがA/B間を移るだけで棄却。
- 4×4 CONVERT/CONNECT対PLACE/CONNECTは全到達state70,618で、現行
  100k exactに完全に収まるため棄却。
- 同じ侵食橋の5×5初案は100,001 stateを越えたが、Bがply10以内に
  強制勝ちするため棄却。
- 3方向HOP/PUSHの交差織りは状態規模、goal、作用、no-draw、T3上限を
  満たしたが、canonical A13/B14が各100kで打切り。別実装の当初falseは
  role-code bugで無効だった。UNKNOWNを短勝ち不在とせず閉じた。後の枝別
  追加診断も選考根拠に使わない。

最後の案から方向を各3から2へ減らした本候補は、分岐を下げて同じ事前
horizonを完全検査できる別wireである。結果に応じたseed、勝率閾値、先手、
配置の救済ではないが、開発露出をproposalに明記し、因果的改善や確認候補とは
呼ばない。今後、より長い単純万能方策、dead option、証明欠陥を見つけたら
登録前に棄却する。
