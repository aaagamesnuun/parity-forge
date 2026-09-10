> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan25「段違いの直交hunter」固定screen結果

## 結論

固定screenは正常完了したが、baseで`NO_FLAG`。人間が確認する候補には
進めない。後段48局は事前規則どおり`NOT_STARTED_GATE_CLOSED`であり、
追加seed、再試行、予算増加、mirror実行、閾値緩和は行わない。

登録commitは`8b15e1ea44831e5af45d73f27f3c7c4af4be3e3b`。
単一runは`plan0025-staggered-orthogonal-hunters-v1`。exactは100,000状態で
`UNKNOWN_CENSORED`、外部PV replayなし。base32局は全てA/Bどちらかの
`GOAL`で完了し、draw、censor、failureは0。観測手数は7..19plyで、各局の
確認済みprefixは1回だけreplayされた。全合法手の決着は別途23ply終了証明が
担い、sampleの決着だけを証明にしない。

## Base結果

結果は先手A勝数。条件を合算して公平性とは読まない。

| 条件 | 完了 | A勝/B勝 | 固定gate | 判定 |
|---|---:|---:|---:|---|
| T4/T4, seeds500..515 | 16/16 | 7/9 | A勝5..11 | pass |
| T3/T3, seeds500..515 | 16/16 | 15/1 | A勝4..12 | **fail** |

T4初手に非0の最善終局値はなく、`SHORT_FORCED_RESULT`ではない。限定的な
戦術選択証拠はA3局/B9局だったが、base不通過を救わない。記述的合計は
A22/B10でも、深さの異なる条件を混ぜた値なので選考には使わない。

Plan24ではT3/T3がA12/B4、Plan25ではA15/B1で、片方のBを1手前進済みに
する変更が浅い同型agentの先手偏りを改善しなかった。一方T4/T4はA7/B9。
これは深さ3と4で挙動が大きく変わる観測であり、人間の奥深さの証明ではない。
配置の単調なB強化も立証されない。

## 主張できないことと次の扱い

exact予算切れは難しさの証明ではない。T4自己対戦の混在勝敗、depth差、
戦術選択も、人間同士の公平性、学習性、面白さを確立しない。そのためrawの
`fairness_established`、`hardness_established`、`fun_established`は全てfalse。

次は「Bをさらに前へ置く」だけでなく、T3でAの短い到達脅威が一方的になり、
T4で逆転する具体的trace構造を保存結果から調べる。新案は短い万能必勝、
dead goal、23ply終了、100,000 node上限を先に確認し、別hash・別plan・
新seedでのみ実行する。

独立保存物監査はPASS。70 envelopes、68 publication hashes、登録sourceの
182 pins（180 Python＋plan＋data）、81予定/33実施/48 gate-closed、全セル、
node、Wilson区間、replay、23ply上限、戦術証拠が一致し、driftはなかった。
本runの技術的受理は、同時に開始した登録sourceの全回帰が完了するまで
暫定である。
