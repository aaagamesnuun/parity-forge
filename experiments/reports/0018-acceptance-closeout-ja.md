> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan18 — 計算・証拠の正式受入れ

2026-09-05。ゲームの合格ではなく、既存の固定実験の技術的受入れ。

- 全回帰：`PYTHONPATH=src python3 -m unittest discover -s tests -v`。
- 実測：1,259件、5,171.636秒、`OK (skipped=2)`。
- session44075はexit0、PID64445は終了。再起動していない。
- 2件のスキップは大規模な旧保存証拠再構築の明示的opt-inテスト。
- ログ：`/tmp/parity-forge-plan0018.JxQbr8/full-suite.log`。
- ログSHA256：`1c7ed6d2e63a362a4fc4093e286a066c7a604646faf54a2bbfb40cd984d36fc7`。
- rootと独立担当が、登録点d1364e81bからsrc/research/scripts/testsに追跡差分なし、
  保存点ebaeb054aからPlan18生データに追跡差分なしを確認した。
- 登録済みの証拠検査・ソース照合は既に完了済み。追加対局・解析・再生・inspectなし。

12配置・1,920局・24厳密結果と、その暫定ラベルは変更しない。
現在の全製品条件を満たすゲームは未発見。D-057の簡単には解けない複雑さも未達。
[科学的結果と限界](0018-no-draw-game-findings-ja.md)はそのまま保持する。
