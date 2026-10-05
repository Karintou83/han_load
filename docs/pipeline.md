# 他の藩へ横展開するためのパイプライン

## 方針

1. 人物リストの取得元は Category ではなく **Template** を正とする。
   `Template:○○藩主` は代数順に並んでいて信頼性が高い。Categoryは知藩事が含まれないなどの差がある。
   Categoryは補助的なクロスチェックにのみ使う。
2. 出自欄の自動分類(パターンマッチ)は行わない。
   「先代の子」の機械的処理はできるが、婿養子や記述の矛盾の判断は人間が行う。

## 手順

```
Step 1: 対象藩のWikipedia記事・藩項目のQIDを確認
Step 2: Template:○○藩主 のwikitextを取得し、代数順の人物タイトルを抽出
Step 3: 藩主の役職項目(P39用)の有無を確認し、なければCREATE
Step 4: 各人物のQIDを title→QID 変換で解決(wbgetentities, sitelinks=jawiki)
Step 5: 基本プロパティ(P31/P21/P106/P53/P97/P119/P1559)と
        P39/P580/P582/P1365/P1366 を生成
Step 6: 家系関係(P22/P40/P1038+P1039)はドラフト生成 → 人間がレビュー → 投入
Step 7: QuickStatementsへ投入
Step 8: SPARQL / GeneaWiki 等で反映を確認(P39での絞り込みクエリを使う)
```

実装は `code/create_han_lord_position.py` にあります。このスクリプトはTSVを出力するだけで、Wikidataへの書き込みは行いません。

## QuickStatements運用メモ

- V1形式(タブ区切り)を使う。
- 「No success flag set in API result」は、多くの場合ログインセッションの切れが原因。再ログインで解決する。
- 既存値の修正も、新規追加と処理速度は変わらない。同一値の重複投入は「変更なし」でスキップされる。
- 項目ページはすぐ反映されるが、Wikidata Query Service(SPARQL)への反映は数分〜1時間程度遅れることがある。
- 新規項目の作成は `CREATE` と `LAST` で行う。**ただし値の位置に `LAST` を使うと
  Error 422 (patch-result-invalid-value) になり、以降のLAST参照も無効になる**(赤穂藩での実投入で確認)。
  `LAST` は主語(1列目)にのみ使い、値には実際のQIDを書く。
- 大量投入(数十件以上)は、コミュニティのルール上ボットフラグの検討対象になり得る。十数件規模では不要と考えている。
- **必ず数件だけ試し打ちしてから本番投入する。**

## 既存の家系図可視化ツールの調査

| ツール | 特徴 | 峰山藩への適用 |
|---|---|---|
| GeneaWiki (Magnus Manske) | P22/P25/P26/P40を再帰的に辿って自動描画 | 不向き。婿養子(P1038)経由で外部の大名家系に広がり、100人上限に達する |
| Ancestors on Wikidata | `level` で遡る世代数を制限できる | 要検証 |
| wikitree (GitHub: mshd/wikitree) | TreantJSベースのOSS | 実装の参考 |

汎用ツールはP22/P40を無制限に辿るため、特定の藩に閉じた家系図には向きません。
自作ツールでは、まずSPARQLで「P39=○○藩主」の人物集合を取得し、
その集合の内部だけでP22/P40/P1038のエッジを描画する設計にします。
