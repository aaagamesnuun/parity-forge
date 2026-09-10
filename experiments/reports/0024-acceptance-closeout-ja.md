> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan24 技術受理と終了

## 判定

Plan24を計算・保存証拠として`COMPLETED / ACCEPTED`とする。ゲーム判定は
`NO_FLAG`のままで、人間試遊候補ではない。raw summaryの
`PROVISIONAL_UNTIL_FULL_REGRESSION`は実行時点の不変記録なので変更せず、
このcloseoutが後続の技術受理を記録する。

## 登録と実行

- 登録commit：`10919fb9ccc4a03bafd408f172f69e61ac84e290`
- 単一pilot：session60252、exit0
- 単一全回帰：session13168、exit0
- worktree：`/tmp/parity-forge-plan0024.YBi3xF/checkout`
- full-suite：1,315 tests / 5,452.647s / `OK (skipped=2)`
- log SHA256：`59f567ea1cc056f725f930e0dc7699ae76f5e5050b2f29c310606e9ab6c893cc`

2件のskipはいずれも明示的opt-inの再構築テスト。登録HEADは一致し、tracked
sourceに差異はない。全17件のPlan24 adapter/screen testも全回帰log内で
個別にpassした。

## 保存証拠

独立監査は次を確認してPASSした。

- 166 envelopes、164 publication hashes、180 source pins
  （178 Python＋active plan＋proposal）が一致。
- 固定81予定を全て実施。exact UNKNOWN100k、外部PV replay0。
- 80局は全て決着し、draw/censor/failure/unstarted0、各prefix replay1。
- 7セル、node集計、Wilson区間、戦術証拠、7..19plyと23ply上限が一致。
- isolated run全166ファイルとmain保存コピーがbyte一致。

## ゲーム判定の保存

唯一の固定gate未達は`R/T4`で、B側T4が6/8勝、必要条件は7/8だった。
他条件が通ったことやexactの予算切れを、公平性・難しさ・面白さに読み替えない。
閾値緩和、seed追加、再実行、予算増加、mirror実行はしない。詳細は
[Plan24結果](0024-two-orthogonal-hunters-findings-ja.md)。

Plan24のpilot、exact、80局、replay、全回帰を今後再起動・再開しない。
次の段違い配置は別hash・別plan・新seedとしてのみ扱う。
