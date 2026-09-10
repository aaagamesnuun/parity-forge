> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan20 技術的受入れ

2026-09-05 23:21 JST。計算・証拠としてCOMPLETED / ACCEPTED。
ゲームの公平性・難しさ・面白さを認定する受入れではない。適格ゲームは0件のまま。

登録637c9ae144be5353343234697120e631d1a64d4eのisolated worktreeで、
全体テストは1,274件、5,150.027秒、OK(skipped=2)。session80972はexit0、
PID79233は終了。skip2件は、実アーカイブの大規模再構築に対する既存の
明示的opt-in試験。失敗・エラーはない。

ログ：/tmp/parity-forge-plan0020.q9qwHS/full-suite.log。
SHA256：74221e31227edf347bcae9730eebf51a769a7cbb0e32140113dd06a7a9f17c81。
独立確認で実末尾、skip理由、登録HEAD、全tracked Pythonと登録計画の無変更、
未追跡Pythonなしを確認した。共有checkoutと実行worktreeの保存ランは全バイト一致。
以前の保存限定監査は256ハッシュ・166 Python＋計画1件・全予定・30集計セルを確認済み。
今回の受入れ確認で対局・solver・棋譜再生を呼び直していない。

120局すべて勝敗あり、exactは完了2件／UNKNOWN4件、REVIEW_ONLY0。
UNKNOWNの1件には別の短い必勝証明がある。
[結果報告](0020-directional-race-findings-ja.md)と生の暫定ラベルは履歴として不変。
本書が、その後の正式な技術的受入れを記録する。

全体テスト・pilot・監査を再起動しない。Plan20を閉じ、既存APIを再利用した
Plan21の2条件へ移る。Plan21の新コードは別の全体テストで検証する。
