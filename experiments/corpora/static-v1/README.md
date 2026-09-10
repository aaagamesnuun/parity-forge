> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Static v1 corpus

`corpus.json` is frozen evidence for parser and cheap-diagnostic behavior. It was
manually constructed before evaluator tuning and must not be edited to make tests
pass. A genuinely wrong expected classification requires a new decision record and
preferably a successor corpus ID, preserving this version.

This first corpus is deliberately scoped to static phenomena. Dominance, draw
rate, choice quality, game length, solved openings, and agent disagreement require
play evaluators and will be added in successor frozen corpora.
