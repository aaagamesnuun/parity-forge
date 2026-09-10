> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0016・0017 — 計算と証拠の受入れ完了

2026-09-05。新しいゲームの合格ではなく、保存済み実験の技術的な受入れです。

- 実行コマンド：`PYTHONPATH=src python3 -m unittest discover -s tests -v`
- 結果：`Ran 1219 tests in 5123.653s`、`OK (skipped=2)`、終了コード0。
- 2件のskipは既定の大規模な旧証拠再構築。FAIL/ERRORはありません。
- 実行時のコードは `eb9e53fcc`。終了まで src/research/scripts/tests の変更なし。
- ログ：`/tmp/parity-forge-plan0016-tests.VsEzwh/full-suite.log`
- ログSHA-256：`a51d8d15b1d59230af5030a0fba399646ee74af83c67f0be535592fa37370c8b`。
- rootと独立レビュー担当の両方が、終了行・ソース不変・証拠ハッシュを確認しました。

Plan 0016は23配置・3,680局、計算打切り／実行失敗／未実施はいずれも0。
既に完了した全棋譜検証とsource-verificationを受け入れました。再対局・再検証はしていません。
保存計画のSHA-256は `e689592ce9f279c4c3cb9089d88b979ea3c317cc912d5752583543d35b48e0aa`、
manifestは `3c54f7b753ce56d2d6fc28e77c6d8eddc0a5ebd8df11d151bc15a6068cb6814b`。

Plan 0017は1回のexact解析、1,381状態、DRAW。既に実施した1回の外部PV再生と
入力・計画・ソース照合を受け入れました。再解析・追加再生はしていません。
resultのSHA-256は `378da30af6bb4762b6ce9a4286d13c2aede2c9cf8c614d2d3c9b3e4c1cc0b13b`。

両実験の元データにあるPROVISIONAL表示、Plan 0016の登録計画の元のチェック欄は
実行当時の記録として変更していません。この別文書が後日の受入れ記録です。

ゲームの評価は変わりません。raw flagのうち3条件は短い必勝手順、残りcarrier 7は
実際に引き分ける合法手順があり、D-055の必須条件を満たしません。
公平性・戦略性・面白さを満たす発見済みゲームは、まだありません。
