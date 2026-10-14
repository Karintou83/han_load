"""
四国で、Wikidataに藩項目(jawikiのsitelink付き)が無い藩の「藩」項目を新規作成する
QuickStatements V1 TSVを作る。Wikidataへの書き込みは行わない。
(make_han_items.py は関東の野本藩・東方藩の投入済みTSVを再生成してしまうため、別ファイルにした。)

使い方(code/ フォルダで):
    python make_han_items_shikoku.py     # new_han_items_shikoku.tsv を生成

投入前に必ず確認すること:
  - Wikidataで「松山新田藩」を検索し、すでに項目が存在しないか確認する(重複作成を避ける)。
    存在するがjawikiの記事にsitelinkが無いだけなら、新規作成せずsitelinkを付けて
    han_qid_overrides.json に既存QIDを登録するだけでよい。
  - 藩項目の標準構成(P31の値など)は、既存の藩項目(峰山藩 Q1073012 など)に合わせて extra に足す。

投入後の手順:
  1. new_han_items_shikoku.tsv をQuickStatementsで実行。
  2. 発行されたQIDを han_qid_overrides.json に登録する
       {"野本藩": "...", "東方藩": "...", "松山新田藩": "Q..."}
  3. python run_batch_shikoku.py 松山新田藩   で役職項目TSVを生成。
"""
# (藩名, 旧国, 説明文, 追加ステートメント[列のリスト])
NEW_HAN = [
    # 松山新田藩(伊予国)。伊予松山藩の支藩(久松松平家)。新田藩は固有の領地・陣屋を持たない分家藩
    ("松山新田藩", "伊予国", "伊予国の藩", []),
]


def main():
    lines = []
    for name, prov, desc, extra in NEW_HAN:
        lines.append(["CREATE"])
        lines.append(["LAST", "Lja", f'"{name}"'])
        lines.append(["LAST", "Dja", f'"{desc}"'])
        lines.append(["LAST", "P17", "Q17"])
        lines.append(["LAST", "P2348", "Q184963"])
        for e in extra:
            lines.append(["LAST"] + e)
    with open("new_han_items_shikoku.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join("\t".join(l) for l in lines) + "\n")
    print("\n".join("\t".join(l) for l in lines))
    print("\nnew_han_items_shikoku.tsv を生成しました。重複と P31 などを確認してから投入してください。")


if __name__ == "__main__":
    main()
