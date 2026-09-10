> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan30 preselection 結果

## 結論

Plan30の単一production runは正常終了したが、結果は`NO_SELECTION`である。
4候補すべてが`NOT_SELECTED_EVIDENCE_INCOMPLETE`で、選択候補はnull、
`human_review_eligible=false`である。公平性、実用的難しさ、面白さ、学習価値、
遊べなさのいずれも判定していない。

登録commit：
`27b5138fe3dddc22c4e1c24d261746f036174598`。
authoritative run startは2026-09-08 00:31:05.688764 JST、最終slot保存は
00:34:02.358361 JST。runnerはexit0だった。

## 実行された証拠

全56枠のうち計算したのはshort query5件だけだった。

| cell | query | status | misses | 判定 |
|---:|:---|:---|---:|:---|
| 1 | A7 | `UNKNOWN_CENSORED` | 100,000 | evidence incomplete |
| 2 | A7 | `COMPLETE`、root value0、force false | 95,704 | B queryへ継続 |
| 2 | B8 | `UNKNOWN_CENSORED` | 100,000 | evidence incomplete |
| 3 | A7 | `UNKNOWN_CENSORED` | 100,000 | evidence incomplete |
| 4 | A7 | `UNKNOWN_CENSORED` | 100,000 | evidence incomplete |

short miss合計は495,704。残り51枠は`NOT_STARTED_GATE_CLOSED`である。
したがってproduction game32枠、exact4枠、BFS4枠はすべて未実行で、game plies、
game nodes、exact states、replay、BFS transitionsは全て0。resource ceiling違反、
draw、PLY_LIMIT、技術失敗はない。

`UNKNOWN_CENSORED`は、固定100,000-nodeの既存探索が問いを決定できなかったこと
だけを表す。勝敗や引き分けではなく、深さの肯定証拠でも、候補が不公平・浅い・
遊べないという棄却証拠でもない。ただしPlan30の事前登録gateでは非認証なので、
遡って通過扱いにせず、追加query、cap増加、対局、補充を行わない。

## 保存と監査

raw runは56 records、116 canonical envelopes、161,182 bytes。rootと二つの
独立saved-only auditがexit0/PASSを再現した。193 source pins、16 direct
entry-point pins、proposal/design/source hash、全schedule、114 publication hashes、
file/byte/resource ceilingが一致し、監査中のproduction callは0だった。

- summary SHA256：
  `8ebbd7d298ef437a2a3a24b90eb125e3930e22c79548f54cafd211dafd9c01b3`
- source-verification SHA256：
  `e8110bd56c229c5653941cb85ab17836b950c5bbf602d27e51133f94af0108d8`
- 116-file path/raw-SHA map digest：
  `16ffab694da7dd4a819f43fdd75f2d220415dc3bae39a4dfe472f37855770e41`
- production log SHA256：
  `7c3255ddb7bde8fd1802e115d070fdfadff1fd9c138d2d5286bd4a481a9eceda`
- saved audit log SHA256：
  `1a8e8313b5aadc79897ee9d479ee5863a8e4599e96afe445c680d2f3053790c4`

## launcher preflight

00:28:39 JSTの最初のshell formは、`scripts` packageを解決できずmodule import
line25で終了した。`main`、`run_pilot`、proposal load、output reservationより前で、
short/game/exact/replay/BFSは全て0。二つの独立レビューがPlan27と同型の
non-production launcher preflightと判定した。257-byte logのSHA256は
`76b12b9e58521d36fb296b6cbfc9e85b6ceea9169dfb7e29eea35e6cbfa25e10`。
正しいmodule invocationだけを唯一のproduction runとして数える。追加起動は禁止。

## 技術受入と次の解釈

単一full regressionは登録sourceから並行実行中で、技術受入はまだprovisional。
実際の最終`Ran`、`OK`、exit0と16MiB以下のdurable log SHA256が揃うまでPlan30を
archiveしない。中断・失敗時も再実行しない。

生存候補を変更せずPlan31へ送る条件付きbranchは開かない。研究を続ける場合の
次の未使用番号は、Plan30のretryや補充ではない独立研究単位`Plan0031`である。
Plan番号は時系列の研究単位、proposal/candidateの`v0`はdata artifact版、protocolの
`v1`は実行wire版であり、互いに別である。

今回5件中4件がcensorとなり、対局情報を一件も得られなかった。このgateは正直では
あるが、探索しにくい候補ほど早く閉じるため、目的と逆向きのinformative censoringを
生む。次Planで変更するならprospectiveに行い、Plan30を再解釈しない。既存手法の
最小改善候補は、浅いforce queryを完了できる低い最大分岐と、全体を読み切りにくい
長いstrictly-decreasing horizonを静的入場条件として組み合わせることである。
