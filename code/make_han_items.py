"""
Wikidataに藩の項目が無い藩(記事が他の藩へのリダイレクト、または記事自体が無い藩)の
「藩」項目を新規作成するQuickStatements V1 TSVを作る。Wikidataへの書き込みは行わない。

使い方(code/ フォルダで):
    python make_han_items.py            # new_han_items.tsv を生成

投入後の手順:
  1. new_han_items.tsv を QuickStatements に貼り付けて実行(まず1藩だけ試し打ち)。
  2. 発行されたQIDを han_qid_overrides.json に登録する
       {"野本藩": "Q...", "東方藩": "Q..."}
  3. python run_batch_kanto.py 野本藩 東方藩   で役職項目TSVを生成。

【要確認】藩項目の標準的な構成(P31の値など)は、既存の藩項目(例: 峰山藩 Q1073012、湯本藩 Q141661613)
に合わせること。ここでは確実に分かっている定数(P17=日本、P2348=江戸時代)とラベル・説明・存続期間だけ出す。
P31(藩のクラス)・P131(旧国)・P571/P576は、下の NEW_HAN の extra に既存項目と同じ値をQIDで足してから投入する。
"""
# (藩名, 旧国, 説明文, 追加ステートメント[列のリスト])
NEW_HAN = [
    # 野本藩(武蔵国)。伯太藩の前身だが陣屋が違うので別の藩として扱う
    ("野本藩", "武蔵国", "武蔵国の藩", []),
    # 東方藩(武蔵国)。1601年まで存在した藩
    ("東方藩", "武蔵国", "武蔵国の藩", [["P576", "+1601-00-00T00:00:00Z/9"]]),
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
    with open("new_han_items.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join("\t".join(l) for l in lines) + "\n")
    print("\n".join("\t".join(l) for l in lines))
    print("\nnew_han_items.tsv を生成しました。P31などを既存の藩項目に合わせて足してから投入してください。")


if __name__ == "__main__":
    main()
