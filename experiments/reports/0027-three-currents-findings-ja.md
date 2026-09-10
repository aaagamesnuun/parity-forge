> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan27「三潮流 SWAP対PUSH」固定screen結果

## 結論

固定screenは正常完了したが、baseで`NO_FLAG`。人間が確認する候補には
進めない。後段48局は事前規則どおり`NOT_STARTED_GATE_CLOSED`であり、
追加seed、再試行、予算増加、別先手、配置調整、閾値緩和は行わない。

登録commitは`ca3451bb478aed518e34ff5e69ad362f64771d69`。単一runは
`plan0027-three-currents-swap-push-v1`。exactは100,000状態で
`UNKNOWN_CENSORED`、外部PV replayなし。base32局は全てA/Bどちらかの
`GOAL`で完了し、draw、game censor、failureは0。観測手数は7..22plyで、
各局の確認済みprefixは1回だけreplayされた。全合法手の決着は別途Phi54の
減少証明が担い、sampleの決着だけを証明にしない。

## Base結果

結果は先手A勝数。条件を合算して公平性とは読まない。

| 条件 | 完了 | A勝/B勝 | 固定gate | 判定 |
|---|---:|---:|---:|---|
| T4/T4, seeds900..915 | 16/16 | 12/4 | A勝5..11 | **fail** |
| T3/T3, seeds900..915 | 16/16 | 12/4 | A勝4..12 | pass |

T4/T4は許容上限をAの1勝分だけ超えた。したがって`base_pass=false`で、
後段48局を開かない。T4初手に非0の最善終局値はなく、
`SHORT_FORCED_RESULT`ではない。記述的合計A24/B8も選考や公平性の根拠には
使わない。

同じ16 seedではT4/T4とT3/T3の勝者列が16/16一致し、8局は全action列も
一致した。両条件ともA勝率75%だったことは、先手側への偏りとseed/
tie-breaking依存の可能性を示す記述的所見であり、万能必勝や完全解析の
証明ではない。

## 条件付き作用と選択証拠

保存された行動直前盤面と、選択・適用が一致したactionだけから再構成した。

- 実際に相手駒のいる移動先へ入ったA-SWAP：9/32局、9 actions。
- 実際に相手駒を押したB-PUSH：5/32局、6 actions。
- scheduled T4が水平手を選んだ局：A15局、B16局。
- T4が同一局内で+1/-1の合法選択肢を持った戦術証拠：A8局、B3局。

これらのdistinct-game下限は観測base内では満たした。しかしT4/T4の勝数
gateを通らず、全80局完了条件も満たさないため、人間候補にはならない。
作用回数が少ないことも、このgameを相互作用豊富と認定する根拠にはならない。

## 有限決着・計算・監査

A駒ごとに`qA=(4-r)+(4-c)`、B駒ごとに`qB=r+c`を置き、
`Phi=sum(qA)+2sum(qB)`とする。初期値54で、Aの空所移動/SWAPは-1/-3、
Bの空所移動/PUSHは-2/-1。したがって全合法手で正整数Phiが減少し、全合法
手順は54ply以内にA/Bどちらかの勝利で終わる。cap55とdrawは到達不能である。
保存された495遷移でも減少を確認したが、構造証明はこのsampleに依存しない。

charged node合計はA37,321/B33,260、1局最大はA2,190/B2,076、1decision最大は
T4が348、T3が116。全て登録済みの役別41,958保証と100,000 cap内だった。
exact予算切れは難しさの証明ではない。

独立保存物監査はPASS。70 canonical envelopes、68 publication hashes、
登録source186 pins（184 Python＋active plan＋proposal）、81予定/33実施/
48 gate-closed、全decision、合法手、node chain、terminal、replay、Phi、作用・
水平・戦術集計が一致した。artifact raw-SHA map digestは
`8523cc4579f4261b918d2701687b7986b07abe0d26c2a357d24bffaf922d59d1`、summary
raw SHA256は`9c40cd83898e197f36e250189762e99938dc9bba725a9b78d3a2931486aebdf3`。
隔離runをmainへ70ファイルbyte-identicalで1回だけ保存した。

## 主張境界と実行記録

全回帰と同時に行った最初のshell起動は、module import前のpath設定ミスで
exit1となった。`run_pilot`、出力予約、候補読込、exact、game、replayには
未到達で、二つの独立レビューがproduction attemptではないと確認した。
ログは`/tmp/parity-forge-plan0027.mTxbu8/pilot-launcher-failure.log`、SHA256は
`63b0dfefcf188ac891442e6cd9e84a1ecd5673ae64920b7487ddc837066358e6`。
正しいmodule起動による最初で唯一のproduction pilotだけが上記結果を作った。

rawの`fairness_established`、`hardness_established`、`fun_established`は全て
false。exact UNKNOWN、混在勝敗、作用、水平手、戦術選択を、人間同士の
公平性、学習性、奥深さ、面白さに読み替えない。公開範囲で否定した短い
強制勝ちとpure H/Q方策以外の長期・hybrid戦略も未解明である。

このrunの技術的受理は、実行中の登録source全回帰が完了して独立closeout
監査を通るまで暫定である。pilot、exact、32局、replayを再起動・補充しない。
