> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0036 — 試遊画面を実装、最終回帰から専用URLの提供まで継続

これは全体回帰実行中の履歴checkpoint。現在の結果は
[最終受入れ・試遊案内](0036-acceptance-and-play-ja.md) を参照。

2026-09-10 JST。新しいユーザー指示に基づき、研究だけで終わらず実際に試せる
ゲームへ進めた。現在は **SOURCE_FROZEN / SITE_VALIDATED / FULL_REGRESSION_RUNNING**。
まだ完成URLを提供したわけではなく、公平性や楽しさの認定でもない。

## 今回できたこと

「キャッチアンドジャンプ」の未公開Siteを再利用し、試遊室「直線とL字」を実装。
標準は7×7・L字先手、比較は9×9・直線先手。Plan32の登録済みDSLとbyte一致し、
新候補や旧実験の再試行ではない。直線3対L字3の機械的非対称性、毎手3空きマスを
消費する有限性、合法手なし側の敗北を維持。引き分けやパスは追加していない。

- AI相手にどちらの役割でも遊べる。AIは専用worker内の固定プログラム、最大2手先、
  累積8,000探索node以内。毎手のChatGPT呼出し・対局情報の収集はない。
- 1台での2人対戦、形の向き、配置プレビューと確定、手番表示、勝者表示、再戦。
- 途中のやり直しは「中断」であり結果ではない。旧AI応答は同期キャンセルする。
- 日本語のルール、実験段階であること、AIと品質検証の限界を画面に明記。

オンライン友達対戦は未実装。この初回milestoneはユーザーがAIまたは同端末で
試せる状態であり、前のWeb機能要求の全てが完了したと扱わない。
人間の実際の試遊0、ブラウザ操作/視覚検証0。Sitesスキルに従い今回求められていない
ブラウザQAは行わず、非ブラウザの機能検証・元実装照合・buildを実施した。
local previewはHTTP200確認後に開く操作を行い、アプリ応答はqueuedだった。

## 検証証拠

独立した既存候補の短時間試遊根拠レビューPASS（公平性認定ではない）。
独立ソースレビューでAIキャンセル境界の補強を受け入れ、補強後レビューPASS。
最終Site検証session42701は実exit0。型検査、production build、Node12テスト全PASS。
7/9盤面×local/human-A/human-Bの6完全機能トレース、107遷移で元Pythonの
全合法手集合・占有・手番・勝者が一致。これは公平性を測る対局標本ではない。
AIの決定性、予算切れ合法fallback、終局後拒否、L字左上穴の使用済みanchor、
workerキャンセル/重複応答/不正応答/失敗と実production worker bundleも検査した。

[保存ログ類](plan0036-acceptance-evidence/site-tests.log)。最終テスト515.824708ms。
6恒久証拠ファイルはtmp元とbyte一致。独立saved-only監査PASS：Site90pinsと
Python206pins全一致、Site専用Git clean、両DSL byte一致、ログ/exit/現source整合。
親の研究repoはcommit/stageしていない。既存Python・fixture・raw結果は不変。

Site専用commit `9f5dcc8e0de21235f6bea191133ee1b456d35ab3` をpushし実exit0。
Sites版1を保存済み：[実ツール応答記録](0036-saved-site-version.json)。
ローカル監査はremote push/Sites応答の独立照会をしていない。これらはrootの実ツール
応答に基づく別証拠。保存版と非公開展開は別操作で、deployはまだ実行していない。

## 残る有限な手順

全体回帰session78275/PID60198は2026-09-09T16:32:14Zまでに1回開始し実行中。
原ログ・PID・終了記録は`/tmp/parity-forge-plan0036.iiP5fd/`。
既存全回帰は約90分かかる。実summaryとexitを受領し、保存証拠を照合して受入れる。
現時点で全回帰を成功扱いしない。凍結中のコード変更・二重起動はしない。

成功後、既存Siteのowner-only accessを再確認し、保存版1をprivate deployする。
展開の実成功を確認し、実URLと日本語ルール・限界を渡す。その時点まで継続する。
Site project_id `appgprj_6a9c2e806c8c8191a09aa182921017e4`。
version_id `appgprj_6a9c2e806c8c8191a09aa182921017e4~appgver_8eb312ab93b881919634348eb0607220`。
private accessはowner/allowlist1人/external0/groups0を確認済み。変更されていれば勝手に公開しない。

OpenAI Docsの[同じタスクを継続する定期実行](https://learn.chatgpt.com/docs/automations?surface=app)
を確認し、30分ごとの`parity-forge`（試遊版を届けるまで継続）をアプリで作成、ACTIVE。
既存Plan35追跡は削除済みと確認した上で、新しい目的の追跡を1つだけ作った。
テスト完了だけで削除せず、試遊URLの提供で終了する。変化のない待機は通知しない。
ローカルPCとアプリの稼働が必要。課金追加・利用枠リセット・無限の候補追加はしない。
