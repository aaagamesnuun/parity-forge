> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan26「前進した直交hunter対」固定screen結果

## 結論

固定screenは正常完了したが、baseで`NO_FLAG`。人間が確認する候補には
進めない。後段48局は事前規則どおり`NOT_STARTED_GATE_CLOSED`であり、
追加seed、再試行、予算増加、mirror実行、閾値緩和は行わない。

登録commitは`0bf342f04f833505706a8564755d29217cb3f6ff`。
単一runは`plan0026-two-forward-orthogonal-hunters-v1`。exactは100,000状態で
`UNKNOWN_CENSORED`、外部PV replayなし。base32局は全てA/Bどちらかの
`GOAL`で完了し、draw、game censor、failureは0。観測手数は7..19plyで、
各局の確認済みprefixは1回だけreplayされた。全合法手の決着は別途23ply
終了証明が担い、sampleの決着だけを証明にしない。

## Base結果

結果は先手A勝数。条件を合算して公平性とは読まない。

| 条件 | 完了 | A勝/B勝 | 固定gate | 判定 |
|---|---:|---:|---:|---|
| T4/T4, seeds700..715 | 16/16 | 12/4 | A勝5..11 | **fail** |
| T3/T3, seeds700..715 | 16/16 | 13/3 | A勝4..12 | **fail** |

両セルとも許容上限をAの1勝分だけ超えた。したがって、後段48局を開く
条件は満たさない。T4初手に非0の最善終局値はなく、
`SHORT_FORCED_RESULT`ではない。限定的な戦術選択証拠はA3局/B4局だったが、
base不通過を救わない。深さの異なる条件を混ぜた記述的合計A25/B7も、
選考や公平性の根拠には使わない。

Plan24のbaseはT4/T4 A10/B6、T3/T3 A12/B4、Plan25はA7/B9とA15/B1、
Plan26はA12/B4とA13/B3だった。小さな初期配置変更と新seedで浅い同型
agentの勝敗が動いており、どの座標変更も単調な強化・弱化とは立証されない。
今回の「横対称へ戻す」変更も、固定screen上の先手偏りを解消しなかった。

## 計算・監査と主張境界

charged node合計はA91,626/B84,212、1局最大はA5,879/B5,414で、登録済みの
役別上限と100,000 cap内だった。exact予算切れは難しさの証明ではない。
混在勝敗、depth差、戦術選択も、人間同士の公平性、学習性、面白さを
確立しない。そのためrawの`fairness_established`、
`hardness_established`、`fun_established`は全てfalse。

独立保存物監査はPASS。70 envelopes、68 publication hashes、登録sourceの
184 pins、81予定/33実施/48 gate-closed、全セル、node、replay、prefix、
23ply上限、戦術証拠が一致し、driftはなかった。mainへ保存したrunは隔離
worktreeの70ファイルとbyte-identicalである。

次の候補がある場合も、このPlanを救済せず、別の研究質問、別hash、別plan、
新seedとして事前登録する。まず短い万能必勝、dead goal、有限決着証明と
計算上限をsource側で確認する。本runの技術的受理は、同時に開始した登録
sourceの全回帰が完了するまで暫定である。
