# 江戸時代藩主のWikidata整備ツール(峰山藩を起点に)

江戸時代の藩主について、Wikidataの項目を整備するための調査記録とスクリプト集です。
最終的には、整備したデータから藩主の家系図を可視化するサイトを作ることを目指しています。

## 内容

- `code/create_han_lord_position.py` — 「○○藩主」の役職項目と各藩主の基本ステートメント、家系ドラフトを、
  QuickStatements V1形式のTSVとして生成するスクリプト。**Wikidataへの書き込みは行いません。**
- `code/*.tsv`, `code/*_report.txt` — 小城藩・鹿島藩・佐倉藩・赤穂藩・津山藩で生成した出力
  (ドラフトを含む。未レビューのものがあります)
- `docs/` — 調査結果とモデリング方針の解説
  - [`authority-databases.md`](docs/authority-databases.md): 典拠データベースの調査結果
  - [`modeling.md`](docs/modeling.md): Wikidataのプロパティ設計(家系・在職)
  - [`pipeline.md`](docs/pipeline.md): 他の藩へ横展開するためのパイプライン設計とQuickStatementsの運用メモ
  - [`status.md`](docs/status.md): 峰山藩主12代の基礎データと未解決事項

## 使い方(概要)

```
pip install requests
python code/create_han_lord_position.py prepare-han <藩名> <旧国名>
```

生成されたTSVは、**必ず内容を目視で確認し、数件だけ試し打ちしてから**
[QuickStatements](https://quickstatements.toolforge.org/) に貼り付けてください。
詳しい引数は `code/create_han_lord_position.py` 冒頭のdocstringを参照してください。

## 注意

- 家系関係(P22/P40/P1038/P1039)のドラフトは、Wikipediaの記載から機械的に作ったものです。
  婿養子・養子の判断などは人間によるレビューが前提で、未確認の項目があります
  (詳細は [`docs/status.md`](docs/status.md))。
- Wikidata側のステートメントの多くは、現時点で出典(P248/P854等)が付いていません。

## ライセンス

- コード(`code/*.py`): MIT License(`LICENSE`)
- データ(`code/*.tsv` など)と文書(`docs/`): [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/deed.ja)(Wikidataの方針に合わせています)
- データの元になった日本語版Wikipediaの記事は、CC BY-SA 4.0 です。
  記述をそのまま転載している部分がある場合は、そちらの条件に従ってください。
