> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan31 静的設計レビュー

## 結論

固定した2構造・最大2 draft/構造の設計段階は、3定義を調べた時点で終了した。
CELL-1 `zigzag-hop-two-hunters-v0`だけを静的にadmitする。CELL-2の2 draftは
完全なsource-level単純必勝策が見つかったため、ゲーム、exact solver、選択探索、
BFSを一度も呼ばずに棄却した。Plan31のproduction countは0、人間レビュー資格は
falseである。

これはCELL-1の公平性、難しさまたは面白さの判定ではない。静的admissionが示すのは、
全合法プレイの無引き分け、両者の明示ゴールと条件付き効果の実在、旧領域からの新規性、
低分岐による次段short screenの完遂可能性だけである。

機械可読の全記録は
`experiments/proposals/plan0031-design-drafts-v0.json`、そのSHA256は
`b047936221304388f8c5b52dce94ed2274ab5c0492f0bfdadefb21e54b074555`である。

## 固定範囲と実消費

- 構造上限2、各構造のdata-only draft上限2、置換・backfillなし
- 実際に生成・検査したdraftは3、未生成枠は1
- design-stage production/game/exact/solver/BFS callはすべて0
- engine prefix replayはCELL-1の4本を主系と独立系で各1回だけ、合計8 replay・
  68 transitions
- CELL-2はsource proofでfail-closeしたためprefix replayは0

番号は結果の良否ではなく、凍結した研究上の問いを時系列に識別する。Plan31は
Plan30のcap追加や再試行ではなく、Plan30で露呈した高分岐とshort-screen予算の
不整合を避ける独立研究単位である。定義名の`v0`/`v1`はデータ版でありPlan番号とは
別である。

## CELL-1 — 静的admit

5x5、A先手。Aは下向きHOP5枚でLEFT–RIGHT接続、Bは上/左MOVE_CAPTURE2枚で
A全滅を目指す。definition hashは
`8c07cc4a89981b2b1533cfafd12081f71c72c0f79835172765fa4b9a3fa8600a`。
public old-sixは両role順でfalse、Plans20–30および最終CELLとのrole-neutral衝突もない。
初期局面は非終局でA合法手5。全reachable stateの最大分岐は5で、初期状態が達成する。

ポテンシャル
`Phi=2*SUM_A(4-row)+SUM_B(row+column)`は初期47である。A通常HOPで2、
実HOPで4、Bの上/左移動で1減り、捕獲時はさらに捕獲A項が消える。常に非負整数で
1以上減るため、`max_plies=48`より前に必ずA/Bどちらか一方が勝ち、PLY_LIMITには
到達しない。

主系と独立系は次の4 prefixを各1回ずつstepwise replayし、全手の合法性、途中終局なし、
全遷移のPhi減少を確認した。

- A CONNECT GOAL: 11 ply、A勝ち
- B ELIMINATE GOAL: 14 ply、B勝ち、実capture5回
- 実HOP: 7 ply後も非終局、実HOP1回
- 実capture: 2 ply後も非終局、実capture1回

主系potential-trace digestは順に
`4891c9aab0785e166c8f5eca829d9545a68374ae3b5614cf2d76c1073f805d06`、
`63a4d08d5dcd802339e453e5bb9792e9e8c8b64200ca7d4ebfb4e3adce8c5310`、
`948aa38b850c5c7355423545f485d82335878703607ba9b70044b4783ec89b37`、
`07b61045e39cc5a6df666a6b9c868ee6c87a1cc33da3ccec649f320885786995`。
独立系も34/34 transitionsを再現した。source-onlyの限定レビューではA-by-ply7または
B-by-ply8の単純万能策を発見しなかったが、これは不存在証明ではない。

`b=5`なので、完全木の上限は`S7=97,655`、`S8=488,280`、
`40*S4=31,200`。従って次段ではcap切れを情報として扱わず、cap切れ自体を
admission証明との技術矛盾として扱える。

## CELL-2 — 2 draftともsource棄却

draft1 `interleaved-push-step-bridges-v0`はD-055ポテンシャルと`b=5`自体は成立した。
しかし全列の1-cell gapをAが順に閉じるだけで、Bの応手に依存せずAがply5で勝つ。
さらにA/B双方のCONNECT goalが全合法プレイ中に到達不能だった。従って実PUSHの
source prefix以外を再生せず、残り静的検査をgate-closeした。

唯一のdraft2 `staggered-push-step-bridges-v1`は、A `(2,1)->(1,1)`と
B `(2,0)->(4,0)`だけを変更した。definition hashは
`8caa98bd96f377ba42bbdb4f92594a5e41ce904b1dbd06deb599f1db76e26231`。
`Phi0=50`、`max_plies=51`、`b=5`、旧領域非衝突は成立し、両GOALと実PUSHの
source-only lineも構成できた。

しかし各列gapを`d_i=B_row-A_row-1`とすると初期総和は8である。Aが最初の4手で
`d_i>0`の列だけを通常stepすれば、各B手も総和を1減らすためB4後に全列が隣接する。
A5では実PUSHが必ず可能で、その直後のA/B row-sumは8/13なのでどちらも5枚同一行の
接続を持たない。Bは全列で無手となり、Aが`NO_LEGAL_ACTION`でply9勝利する。
これは全B応手を覆う単純万能策なので、draft2もprefix replay前に棄却した。
全合法プレイ15 ply以下という追加上界も、品質の根拠ではなく短さの診断である。

## 事前露出と次段

Plan31活性化前にはMOVE/CONNECT対HOP/CONNECTとPUSH/CONNECT対
MOVE_CAPTURE/CONNECTのsource案も比較した。前者の初稿にはA ply3策があり、後者には
捕獲で片側goalを恒久的に壊す構造リスクがあったため、固定2構造へ採用しなかった。
これらはdevelopment exposureであり、Plan31の選択証拠ではない。また固定ply層
`2^17`を一般条件にする案は、一部の整合的定義に数学的に適用不能だったため採用せず、
UNKNOWNを簡易な難しさ得点へ置き換えていない。

次はCELL-1一件だけを変更せずにfreezeする。新しいseedと、完全A7/B8 short screen、
exact100,000-state probe、T3/T3・T4/T4各4局の順序と全上限を登録前に固定する。
short screenのcensor、draw、PLY_LIMIT、winnerless、証拠不整合は技術失敗である。
exact UNKNOWNは未解決のまま中立であり、全gateと保存監査、単一全回帰が通るまで
人間へルールを推薦しない。
