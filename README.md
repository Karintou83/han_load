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

## 連絡先の設定(User-Agent)

Wikimediaの[User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)に従い、
APIリクエストには連絡先を含めます。他の人が使う場合は、環境変数 `EDO_UA_CONTACT` に
**自分の連絡先(Wikipediaの利用者ページのURLなど)** を設定してください。未設定の場合は、作者の利用者ページが使われます。

```
# PowerShell
$env:EDO_UA_CONTACT = "https://ja.wikipedia.org/wiki/User:YourName"
# bash
export EDO_UA_CONTACT="https://ja.wikipedia.org/wiki/User:YourName"
```

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

## 個別の藩についてのメモ(東北の藩のTSV作成時)

- **湯長谷藩**: 初代・遠山政亮の在職は、湯長谷藩主としての1676年から始めています。これは、この藩がもともと湯本藩の藩主として始まったことに起因します(作者の説明)。
  政亮の湯本藩主時代(1670-1676)は、湯長谷藩主の在職からは外しました。湯本藩の項目は後で作り、その在職として別に入れる予定です。
- **矢島藩**: 途中で旗本になった時期があります。藩主として扱うのは
  生駒高俊(1640-1658)と生駒親敬(1868-1871)の2人のみです。
  旗本期の当主は在職(P1308)から外しましたが、親子・養子関係(P22/P40/P1038)は家系ドラフトに残しています。
- **黒石藩**: 最初は旗本でした。藩主として扱うのは
  津軽親足(1809-1825)・津軽順承(1825-1839)・津軽承保(1839-1851)・津軽承叙(1851-1871)の4人のみです。
  旗本期の当主は在職から外しましたが、家系ドラフトの親子・養子関係は残しています。
- **磐城平藩(要確認)**: 井上正経の退任と安藤信成の入封の年を、テンプレート上は1756年としています。
  根拠は、いわき市の資料(領主の変遷)に「宝暦6年(1756)5月に新領主として安藤信成が入封」とあることです。
  一方、日本語版Wikipediaの「井上正経」「磐城平藩」の記事は、井上氏の在任を宝暦8年(1758)まで、
  同年12月の浜松への転封としています(大坂城代・京都所司代の就任を挟むため、年がずれている可能性があります)。
  文献でさらに確認するまでは、1756年は暫定値です。
