> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0037 — オンライン友達対戦を実装、全体検証から公開まで継続

**履歴:** 以下は保存時点の記録。現在はD-076により版2を公開済み。
[公開結果・遊び方](0037-online-publication-ja.md)。全回帰の検収は引き続き別途確認中。

2026-09-10 JST、20:01:15Z checkpoint。
SOURCE_FROZEN / SITE_VALIDATED / FULL_REGRESSION_RUNNING。
公開版はまだPlan36版1。オンライン版2は保存済みで、公開済みではない。

## 実装と遊び方

「友達とオンライン対戦」を選び、盤面と自分の役割を選んで部屋を作る。
招待リンクをコピーして友達に送り、相手が「この部屋に参加する」を押す。
リンクを持つ最初の参加者が相手。アカウントは不要で、AI・同端末対戦も維持する。
全員に公開される部屋一覧、チャット、ランキングは追加していない。

固定TILE7/B・9/AのDSLと既存tile.tsは不変。毎手3マス消費し置けない側が負け。
切断と部屋の24時間期限は外的な中断であり、引き分けや敗北ではない。
再戦は新しい部屋を作る。相手の盤面を一方的にリセットしない。

D1を席と棋譜の正本とし、クライアントの役割・盤面・勝者を採用しない。
サーバーは固定DSLと最大27手の保存履歴から再構築し、合法性・手番を検証する。
招待と席の強いランダム資格情報は分離し、DBにはhashのみ保存。
招待はURL fragment、席tokenはAPI headerを使用し、queryやログには出さない。
作成・参加の送信前に端末内へ資格情報を保存。保存不可なら席確保を始めない。
同じ資格情報の再送と着手IDの再送に対応し、version条件付きSQL更新で競合を拒否。
古いpollの成功・失敗は新しい部屋activationを上書きしない。

通常3秒間隔、非表示15秒、失敗時最大30秒まで待って同期する。部屋は最大500件。
24時間後は利用不能になり、新規作成時に期限切れを最大20件ずつ削除する。
期限と物理削除の時刻は同一と約束しない。端末保存は資格情報だけで、盤面の正本はD1。
オンラインでの保存を画面に明記した。公平性・面白さ・強固な乱用対策の認定はない。

## 検証

独立設計・ソースレビューを実施。旧poll404が復帰成功を上書きする境界と、
保存pending guestをroom URLから再参加させる境界を修正し、最終source review PASS。
追加2テストはpure lifecycle/routingであり、React hook実動作やブラウザQAではない。

最終build/typecheck/28 Site tests成功、session18389実exit0（chunk3b9f58）。
16 room tests＋既存12 tests、542.35525ms。席の認可・join競合・CAS着手・重複送信・
不正手・終局後拒否・期限前後・容量・保存失敗・古い応答を検査。
既存6 traces/107 transitionsのPython照合とproduction worker bundleテストも成功。

ローカルD1に生成migrationを1回適用、2 statements/実exit0。
非ブラウザの実HTTPで2クライアントの機能検査：7×7で16手、9×9で26手、計42手。
両端末の盤面一致・再送・再取得・一意な終局を確認、1,699ms、実exit0。
このHTTP検査後の変更はclientの上記2境界のみで、サーバー/DSL/migrationは同一。
各traceは機能検査であり、新しい公平性標本、episode2、人間試遊ではない。
人間試遊0。ブラウザ操作/スクリーンショットなし。既存previewHTTP200、開く操作は
queued応答で安定tab IDは返らなかった。dev server52627は公開まで維持。

103 Site pinsと206 Python pinsを保存し一致確認。Site専用commit
`7642e98a4fafa30821ac4c2dbf5f9dd6d9e98f6e`、19 files/786追加25削除。
Python206、既存tile.ts、DSL、旧研究・raw結果は不変。親repoはcommit/stageしていない。
8恒久証拠は[証拠ディレクトリ](plan0037-acceptance-evidence/final-site-tests.log)に保存。
最終Site log SHA256 `eb119b01acf5c356057712f6bf8de5f14acabf2fceba127b25dfc21bb33889fa`。

Sites building/hostingスキルに従い、既存D1・依存版・公開アクセスを維持して構築。
新schemaと生成migrationを保存・点検、archiveに含めた。公開DBのnative overviewは
DB binding/ユーザーtable0/省略0だった。既存tableを変更するmigrationではない。
[Cloudflare D1の一次資料](https://developers.cloudflare.com/d1/worker-api/d1-database/)
を確認し、各API処理はfirst-primary sessionから準備済みSQLを使う。

## 残る有限な手順

Pythonの必須全体回帰session80276/PID80326は1回実行中。
開始から23:42経過時も動作、前段のinitial-structure差分検査へ進行している。
ログ/exit/pinsは`/tmp/parity-forge-plan0037.Vr5Mt5/`。二重起動しない。
実際の最終summary/exitが出るまで全体受入れ成功とはしない。
Python固定206の回帰と、Site固定103の最終build/testsを分けて照合する。

ソースpush実exit0の後、同じarchiveでSites版2を保存した。
[実ツール応答](0037-saved-site-version.json)。まだdeployはしていない。
全体回帰受入れ後、public accessを再確認してこの保存版2を同じSiteへ公開する。
実deployment succeeded後に、既知URLでscripts/check-online.mjsを1回、2部屋だけ実行し、
匿名pageも確認する。tokenを記録しない。日本語で実URLと作成→招待→参加手順を渡す。
既適用migrationを改変せず、失敗が許可外対応を要するなら根拠を残して停止する。

以前の継続希望と今回のオンライン要望に沿い、OpenAI Docsの
[同じタスク内の定期実行](https://learn.chatgpt.com/docs/automations?surface=app)を確認。
アプリで30分間隔の`parity-forge`（オンライン対戦の公開まで継続）を1つ作成、ACTIVE。
既存同名追跡がないことを先に確認した。状態不変では通知せず、公開・意味ある失敗・
必要な判断のみ通知。実オンラインURL提供後にこの追跡を削除し、dev serverを止める。
ローカルPCとアプリの稼働が必要。追加候補研究・課金・外部募集は自動で始めない。

最終独立saved-only checkpoint監査PASS。103/206現pins、旧Python pins、8copies、
最終logs/exits、既存tile.ts/DSLの不変、archive/保存版2を照合し差異なし。
rootのremote実応答を照合した範囲で、監査者が別途remoteを照会したわけではない。
20:05:10Z観測で全体回帰PID80326は29:37経過して引き続きpublic master-domain検査。
最終summary/exitは未取得、source clean/pins一致。公開までの有限追跡を維持する。
