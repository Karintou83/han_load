"""
近畿で、Wikidataに藩項目(jawikiのsitelink付き)が無い藩の「藩」項目を新規作成する
QuickStatements V1 TSVを作る。Wikidataへの書き込みは行わない。

使い方(code/ フォルダで):
    python make_han_items_kinki.py     # new_han_items_kinki.tsv を生成

対象: 朝日山藩・大森藩(近江国)
  どちらも jawiki の記事が山形藩へのリダイレクトで、藩QIDが引けない(2026-10-14 の --check)。
  Template:朝日山藩主 / Template:大森藩主 は存在する。
  山形藩(出羽国、整備済み)とは根拠地が違うので、同じ藩項目は共有せず新規作成する方針。

投入前に必ず確認すること:
  - Wikidataで「朝日山藩」「大森藩」を検索し、すでに項目が存在しないか確認する(重複作成を避ける)。
    存在するがjawikiの記事にsitelinkが無い(リダイレクトのため)だけなら、新規作成せず
    han_qid_overrides.json に既存QIDを登録するだけでよい。
  - 各藩の旧国・領地・年代を日本語版Wikipedia(山形藩の記事、Templateの内容)で確認し、
    説明文を必要なら直す。藩の標準構成(P31の値など)は既存の藩項目に合わせて extra に足す。

投入後の手順:
  1. new_han_items_kinki.tsv をQuickStatementsで実行。
  2. 発行されたQIDを han_qid_overrides.json に登録する
       {"朝日山藩": "Q...", "大森藩": "Q...", ...(既存の登録は残す)}
  3. python run_batch_kinki.py 朝日山藩 大森藩   で役職項目TSVを生成。
"""
# (藩名, 旧国, 説明文, 追加ステートメント[列のリスト])
NEW_HAN = [
    ("朝日山藩", "近江国", "近江国の藩", []),
    ("大森藩", "近江国", "近江国の藩", []),
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
    with open("new_han_items_kinki.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join("\t".join(l) for l in lines) + "\n")
    print("\n".join("\t".join(l) for l in lines))
    print("\nnew_han_items_kinki.tsv を生成しました。重複と P31 などを確認してから投入してください。")


if __name__ == "__main__":
    main()
