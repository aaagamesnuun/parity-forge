> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0032：技術受入れと限定試遊への引き渡し

2026-09-08。今回の実装・1回の診断は完了した。次は任意の人間の感想を待つ。
試遊ガイドと起動手段を用意したのであり、面白さや公平性を認定したわけではない。

## 技術受入れ

唯一の全回帰は `PYTHONPATH=src python3 -m unittest discover -s tests -v`。
session81830/PID48556は終了し、実exit0を2026-09-07T21:26:50Zの確認までに回収した。
summaryは **1,437 tests /5,386.118秒 /OK (skipped=2)**。
新規34件も凍結最終版で全てok。再テストや再実行は行っていない。

独立の保存証拠監査はPASS。現在の190 Pythonファイルのhash、manifestの9依存pin、
全34新test名、全回帰log、pilot/全回帰の別々の終了receiptが一致した。
新6ファイルは1,899行で、2,000行・6ファイルの境界内。既存Pythonや凍結fixtureは
変更せず、新たな外部依存やAPI課金を導入していない。

[全回帰receipt](0032-full-suite-exit-receipt.json)と
[恒久保存した証拠](plan0032-acceptance-evidence/)を参照。

| 保存物 | SHA256 |
|---|---|
| full-suite.log | `de4896da1f5abf11e5420b67f37646db6f281de82d00751433d93f17044b011c` |
| source-pins.sha256 | `615a484c76711915ecd58e5f7847cf6cae5aa99b15c2441ead19e38623f833f4` |
| pilot.log | `3fdff9e0c7019975f6028a3e8143b9958ae98604d37ada9fde7a2f9c3792ff97` |

元の `/tmp/parity-forge-plan0032.yFsHOq/` と恒久コピーはbyte hash一致。
receiptの観測時刻を、実際のプロセス終了時刻と偽ってはいない。
過去pilot receiptの当時のFULL_REGRESSION_RUNNINGも上書きしていない。

## 実験は1回で終了

8定義・2骨格、64局すべて通常決着。CPU308.365877秒、対局打切り/引き分け/
未開始/random fallbackは0。ゲーム探索184,809遷移、1,421 ply。
短手数queryは15 COMPLETE false/1 UNKNOWNで、計87,071遷移。
UNKNOWNを引き分けやfalseに変えていない。3-ply陰性はソース上既知なので、
深さや難しさの発見には数えない。詳細は[結果](0032-episode1-findings-ja.md)。

モデルを毎手・毎局呼ばない検証経路は実際に機能した。ただし今回の設計・実装・
レビュー・解釈にはモデルを使っており、総token消費が0だったわけではない。
総token数は取得できない。1回の成功で探索方法一般の優秀さを証明したとも扱わない。

## 人間に渡せる2つの候補

1. **I/L配置7×7・B先手**。短い操作性・駆け引き確認の第一候補。
2. **I/L配置9×9・A先手**。少し長い選択を見たい場合の比較用。

全合法プレイの有限・単独勝者性、機械的非対称性、宣言した短手数queryの完了、
技術受入れ、具体的な既知の弱点、紙/ターミナルによる最小の試し方が揃った。
限定ソースレビューでも、直接鏡映・固定終局手数パリティ・形状包含から人間試遊を
無意味にする明白な万能戦略は見つからなかった。ただし最適必勝法不在の証明ではない。

9×9の4勝4敗は方策で勝者が反転した結果で、公平性とは呼べない。7×7の5勝3敗も
小標本かつ方策依存。探索はしばしば1手先で、強いAIへの耐性・人間の上達・面白さは
未確認。TRAIL族のB側優勢も普遍的な欠陥とは証明されていない。

[試遊ガイド](../../docs/reviews/2026-09-08-finite-space-play-guide-ja.md)は登録DSLの
静的な `describe_rules` 出力とsourceから導出した。2つのprototype JSONは登録wireと
完全同値・semantic hash一致を確認済みで、新しい候補ではない。
独立handoff監査は先手、形、配置、終局、座標、CLI、q、中断、20分の手動上限、
紙/terminal限定の説明を照合してPASS。局間の担当交替という文言も明確化した。
この監査で実際の対局や人間UXを追加検証したことにはしていない。

## ラベルと停止点

rawのhuman_review_eligible=false、disposition、勝敗・UNKNOWNは一切変更しない。
別の[handoff record](0032-human-handoff.json)に、品質認定ではない
UNSCORED_EXPLORATORY_HANDOFF_READYを記録する。人間試遊0、外部テスター0、
サイト作成/公開0。試すかどうかはユーザーが決め、お願いする時間は合計20分まで。

今回の自律作業の出口には到達したため、既存の30分ごとのheartbeat
`parity-forge`（Parity Forge 研究継続）は2026-09-07T21:40:10Zにapp toolで削除した。
OpenAI Docsスキルに従って[公式の定期タスク案内](https://learn.chatgpt.com/docs/automations?surface=app)
と現在の設定を確認し、app経由で既存の1件だけを終了した。試作や研究データ、
このタスクは削除していない。定期継続が再び必要なら、その時点で再設定できる。

これはプロジェクト放棄でも、3episodeの上限を使い切る義務でもない。現在は待つべき
計算がなく、残る不確実性には実際の人間の反応が有用である。第2episodeやサイト版を
自動で追加せず、任意の感想または次の方向の入力を待つ。Plan32はその引き渡し記録
としてactiveに残す。Plan31・閉じた旧研究・保護領域は再開しない。
