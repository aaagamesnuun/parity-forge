> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan29前段：既存手法による有界preselection記録

追記（2026-09-07）：後に固定したPlan29 CELL-3の
PUSH/REACH_EDGE対HOP/REACH_EDGEは、公開old-six predicateでrole-swap込み
trueだった。Plan29のno-substitution規則により、全Planを未登録・production0で
閉じた。さらに、attempted CELL-4は契約したHOP/REACH_EDGEではなく
HOP/CONNECT_EDGESへdriftしていた。以下は引き続きdevelopment exposureであり、
Plan30の選択証拠ではない。

2026-09-06。Plan28のpilotが`NO_FLAG`となり、登録済み全回帰を待つ間に
行ったsource-led開発記録である。以下は既存parser/engine、到達状態BFS、
有限horizon AND/ORだけを用いた。Plan28の追加game、solver、replay、seed
補充は0。各候補のproduction実行、exact solver、replay、repo内実装変更も
0である。

ただし、ここで報告するcanonical定義、checker、raw出力はrepo内の再現可能な
正本として一式保存されていない。従って全数値を
`UNREGISTERED_DEVELOPMENT_EXPOSURE_ONLY / NOT_SELECTION_EVIDENCE`とする。
独立監査はこの欠落自体を確認した。以下は避ける領域とPlan29の設計理由を
開示する記録であり、Plan29候補をpass/failさせる証拠ではない。Plan29は別途、
4定義と順序を固定して登録した証拠だけで判定する。

## 個別に棄却した候補

### CONVERT対PUSHの交差流

`cross-current-convert-push-v0`、definition hash
`10d10f4101d78e837dad79db461fbe5a4096fae76fcc6cbc4383a28ea2022cae`。
5×5/A先手で、Aは東3方向へCONVERTしてRIGHTへ到達、Bは北3方向へ
PUSHしてTOPへ到達する。A3枚、B9枚、`max_plies=18`。

Aの全合法手はBを1枚減らし、BはB枚数を増やさないため、全合法列は
最大17plyで一意に決着する。到達列挙はply10途中で100,005状態を越え、
両GOALと実PUSHの合法lineも存在した。しかし完全な有界AND/ORで、Bは
6ply以内に勝ちを強制できた（328 misses/41 hits、B5はfalse）。状態幅や
GOALの存在は、短い万能必勝を上書きしないため登録前に棄却した。

### B先手の四lane HOP対SWAP

`four-lanes-hop-swap-b-first-v0`、definition hash
`eaab34f08a47f57c4c527df229eed3c10e746c0876918af0ff25ec67c86a2fbe`。
5×5、Aはrow0のcolumns0,1,3,4から南3方向へHOPしてBOTTOMへ到達し、
Bはrow4の同じ4列から北3方向へSWAPしてTOPへ到達する。B先手、
`max_plies=33`。

`Phi=sum_A(4-row)+sum_B(row)=32`は通常移動で1、実HOP/実SWAPで2減る。
従って全合法列は32ply以内に一意に決着する。各役の合法手は最大12、
T3は1判断1,884、役別1局30,144 node以下。独立した二つの実装が、ply7
途中で100,001状態、248,841遷移、Phi違反0を再現した。

助言的な既存agent40局は全てGOAL終了し、異なるprofileを記述的に合算すると
A21/B19だった。しかし完全AND/ORはB7をtrue（1,258 misses/829 hits）、
B5をfalseとし、Bが自身の4手目までに勝ちを強制すると示した。A14はfalse
（47,068/9,368）。浅いagentの混合勝敗より完全な短手反例を優先し、この
候補も登録前に棄却した。

### CONVERT対SWAP/CONNECTの案

5×5/A先手、A CONVERT/CONNECT LEFT–RIGHT、B SWAP/CONNECT TOP–BOTTOMの
固定案、definition hash
`66948e20b854d13b141caac1849975b048010539563e95c46b6d8842609518cc`。
Bのrowを数えるpotential25により全合法列25ply以内、両GOALの合法lineも
確認できた。しかし全到達stateは8,776だけで、Bは8ply以内に強制勝ちを
持った。完全読切り規模と短勝ちの両方で棄却した。

## 二つの固定部分族の負結果

これらは各々の明示した有限範囲だけの助言的preselection結果であり、action
pair全体の不可能性を主張しない。

### 整列home-row HOP対SWAP

5×5、Aをrow0、Bをrow4の同じ3列または4列へ置き、A HOPは南向き、
B SWAPは北向きとした。各roleのcolumn deltaを
`{-1,0}`, `{-1,1}`, `{0,1}`, `{-1,0,1}`から独立に選び、先手A/Bを含めた。
左右反転前480定義、反転固定24からBurnsideで252 orbitとなる。

252/252をcanonical parseし、先手はply7、後手はply8までの完全AND/ORを
各100,000 misses上限で実行した。236定義は先手がply7以内、残る16定義は
後手がply8以内に勝ちを強制した。CLEAR 0、budget UNKNOWN 0、単一queryの
最大は34,627 misses。この整列部分族には両者の最初4手を越えて残る候補が
ない。上下で異なる列集合を使うstaggered配置までは否定しない。

### CONVERT/ELIMINATE対PUSH/CONNECT

5×5/A先手、A3枚/B9枚、cap18。Aは2方向CONVERTでB全滅、Bは2方向PUSHで
TOP–BOTTOM接続を目指す。上辺gap3種、A中段motif4種、vector pair4種の
固定48定義を追加・補充なしで列挙した。

全48定義の到達graphは各11..783状態、合計8,630状態で完全に枯渇した。
A/BどちらのGOAL terminalも0で、全terminalはNO_LEGAL_ACTIONだった。
CONVERTがBを減らしても次のA接触が維持されず、全滅前にAが動けなくなる。
「相手枚数が単調減少する」だけではELIMINATE goalの機能性を保証しない。
goal/状態幅gateで全件を閉じ、その後の短手AND/ORは0件とした。

## Plan29へ反映する順序

単発候補を32局のscreenへ直送するより、既存手法だけの固定4候補screenを
一段置く。4件は少なくともaction pairまたはgoal pairが異なるものとし、
座標、閾値、先手だけを変えた候補で埋めない。全canonical JSON/hashと順序を
登録前に固定し、失格分の補充、retry、cap追加をしない。

1. parse/hash、初期非terminal、全合法無引分証明、両GOALと特殊作用の合法line。
2. 各役の最初4手までの完全AND/OR。trueだけでなく100k UNKNOWNも閉じる。
3. T2/T2とT3/T3を各4局。各cellを別々に判定し、各4/4完了、A勝1..3を
   要求する。合算勝敗で一方のdepthの全勝を隠さない。LLMは使わない。
4. 生存候補だけ100,001-state BFS。完全枯渇は易しすぎるため閉じる。
5. 生存候補だけ各役最初7手までを100k AND/OR。両方COMPLETE falseだけ残す。
   100k到達は`NOT_SELECTED_EVIDENCE_INCOMPLETE`であり、科学的な棄却、
   易しさ、難しさの証拠にしない。

候補ごとに最大分岐`b`とpotentialから役別最大判断回数`t`を証明し、
`t*(b+b^2+b^3)<=100000`だけをT3へ入れる。短手queryはtargetごと100k、
BFSはstateだけでなくtransition/output上限も登録前に固定する。最大1件を
結果を見る前に固定した順位で選び、Plan29は選択証拠として閉じる。その1件
だけをfresh seedの別Plan30対局screenへ送る。Plan29自体は公平性、奥深さ、
面白さ、人間適格を主張しない。
