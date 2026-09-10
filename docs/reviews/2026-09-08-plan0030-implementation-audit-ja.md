> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan30 登録前実装監査

## 結論

Plan30固有のrunnerとtestは実装・凍結済みで、登録阻害課題は残っていない。
これはproduction結果、公平性、難しさ、面白さ、人間playtest適格の証拠ではない。
4候補に対するgame、exact、selection query、replay、BFSはまだ0件である。

凍結SHA256：

- `scripts/plan0030_preselection.py`:
  `1c77d335c97b683f32ed52c47977b1af408031a70157b94ec1017054dc31d127`
- `tests/test_plan0030_preselection.py`:
  `8c1df20038c129173a7cca39796269681cb0723917ee44c42f3b5aed69f67a32`

## 検証結果

- Plan30 focused test：34/34 PASS。
- Plan20 exact、Plan24 play、terminal-searchの関連suite込み：65/65 PASS。
- `py_compile` と `git diff --check`：PASS。
- 独立read-only API/protocol監査：PASS、P0/P1残件なし。
- 独立read-only test/evidence監査：PASS、登録阻害残件なし。

testはstatic check、mock、機械的に別のtiny fixtureだけを使った。tiny fixtureでは
accepted Plan20 exactとPlan24 playの実wireがPlan30 validatorを通ることを確認した。
production4定義は実行していない。

## 固定した重要境界

- 全56 schedule slotをattempt/resultまたは明示closureとして保存する。
- Aがroot actorなのでBの短勝ちは`max(root values) == -1`だけで成立する。
- Pythonのbooleanを整数証拠として受理せず、decisive exact PVは1手以上とする。
- BFSは完全な`GameState` identityを使い、draw、PLY_LIMIT、winnerless terminalを
  技術失敗として拒否する。
- saved-only auditはgame/search/solve/replay/BFSを呼ばず、gate、disposition、
  resource、summary、source pin、hash、file/byte ceiling、failure locusを再構成する。
- bootstrapからfallback summaryまで、単発のpre/post-write例外を合成注入し、
  計算再実行なしで閉じて監査できることを確認した。
- 例外typeは256 UTF-8 bytes、messageは4,096 UTF-8 bytesに制限し、切詰め時は
  元byte数とSHA256を保存する。

同一artifactの回復保存まで連続して失敗する持続的storage faultでは、物理的に
完全な証拠を書けずCLI例外となり得る。この境界はproduction計算の再実行、resume、
seed差替えを許可しない。

## 次

production count zeroのまま、確定した2ファイルと計画記録を一度だけclean commitへ
登録する。そのcommitから単一preselectionと単一full regressionを別々のclean
worktreeで開始する。runnerが出す候補ラベルは最大でも
`PRESELECTED_TECHNICAL_ACCEPTANCE_PENDING`であり、saved/source auditとfull
regressionの実際の`Ran`、`OK`、exit0が揃う前にPlan31へ昇格させない。
