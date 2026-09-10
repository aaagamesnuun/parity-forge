> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan40 実装チェックポイント

2026-09-10 JST。SOURCE_FROZEN / FULL_REGRESSION_RUNNING。
実装と専用テストは通過したが、全回帰も対局実験も未検収。

「架橋と転色」の登録規則を6個の新規Pythonファイルへ実装した。旧206個の
ソース、過去のimmutable結果、公開Site/GitHubは変更していない。

- core: 厳密なDSL、原子的な架橋・転色、手番/資源/石数の検査、接続勝利、
  JSON往復、ルールと有限一意終局の説明。
- search: 固定した接続距離評価、random/greedy/depth最大3の探索、完成深さの
  保持と全遷移課金。キャッシュは不変の盤面隣接表だけで、探索結果は蓄積しない。
- runner: 登録とソース・全回帰実成功の封印、固定1回claim、計算打切りUNKNOWN、
  累積出力量、独立した座標集合の処理による全prefix照合。

## 確認済み

1. focused1: 48tests / 0.146s / actualexit0（chunk82406c）。
2. 独立監査で、継承CPUhard limitが登録値より低い場合の不整合を発見。
   claim取得前に拒否するガードとmockテストを追加した。ゲーム規則・方策・
   予算は変更していない。
3. focused2: 49tests / 0.129s / actualexit0（chunk41e8c8）。
4. 最終独立ソース/hash監査PASS、旧206pinと新6pinのroot照合もexit0。
   本番のclaim/出力先は未作成。登録・契約の凍結入力も未変更。

専用テストは小型の機能fixture、制御した探索木、mock/temp出力だけを使った。
新しい発見実験の対局・exact queryは0。専用テストの残り1回は消費しない。
凍結根拠は [source-freeze](0040-source-freeze.json)、全49件のログは
`plan0040-acceptance-evidence/focused-2.log` に保存した。

## 実行中の全回帰

必須コマンド `PYTHONPATH=src python3 -m unittest discover -s tests -v` を
一度だけ開始した。session54037、shellPID13614、PythonPID13615。
2026-09-10T08:22:57Zの観測時点でPython稼働とログ進行を確認。
[起動receipt](0040-full-suite-launch-receipt.json) はRUNNINGの歴史的記録として保存する。

次回は同じsession/logを引き継ぐ。起動し直さず、実exitと全回帰サマリーを
確認して別の完了receiptを作る。それまでは受理・manifest封印・16局実験を
始めない。既存の時間ごとの定期実行を維持し、新しいtimerは作成していない。

全回帰が合格しても、公平性・奥深さ・面白さ・人間が試す価値の判定には
ならない。これらは今回まだ評価していない。
