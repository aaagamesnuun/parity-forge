> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan30 技術受理と終了

## 判定

Plan30を計算・保存証拠として`COMPLETED / ACCEPTED`とする。科学的結果は
`NO_SELECTION`、選択候補はnull、`human_review_eligible=false`のままである。
技術受理は候補の公平性、深さ、面白さまたは遊べなさを認定しない。

## 登録と単一実行

- 登録commit：`27b5138fe3dddc22c4e1c24d261746f036174598`
- 登録tree：`c3425bfe4bc76e9fa570b5ff1950bfcd3fb564b2`
- 単一production preselection：2026-09-08 00:31:05.688764–00:34:02 JST、exit0
- 単一全回帰：session50297、PID19792、exit0
- full regression：1,403 tests / 5,398.474s / `OK (skipped=2)`
- log：`experiments/reports/0030-full-regression.log`
- log bytes：163,602
- log SHA256：`482a027b9db48e9605fc79c6cb5829275669cc9b88208142d0a73b9fb1d885bd`

全回帰は登録sourceのclean worktree
`/tmp/parity-forge-plan0030-regression.rhcvdY/checkout`で一度だけ実行した。
終了後PID19792は存在せず、worktreeのHEAD/treeは上記登録値と一致し、tracked/
untracked変更はない。Plan30固有34 testsはすべてlog内でpassし、FAIL/ERRORは0。
2件のskipは既存の明示的opt-in実証拠再構築testである。

00:28:39 JSTの最初のshell formは`scripts` import前提を満たさず、`main`、
runner、proposal load、output予約またはproduction callより前に終了した。
保存した257-byte log SHA256は
`76b12b9e58521d36fb296b6cbfc9e85b6ceea9169dfb7e29eea35e6cbfa25e10`。
二つの独立レビューどおりnon-production launcher preflightとして扱い、正しい
module invocationだけを単一production runに数える。

## 保存証拠

production runは56 attempt/result枠を116 canonical files、161,182 bytesで保存した。
実計算はshort query5件のみである。

- CELL-1 A7、CELL-2 B8、CELL-3 A7、CELL-4 A7：各100,000 missesで
  `UNKNOWN_CENSORED`
- CELL-2 A7：95,704 missesで`COMPLETE`、root value0、forced false
- 残り51枠：`NOT_STARTED_GATE_CLOSED`
- short misses合計：495,704
- production game / exact / replay / BFS：すべて0

rootと二つの独立saved-only auditは193 source pins、16 direct pins、114
publication hashes、schedule、gate、resource totalsをproduction callなしで再構成して
PASSした。isolated runとmain保存コピーの116 filesはbyte一致する。
終了後の別の独立closeout監査も193/193 source pins、16/16 direct pins、
114/114 publication hashes、34/34 Plan30 tests、登録commit/tree、clean worktree、
main/isolated全116 filesを照合してPASSした。

- summary SHA256：
  `8ebbd7d298ef437a2a3a24b90eb125e3930e22c79548f54cafd211dafd9c01b3`
- source-verification SHA256：
  `e8110bd56c229c5653941cb85ab17836b950c5bbf602d27e51133f94af0108d8`
- production log SHA256：
  `7c3255ddb7bde8fd1802e115d070fdfadff1fd9c138d2d5286bd4a481a9eceda`
- saved-audit log SHA256：
  `1a8e8313b5aadc79897ee9d479ee5863a8e4599e96afe445c680d2f3053790c4`

## 科学的解釈と次の番号

4件のcensorは固定100,000-node手法がply7/8の問いを決定できなかったことだけを
意味する。Plan30の静的T3条件は最大分岐15で一役72,300または93,990 nodesを
保証したが、同じ分岐のdepth7/8無転置上限は183,063,615 / 2,745,954,240で
あり、short gateのcapとは整合していなかった。従って候補品質の比較に到達する
前に閉じたのであり、UNKNOWNを難しさ、不公平、浅さまたは遊べなさへ変換しない。

Plan30の事前登録条件は遡及変更せず、追加query、対局、exact、BFS、seed、cap、
rerunを行わない。変更なしの生存候補を送る条件付きPlan31 branchは開かなかった。
研究を続ける次の独立単位は、未使用の時系列番号`Plan0031`である。これは
Plan30のretry、補充、候補versionまたは再分類ではない。
